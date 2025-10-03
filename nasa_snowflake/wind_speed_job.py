# jobs/wind_pressure/wind_speed_job.py
import pandas as pd
import numpy as np
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut())
def search_wind_files(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name="M2I1NXASM",
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} wind files")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op
def process_wind_file(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # Debug: show available variables
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables: {available_vars}")
        
        if "U10M" not in ds or "V10M" not in ds:
            context.log.warning("U10M or V10M not found")
            return pd.DataFrame()
        
        df = ds[["U10M", "V10M"]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        
        if df.empty:
            context.log.warning("No data within Alexandria bounds")
            return pd.DataFrame()
            
        df["wind_speed"] = np.sqrt(df["U10M"]**2 + df["V10M"]**2)
        ds.close()
        
        context.log.info(f"Processed {len(df)} wind speed data points")
        return df[["time", "wind_speed"]]
        
    except Exception as e:
        context.log.error(f"Error processing wind file: {e}")
        return pd.DataFrame()

@op
def transform_wind_daily(context, df):
    if df.empty: 
        context.log.info("No data to transform for wind speed")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    
    # ✅ الإصلاح: استخدام agg بطريقة صحيحة
    daily_stats = df.groupby("date")["wind_speed"].agg([
        ('avg_value', 'mean'),
        ('min_value', 'min'),
        ('max_value', 'max'),
        ('std_value', 'std'),
        ('measurement_count', 'count')
    ]).reset_index()
    
    daily_stats["variable"] = "wind_speed"
    
    context.log.info(f"Transformed {len(daily_stats)} daily wind speed records")
    return daily_stats

@op
def load_wind_to_snowflake(context, df: pd.DataFrame):
    """تحميل بيانات سرعة الرياح لـ Snowflake"""
    if df.empty:
        context.log.info("No wind speed data to load")
        return
    
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    # إنشاء الجدول إذا لم يكن موجوداً (أفضل من REPLACE)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS NASA_WIND_SPEED_ALEX (
            date DATE,
            variable STRING,
            avg_value FLOAT,
            min_value FLOAT,
            max_value FLOAT,
            std_value FLOAT,
            measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    # ✅ الإصلاح: ترتيب الأعمدة بشكل صحيح
    rows = []
    for _, row in df.iterrows():
        rows.append((
            row["date"],                      # DATE
            "wind_speed",                     # STRING 
            float(row["avg_value"]),          # FLOAT
            float(row["min_value"]),          # FLOAT  
            float(row["max_value"]),          # FLOAT
            float(row["std_value"]) if pd.notna(row["std_value"]) else 0.0,  # FLOAT (تعامل مع NaN)
            int(row["measurement_count"])     # INT
        ))
    
    # ✅ استخدام INSERT مع تحديد الأعمدة
    insert_query = """
        INSERT INTO NASA_WIND_SPEED_ALEX 
        (date, variable, avg_value, min_value, max_value, std_value, measurement_count) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        cur.executemany(insert_query, rows)
        conn.commit()
        context.log.info(f"✅ Successfully loaded {len(df)} daily wind speed records")
        
    except Exception as e:
        context.log.error(f"❌ Error loading wind speed data: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def wind_speed_job():
    files = search_wind_files()
    processed = files.map(process_wind_file)
    transformed = processed.map(transform_wind_daily)
    transformed.map(load_wind_to_snowflake)
