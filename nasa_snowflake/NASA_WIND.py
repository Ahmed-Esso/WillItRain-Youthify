import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime, timedelta
import numpy as np

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

VARIABLES = ["U10M", "V10M"]  # مركبات الرياح على ارتفاع 10 أمتار

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

def get_wind_category(speed):
    """تصنيف سرعة الرياح"""
    if speed < 0.5:
        return "Calm"
    elif speed < 1.5:
        return "Light Air"
    elif speed < 3.0:
        return "Light Breeze"
    elif speed < 5.0:
        return "Gentle Breeze"
    elif speed < 8.0:
        return "Moderate Breeze"
    elif speed < 10.5:
        return "Fresh Breeze"
    else:
        return "Strong Breeze"

def calculate_wind_direction(u_component, v_component):
    """حساب اتجاه الرياح (بالدرجات) من المركبات"""
    # حساب الاتجاه بالراديان ثم تحويله لدرجات
    direction_rad = np.arctan2(-u_component, -v_component)
    direction_deg = np.degrees(direction_rad)
    
    # تحويل إلى نطاق 0-360
    direction_deg = direction_deg % 360
    return direction_deg

# ==========================
# DAGSTER OPS - REAL WIND SPEED (أسماء معدلة)
# ==========================

@op(out=DynamicOut())
def search_nasa_files_2022_real_wind(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة - للإصدار الجديد
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-01-31"),  # سنة 2022 كاملة
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # منطقة القاهرة
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    # نرجع كل file كـ dynamic output منفصل
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

@op
def process_single_file_real_wind_components(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب سرعة الرياح الحقيقية من U10M و V10M
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # فتح الملف مباشرة من الإنترنت
        file_stream = earthaccess.open([granule])[0]
        
        # فتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        # نتأكد من وجود كلا المركبتين
        if "U10M" in ds.variables and "V10M" in ds.variables:
            context.log.info("📊 Processing wind components U10M & V10M")
            
            # نحول البيانات لـ DataFrame
            df = ds[["U10M", "V10M"]].to_dataframe().reset_index()
            
            # نتأكد من وجود عمود الوقت
            if "time" not in df.columns:
                context.log.warning("⚠️ No time column found")
                return pd.DataFrame()
            
            # نحول الوقت لـ datetime
            df["time"] = pd.to_datetime(df["time"])
            df["date"] = df["time"].dt.date
            
            # نحسب سرعة الرياح الحقيقية من المركبتين
            df["WIND_SPEED"] = np.sqrt(df["U10M"]**2 + df["V10M"]**2)
            
            # نحسب اتجاه الرياح
            df["WIND_DIRECTION"] = calculate_wind_direction(df["U10M"], df["V10M"])
            
            # نحسب المتوسط اليومي لكل موقع
            daily_avg = df.groupby(["date", "lat", "lon"]).agg({
                'WIND_SPEED': 'mean',
                'WIND_DIRECTION': 'mean',
                'U10M': 'mean',
                'V10M': 'mean'
            }).reset_index()
            
            daily_avg["variable"] = "WIND_SPEED"
            
            all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning("⚠️ No wind components found in file")
            return pd.DataFrame()
        
        # نجمع كل البيانات اليومية
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily wind speed records")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()

@op
def transform_daily_real_wind_speed(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل البيانات اليومية لسرعة الرياح الحقيقية
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily wind speed records...")
    
    # نتأكد من وجود الأعمدة المطلوبة
    required_cols = ["date", "WIND_SPEED", "U10M", "V10M", "WIND_DIRECTION"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # نحسب المتوسط اليومي الشامل (لجميع المواقع)
    daily_summary = (
        df.groupby(["date"])
        .agg({
            'WIND_SPEED': ['mean', 'max', 'min', 'std'],
            'WIND_DIRECTION': 'mean',
            'U10M': 'mean',
            'V10M': 'mean',
            'lat': 'count'
        })
        .reset_index()
    )
    
    # نصلح أسماء الأعمدة بعد الـ groupby
    daily_summary.columns = [
        'date', 
        'avg_wind_speed', 'max_wind_speed', 'min_wind_speed', 'wind_speed_std',
        'wind_direction',
        'avg_u_component', 'avg_v_component',
        'measurement_count'
    ]
    
    # نضيف معلومات إضافية
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear
    daily_summary["day_name"] = pd.to_datetime(daily_summary["date"]).dt.day_name()
    daily_summary["season"] = daily_summary["month"].apply(get_season)
    daily_summary["variable"] = "WIND_SPEED"
    
    # نضيف تصنيف سرعة الرياح
    daily_summary["wind_category"] = daily_summary["avg_wind_speed"].apply(get_wind_category)
    
    # نرتب الأعمدة
    result = daily_summary[[
        "date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", 
        "avg_wind_speed", "max_wind_speed", "min_wind_speed", "wind_speed_std",
        "wind_direction", "avg_u_component", "avg_v_component",
        "wind_category", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily wind speed summary records")
    
    return result

@op
def load_daily_real_wind_speed_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات سرعة الرياح الحقيقية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily wind speed records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # ننشئ الجدول الجديد لو غير موجود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_REAL_WIND_SPEED (
                date DATE,
                year INT,
                month INT,
                day INT,
                day_of_year INT,
                day_name STRING,
                season STRING,
                variable STRING,
                avg_wind_speed FLOAT,
                max_wind_speed FLOAT,
                min_wind_speed FLOAT,
                wind_speed_std FLOAT,
                wind_direction FLOAT,
                avg_u_component FLOAT,
                avg_v_component FLOAT,
                wind_category STRING,
                measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # batch insert للبيانات اليومية
        insert_query = """
            INSERT INTO NASA_DAILY_REAL_WIND_SPEED 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_wind_speed, max_wind_speed, min_wind_speed, wind_speed_std,
             wind_direction, avg_u_component, avg_v_component,
             wind_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # نحضر البيانات للإدخال
        data_to_insert = [
            (
                row["date"], 
                int(row["year"]), 
                int(row["month"]), 
                int(row["day"]), 
                int(row["day_of_year"]),
                row["day_name"],
                row["season"],
                row["variable"], 
                float(row["avg_wind_speed"]),
                float(row["max_wind_speed"]),
                float(row["min_wind_speed"]),
                float(row["wind_speed_std"]),
                float(row["wind_direction"]),
                float(row["avg_u_component"]),
                float(row["avg_v_component"]),
                row["wind_category"],
                int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        # إدخال جماعي
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} REAL wind speed records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise

# ==========================
# DAGSTER JOB - REAL WIND SPEED PIPELINE 2022
# ==========================

@job
def nasa_daily_real_wind_speed_2022_pipeline():
    """
    Pipeline لمعالجة بيانات سرعة الرياح الحقيقية اليومية لسنة 2022
    """
    # بحث عن الملفات لسنة 2022
    files = search_nasa_files_2022_real_wind()
    
    # معالجة كل ملف وحساب سرعة الرياح الحقيقية من U10M و V10M
    processed = files.map(process_single_file_real_wind_components)
    
    # تحويل البيانات اليومية
    transformed = processed.map(transform_daily_real_wind_speed)
    
    # تحميل البيانات اليومية لـ Snowflake
    transformed.map(load_daily_real_wind_speed_to_snowflake)

# ==========================
# REPOSITORY DEFINITION
# ==========================
from dagster import repository

@repository
def nasa_repository():
    """
    Repository واحد يحتوي على جميع الـ Jobs
    """
    return [
        nasa_daily_real_wind_speed_2022_pipeline,
        # يمكنك إضافة الـ job القديم هنا بعد تعديل أسماء الـ ops فيه أيضاً
    ]

# ==========================
# MAIN EXECUTION (Optional)
# ==========================
if __name__ == "__main__":
    # لتشغيل الـ pipeline مباشرة (اختياري)
    result = nasa_daily_real_wind_speed_2022_pipeline.execute_in_process()
