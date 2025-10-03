# my_pipeline_chlora.py
import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime

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

# ==========================
# Helper Function
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
# VARIABLES: Chlorophyll-a only
# ==========================
VARIABLES = ["chlor_a"]

# ==========================
# SEARCH OP
# ==========================
@op(out=DynamicOut())
def search_nasa_chlor_a_2022(context):
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for MODIS Aqua Chlorophyll files for 2022...")
    results = earthaccess.search_data(
        short_name="MODISA_L3m_CHL",   # Chlorophyll MODIS Aqua L3
        # version="2018.0",            # optional: بعض الداتا مش بتحتاج version
        temporal=("2022-01-01", "2022-01-05"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)  # مصر / شرق المتوسط
    )
    
    context.log.info(f"✅ Found {len(results)} chlor_a files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

# ==========================
# PROCESS Chlorophyll-a
# ==========================
@op
def process_single_chlor_a(context, granule) -> pd.DataFrame:
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream)
        
        if "chlor_a" not in ds.variables:
            context.log.warning("⚠️ chlor_a not found in file")
            return pd.DataFrame()
        
        df = ds[["chlor_a"]].to_dataframe().reset_index()
        
        # بعض منتجات L3 مش بيبقى فيها time، فنعمل fallback
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df["date"] = df["time"].dt.date
        else:
            df["date"] = datetime.utcnow().date()
        
        daily_avg = df.groupby(["date", "lat", "lon"])["chlor_a"].mean().reset_index()
        daily_avg["variable"] = "chlor_a"
        
        ds.close()
        
        context.log.info(f"✅ Processed {len(daily_avg)} chlor_a records")
        return daily_avg
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()

# ==========================
# TRANSFORM Chlorophyll-a
# ==========================
@op
def transform_daily_data(context, df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({"chlor_a": 'mean', 'lat': 'count'})
        .reset_index()
    )
    
    daily_summary.rename(columns={"chlor_a": 'avg_value', 'lat': 'measurement_count'}, inplace=True)
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    result = daily_summary[["date", "year", "month", "day", "variable", "avg_value", "measurement_count"]]
    return result

# ==========================
# LOAD to Snowflake
# ==========================
@op
def load_daily_to_snowflake(context, df: pd.DataFrame):
    if df.empty:
        return "skipped"
    
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS NASA_DAILY_CHLOR_A (
            date DATE, year INT, month INT, day INT,
            variable STRING, avg_value FLOAT, measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    insert_query = """
        INSERT INTO NASA_DAILY_CHLOR_A 
        (date, year, month, day, variable, avg_value, measurement_count) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    data_to_insert = [
        (row["date"], int(row["year"]), int(row["month"]), int(row["day"]), 
         row["variable"], float(row["avg_value"]), int(row["measurement_count"]))
        for _, row in df.iterrows()
    ]
    
    cur.executemany(insert_query, data_to_insert)
    conn.commit()
    cur.close()
    conn.close()
    
    context.log.info(f"✅ Loaded {len(df)} records")
    return "success"

# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_daily_chlor_a_2022_pipeline():
    files = search_nasa_chlor_a_2022()
    processed = files.map(process_single_chlor_a)
    transformed = processed.map(transform_daily_data)
    transformed.map(load_daily_to_snowflake)
