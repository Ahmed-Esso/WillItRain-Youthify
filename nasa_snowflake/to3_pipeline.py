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

VARIABLES = ["TO3"]  # تركيز الأوزون السطحي

# ==========================
# Helper Function
# ==========================
def get_snowflake_connection():
    """Create Snowflake connection"""
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

def get_season(month):
    """تحديد الفصل بناءً على الشهر"""
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Autumn"

def get_surface_ozone_category(ozone):
    """تصنيف تركيز الأوزون السطحي"""
    if ozone < 20:
        return "Very Good"
    elif ozone < 40:
        return "Good"
    elif ozone < 60:
        return "Moderate"
    elif ozone < 80:
        return "Poor"
    else:
        return "Very Poor"

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR TO3
# ==========================

@op(out=DynamicOut())
def search_nasa_files_to3_2022(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة لكل مصر
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

@op
def process_single_file_to3(context, granule) -> pd.DataFrame:
    """معالجة ملف واحد وحساب المتوسط اليومي لـ TO3"""
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        for var in VARIABLES:
            if var in ds.variables:
                context.log.info(f"📊 Processing variable: {var}")
                df = ds[[var]].to_dataframe().reset_index()
                
                if "time" not in df.columns:
                    context.log.warning("⚠️ No time column found")
                    continue
                
                df["time"] = pd.to_datetime(df["time"])
                df = df[
                    (df["lat"] >= 22.0) & (df["lat"] <= 32.0) &
                    (df["lon"] >= 25.0) & (df["lon"] <= 37.0)
                ]
                
                if df.empty:
                    context.log.warning("⚠️ No data within Egypt boundaries")
                    continue
                
                df["date"] = df["time"].dt.date
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["
