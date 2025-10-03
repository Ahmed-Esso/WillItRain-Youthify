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

VARIABLES = ["OMEGA500"]  # السرعة الرأسية عند 500 hPa

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

def get_omega_category(omega):
    """تصنيف السرعة الرأسية"""
    if omega < -0.5:
        return "Strong Upward"
    elif omega < -0.1:
        return "Moderate Upward"
    elif omega < 0.1:
        return "Neutral"
    elif omega < 0.5:
        return "Moderate Downward"
    else:
        return "Strong Downward"

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR OMEGA500
# ==========================

@op(out=DynamicOut())
def search_nasa_files_omega500_2022(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة لكل مصر
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    
    # مصر كلها - حدود جغرافية شاملة
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-1-15"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

@op
def process_single_file_omega500(context, granule) -> pd.DataFrame:
    """معالجة ملف واحد وحساب المتوسط اليومي لـ OMEGA500"""
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
                daily_avg["variable"] = var
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No OMEGA500 variable found in file")
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily OMEGA500 records from file")
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()

@op
def transform_daily_omega500(context, df: pd.DataFrame) -> pd.DataFrame:
    """تحويل البيانات اليومية لـ OMEGA500"""
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily OMEGA500 records...")
    
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({'OMEGA500': 'mean', 'lat': 'count'})
        .reset_index()
    )
    
    daily_summary.rename(columns={'OMEGA500': 'avg_vertical_velocity', 'lat': 'measurement_count'}, inplace=True)
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear
    daily_summary["day_name"] = pd.to_datetime(daily_summary["date"]).dt.day_name()
    daily_summary["season"] = daily_summary["month"].apply(get_season)
    daily_summary["omega_category"] = daily_summary["avg_vertical_velocity"].apply(get_omega_category)
    
    daily_stats = (
        df.groupby(["date"])
        .agg({'OMEGA500': ['max', 'min', 'std']})
        .reset_index()
    )
    daily_stats.columns = ['date', 'max_vertical_velocity', 'min_vertical_velocity', 'omega_std']
    
    final_result = pd.merge(daily_summary, daily_stats, on="date", how="left")
    
    result = final_result[[
        "date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", 
        "avg_vertical_velocity", "max_vertical_velocity", "min_vertical_velocity", "omega_std",
        "omega_category", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily OMEGA500 summary records for Egypt")
    return result

@op
def load_daily_omega500_to_snowflake(context, df: pd.DataFrame):
    """تحميل بيانات OMEGA500 لـ Snowflake"""
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily OMEGA500 records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_VERTICAL_VELOCITY (
                date DATE, year INT, month INT, day INT, day_of_year INT,
                day_name STRING, season STRING, variable STRING,
                avg_vertical_velocity FLOAT, max_vertical_velocity FLOAT,
                min_vertical_velocity FLOAT, omega_std FLOAT,
                omega_category STRING, measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        insert_query = """
            INSERT INTO NASA_DAILY_VERTICAL_VELOCITY 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_vertical_velocity, max_vertical_velocity, min_vertical_velocity, omega_std,
             omega_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        data_to_insert = [
            (
                row["date"], int(row["year"]), int(row["month"]), int(row["day"]), 
                int(row["day_of_year"]), row["day_name"], row["season"], row["variable"], 
                float(row["avg_vertical_velocity"]), float(row["max_vertical_velocity"]),
                float(row["min_vertical_velocity"]), float(row["omega_std"]),
                row["omega_category"], int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        cur.close()
        conn.close()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily OMEGA500 records for Egypt")
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise

@job
def nasa_daily_vertical_velocity_2022_pipeline():
    """Pipeline لبيانات السرعة الرأسية عند 500 hPa"""
    files = search_nasa_files_omega500_2022()
    processed = files.map(process_single_file_omega500)
    transformed = processed.map(transform_daily_omega500)
    transformed.map(load_daily_omega500_to_snowflake)
