import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess

# ==========================
# Snowflake Config
# ==========================
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_PASSWORD = "Ahmedesso@2005"
SNOWFLAKE_AUTHENTICATOR = "snowflake"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

VARIABLES = ["U10M", "V10M"]

# ==========================
# Helper
# ==========================
def get_snowflake_connection():
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=SNOWFLAKE_ROLE
    )

# ==========================
# DAGSTER OPS
# ==========================
@op(out=DynamicOut())
def search_nasa_files(context):
    context.log.info("🔍 Login NASA Earthdata...")
    earthaccess.login(strategy="environment")

    context.log.info("🔍 Search 2022 files...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # القاهرة
    )

    context.log.info(f"✅ Found {len(results)} files")
    for idx, granule in enumerate(results):
        yield DynamicOutput(value=granule, mapping_key=f"file_{idx}")


@op
def process_single_file(context, granule) -> pd.DataFrame:
    """إخراج البيانات الخام اليومية لـ U10M و V10M"""
    try:
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")

        all_data = []
        for var in VARIABLES:
            if var in ds.variables:
                df = ds[[var]].to_dataframe().reset_index()
                df["variable"] = var
                df["date"] = pd.to_datetime(df["time"]).dt.date
                all_data.append(df)

        ds.close()
        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        return combined

    except Exception as e:
        context.log.error(f"❌ Error: {e}")
        return pd.DataFrame()


@op
def load_raw_to_snowflake(context, df: pd.DataFrame):
    """تحميل القيم الخام (U10M و V10M) لـ Snowflake"""
    if df.empty:
        return "skipped"

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_WIND_RAW (
                date DATE,
                lat FLOAT,
                lon FLOAT,
                variable STRING,
                value FLOAT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)

        insert_query = """
            INSERT INTO NASA_WIND_RAW (date, lat, lon, variable, value)
            VALUES (%s, %s, %s, %s, %s)
        """

        data_to_insert = [
            (row["date"], float(row["lat"]), float(row["lon"]), row["variable"], float(row[row["variable"]]))
            for _, row in df.iterrows()
        ]

        cur.executemany(insert_query, data_to_insert)
        conn.commit()

        context.log.info(f"✅ Inserted {len(df)} rows into NASA_WIND_RAW")
        cur.close()
        conn.close()

        return "success"

    except Exception as e:
        context.log.error(f"❌ Error loading raw: {e}")
        raise

# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_raw_wind_pipeline():
    files = search_nasa_files()
    processed = files.map(process_single_file)
    processed.map(load_raw_to_snowflake)
