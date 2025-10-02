# my_pipeline.py
import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime, timedelta

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
# COMMON SEARCH OP (مشترك لجميع الـ pipelines)
# ==========================

@op(out=DynamicOut())
def search_nasa_files_2022_common(context):
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-1-5"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

# ==========================
# PRECIPITATION & CLOUD FRACTION PIPELINE
# ==========================

VARIABLES_PRECIP_CLOUD = ["precipitation", "cloud_fraction"]

@op
def process_single_file_precip_cloud(context, granule) -> pd.DataFrame:
    try:
        context.log.info(f"📥 Streaming file for precip/cloud: {granule['meta']['native-id']}")
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        for var in VARIABLES_PRECIP_CLOUD:
            if var in ds.variables:
                context.log.info(f"📊 Processing variable: {var}")
                df = ds[[var]].to_dataframe().reset_index()
                
                if "time" not in df.columns:
                    continue
                
                df["time"] = pd.to_datetime(df["time"])
                df = df[
                    (df["lat"] >= 22.0) & (df["lat"] <= 32.0) &
                    (df["lon"] >= 25.0) & (df["lon"] <= 37.0)
                ]
                
                if df.empty:
                    continue
                
                df["date"] = df["time"].dt.date
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily precip/cloud records")
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing precip/cloud file: {e}")
        return pd.DataFrame()

@op
def transform_daily_precip_cloud(context, df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({list(df.columns)[3]: 'mean', 'lat': 'count'})
        .reset_index()
    )
    
    if 'precipitation' in df['variable'].values:
        daily_summary.rename(columns={list(df.columns)[3]: 'avg_value'}, inplace=True)
    elif 'cloud_fraction' in df['variable'].values:
        daily_summary.rename(columns={list(df.columns)[3]: 'avg_value'}, inplace=True)
    
    daily_summary.rename(columns={'lat': 'measurement_count'}, inplace=True)
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    result = daily_summary[["date", "year", "month", "day", "variable", "avg_value", "measurement_count"]]
    return result

@op
def load_daily_precip_cloud_to_snowflake(context, df: pd.DataFrame):
    if df.empty:
        return "skipped"
    
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS NASA_DAILY_PRECIP_CLOUD (
            date DATE, year INT, month INT, day INT,
            variable STRING, avg_value FLOAT, measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    insert_query = """
        INSERT INTO NASA_DAILY_PRECIP_CLOUD 
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
    
    context.log.info(f"✅ Loaded {len(df)} precip/cloud records")
    return "success"

@job
def nasa_daily_precip_cloud_2022_pipeline():
    files = search_nasa_files_2022_common()
    processed = files.map(process_single_file_precip_cloud)
    transformed = processed.map(transform_daily_precip_cloud)
    transformed.map(load_daily_precip_cloud_to_snowflake)

# ==========================
# SURFACE PRESSURE PIPELINE (PS)
# ==========================

VARIABLES_PS = ["PS"]

@op
def process_single_file_ps(context, granule) -> pd.DataFrame:
    try:
        context.log.info(f"📥 Streaming file for PS: {granule['meta']['native-id']}")
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        for var in VARIABLES_PS:
            if var in ds.variables:
                df = ds[[var]].to_dataframe().reset_index()
                
                if "time" not in df.columns:
                    continue
                
                df["time"] = pd.to_datetime(df["time"])
                df = df[
                    (df["lat"] >= 22.0) & (df["lat"] <= 32.0) &
                    (df["lon"] >= 25.0) & (df["lon"] <= 37.0)
                ]
                
                if df.empty:
                    continue
                
                df["date"] = df["time"].dt.date
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily PS records")
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing PS file: {e}")
        return pd.DataFrame()

@op
def transform_daily_ps(context, df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({'PS': 'mean', 'lat': 'count'})
        .reset_index()
    )
    
    daily_summary.rename(columns={'PS': 'avg_value', 'lat': 'measurement_count'}, inplace=True)
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    result = daily_summary[["date", "year", "month", "day", "variable", "avg_value", "measurement_count"]]
    return result

@op
def load_daily_ps_to_snowflake(context, df: pd.DataFrame):
    if df.empty:
        return "skipped"
    
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS NASA_DAILY_SURFACE_PRESSURE (
            date DATE, year INT, month INT, day INT,
            variable STRING, avg_value FLOAT, measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    insert_query = """
        INSERT INTO NASA_DAILY_SURFACE_PRESSURE 
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
    
    context.log.info(f"✅ Loaded {len(df)} PS records")
    return "success"

@job
def nasa_daily_surface_pressure_2022_pipeline():
    files = search_nasa_files_2022_common()
    processed = files.map(process_single_file_ps)
    transformed = processed.map(transform_daily_ps)
    transformed.map(load_daily_ps_to_snowflake)
