import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, Config
import earthaccess
import gc
from typing import List

# ==========================
# Configuration 
# ==========================
class PipelineConfig(Config):
    variables: List[str] = ["T2M"]  # متغير واحد للبداية
    start_date: str = "2022-01-01"
    end_date: str = "2023-01-01"    # شهر واحد بس
    max_files: int = 2              # عدد الملفات للمعالجة

# ==========================
# Snowflake Config (آمن)
# ==========================
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_AUTHENTICATOR = "externalbrowser"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

def get_snowflake_connection():
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=SNOWFLAKE_ROLE
    )

# ==========================
# DAGSTER OPS
# ==========================
@op
def extract_nasa_data_safe(context, config: PipelineConfig) -> pd.DataFrame:
    try:
        context.log.info("🔐 Logging into NASA Earthdata...")
        auth = earthaccess.login(strategy="environment")
        if not auth.authenticated:
            context.log.error("❌ Failed to authenticate with NASA Earthdata")
            raise ValueError("Authentication failed")
        context.log.info("✅ Successfully authenticated")
        context.log.info(f"🔍 Searching for data from {config.start_date} to {config.end_date}")
        results = earthaccess.search_data(
            short_name="M2T1NXSLV",
            version="5.12.4",
            temporal=(config.start_date, config.end_date),
            bounding_box=(24.70, 22.00, 37.35, 31.67)
        )
        context.log.info(f"📊 Found {len(results)} files")
        if not results:
            raise ValueError("No data found for the specified parameters")
        limited_results = results[:config.max_files]
        context.log.info(f"🎯 Processing {len(limited_results)} files")
        all_data = []
        for idx, granule in enumerate(limited_results):
            try:
                context.log.info(f"📥 Processing file {idx+1}/{len(limited_results)}")
                file_streams = earthaccess.open([granule])
                if not file_streams:
                    context.log.warning(f"⚠️ Could not open file {idx+1}")
                    continue
                ds = xr.open_dataset(file_streams[0], engine="h5netcdf")
                for variable in config.variables:
                    if variable in ds.variables:
                        context.log.info(f"🔄 Processing variable: {variable}")
                        var_data = ds[variable].isel(time=0)
                        df = var_data.to_dataframe().reset_index()
                        if len(df) > 1000:
                            df = df.sample(n=1000, random_state=42)
                        df["variable"] = variable
                        df["timestamp"] = pd.to_datetime(ds.time.values[0])
                        df["file_index"] = idx
                        all_data.append(df)
                        context.log.info(f"✅ Added {len(df)} rows for {variable}")
                        del var_data
                ds.close()
                del ds
                gc.collect()
            except Exception as e:
                context.log.error(f"❌ Error processing file {idx+1}: {e}")
                continue
        if not all_data:
            raise ValueError("No data was successfully processed")
        final_df = pd.concat(all_data, ignore_index=True)
        context.log.info(f"🎉 Total processed: {len(final_df)} rows")
        return final_df
    except Exception as e:
        context.log.error(f"❌ Error in data extraction: {e}")
        raise

@op
def transform_climate_data(context, df: pd.DataFrame) -> pd.DataFrame:
    context.log.info(f"🔄 Transforming {len(df)} rows")
    value_columns = [col for col in df.columns if col not in ['variable', 'timestamp', 'file_index', 'lat', 'lon', 'time']]
    if not value_columns:
        raise ValueError("No value column found in the data")
    value_col = value_columns[0]
    context.log.info(f"📊 Using column '{value_col}' for calculations")
    transformed = (
        df.groupby(["variable", df["timestamp"].dt.month])
        [value_col].mean()
        .reset_index()
    )
    transformed.rename(columns={
        "timestamp": "month",
        value_col: "avg_value"
    }, inplace=True)
    transformed["month"] = transformed["month"].astype(int)
    context.log.info(f"✅ Transformed to {len(transformed)} summary rows")
    return transformed

@op
def load_to_snowflake_safe(context, df: pd.DataFrame):
    if df.empty:
        context.log.warning("⚠️ No data to load")
        return
    context.log.info(f"📤 Loading {len(df)} rows to Snowflake")
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_CLIMATE_MONTHLY (
                variable STRING,
                month INT,
                avg_value FLOAT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        for _, row in df.iterrows():
            cur.execute(
                "INSERT INTO NASA_CLIMATE_MONTHLY (variable, month, avg_value) VALUES (%s, %s, %s)",
                (row["variable"], int(row["month"]), float(row["avg_value"]))
            )
        conn.commit()
        context.log.info(f"✅ Successfully loaded {len(df)} rows")
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_climate_pipeline():
    config = PipelineConfig(
        variables=["T2M"],
        start_date="2022-01-01",
        end_date="2022-01-15",
        max_files=2
    )
    data = extract_nasa_data_safe(config)
    transformed = transform_climate_data(data)
    load_to_snowflake_safe(transformed)
