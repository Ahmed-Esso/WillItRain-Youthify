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

VARIABLES = ["DISPH"]  # ارتفاع طبقة الخلط

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

def get_mixing_height_category(height):
    """تصنيف ارتفاع طبقة الخلط"""
    if height < 500:
        return "Very Low"
    elif height < 1000:
        return "Low"
    elif height < 1500:
        return "Moderate"
    elif height < 2000:
        return "High"
    else:
        return "Very High"

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR DISPH
# ==========================

@op(out=DynamicOut())
def search_nasa_files_disph_2022(context):
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
def process_single_file_disph(context, granule) -> pd.DataFrame:
    """معالجة ملف واحد وحساب المتوسط اليومي لـ DISPH"""
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
            context.log.warning(f"⚠️ No DISPH variable found in file")
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily DISPH records from file")
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()

@op
def transform_daily_disph(context, df: pd.DataFrame) -> pd.DataFrame:
    """تحويل البيانات اليومية لـ DISPH"""
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily DISPH records...")
    
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({'DISPH': 'mean', 'lat': 'count'})
        .reset_index()
    )
    
    daily_summary.rename(columns={'DISPH': 'avg_mixing_height', 'lat': 'measurement_count'}, inplace=True)
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear
    daily_summary["day_name"] = pd.to_datetime(daily_summary["date"]).dt.day_name()
    daily_summary["season"] = daily_summary["month"].apply(get_season)
    daily_summary["mixing_height_category"] = daily_summary["avg_mixing_height"].apply(get_mixing_height_category)
    
    daily_stats = (
        df.groupby(["date"])
        .agg({'DISPH': ['max', 'min', 'std']})
        .reset_index()
    )
    daily_stats.columns = ['date', 'max_mixing_height', 'min_mixing_height', 'height_std']
    
    final_result = pd.merge(daily_summary, daily_stats, on="date", how="left")
    
    result = final_result[[
        "date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", 
        "avg_mixing_height", "max_mixing_height", "min_mixing_height", "height_std",
        "mixing_height_category", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily DISPH summary records for Egypt")
    return result

@op
def load_daily_disph_to_snowflake(context, df: pd.DataFrame):
    """تحميل بيانات DISPH لـ Snowflake"""
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily DISPH records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_MIXING_HEIGHT (
                date DATE, year INT, month INT, day INT, day_of_year INT,
                day_name STRING, season STRING, variable STRING,
                avg_mixing_height FLOAT, max_mixing_height FLOAT,
                min_mixing_height FLOAT, height_std FLOAT,
                mixing_height_category STRING, measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        insert_query = """
            INSERT INTO NASA_DAILY_MIXING_HEIGHT 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_mixing_height, max_mixing_height, min_mixing_height, height_std,
             mixing_height_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        data_to_insert = [
            (
                row["date"], int(row["year"]), int(row["month"]), int(row["day"]), 
                int(row["day_of_year"]), row["day_name"], row["season"], row["variable"], 
                float(row["avg_mixing_height"]), float(row["max_mixing_height"]),
                float(row["min_mixing_height"]), float(row["height_std"]),
                row["mixing_height_category"], int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        cur.close()
        conn.close()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily DISPH records for Egypt")
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise

@job
def nasa_daily_mixing_height_2022_pipeline():
    """Pipeline لبيانات ارتفاع طبقة الخلط"""
    files = search_nasa_files_disph_2022()
    processed = files.map(process_single_file_disph)
    transformed = processed.map(transform_daily_disph)
    transformed.map(load_daily_disph_to_snowflake)
