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

VARIABLES = ["V10M"]  # سرعة الرياح على ارتفاع 10 أمتار

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

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR V10M
# ==========================

@op(out=DynamicOut())
def search_nasa_files_2022_wind(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-12-31"),  # سنة 2022 كاملة
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
def process_single_file_v10m_wind(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسط اليومي لـ V10M
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # فتح الملف مباشرة من الإنترنت
        file_stream = earthaccess.open([granule])[0]
        
        # فتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        # معالجة المتغير V10M
        for var in VARIABLES:
            if var in ds.variables:
                context.log.info(f"📊 Processing variable: {var}")
                
                # نحول البيانات لـ DataFrame مع الاحتفاظ بالوقت
                df = ds[[var]].to_dataframe().reset_index()
                
                # نتأكد من وجود عمود الوقت
                if "time" not in df.columns:
                    context.log.warning("⚠️ No time column found")
                    continue
                
                # نحول الوقت لـ datetime
                df["time"] = pd.to_datetime(df["time"])
                
                # نجمع البيانات بالساعة ونحسب المتوسط اليومي
                df["date"] = df["time"].dt.date  # نأخذ التاريخ فقط (بدون وقت)
                
                # نحسب المتوسط اليومي لكل موقع
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No V10M variable found in file")
            return pd.DataFrame()
        
        # نجمع كل البيانات اليومية
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily V10M records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()


@op
def transform_daily_v10m_wind(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل البيانات اليومية لـ V10M للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily V10M records...")
    
    # نتأكد من وجود الأعمدة المطلوبة
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # نحسب المتوسط اليومي الشامل (لجميع المواقع)
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({
            'V10M': 'mean',  # متوسط سرعة الرياح
            'lat': 'count'   # عدد القياسات
        })
        .reset_index()
    )
    
    # نعيد تسمية الأعمدة
    daily_summary.rename(columns={
        'V10M': 'avg_wind_speed',
        'lat': 'measurement_count'
    }, inplace=True)
    
    # نضيف معلومات إضافية
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear
    daily_summary["day_name"] = pd.to_datetime(daily_summary["date"]).dt.day_name()
    daily_summary["season"] = daily_summary["month"].apply(get_season)
    
    # نضيف تصنيف سرعة الرياح
    daily_summary["wind_category"] = daily_summary["avg_wind_speed"].apply(get_wind_category)
    
    # نحسب سرعة الرياح القصوى والدنيا لكل يوم
    daily_stats = (
        df.groupby(["date"])
        .agg({
            'V10M': ['max', 'min', 'std']
        })
        .reset_index()
    )
    daily_stats.columns = ['date', 'max_wind_speed', 'min_wind_speed', 'wind_speed_std']
    
    # ندمج الإحصائيات مع البيانات الأساسية
    final_result = pd.merge(daily_summary, daily_stats, on="date", how="left")
    
    # نرتب الأعمدة
    result = final_result[[
        "date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", 
        "avg_wind_speed", "max_wind_speed", "min_wind_speed", "wind_speed_std", 
        "wind_category", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily V10M summary records")
    
    return result


@op
def load_daily_v10m_to_snowflake_wind(context, df: pd.DataFrame):
    """
    تحميل بيانات سرعة الرياح اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily V10M records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # ننشئ الجدول لو غير موجود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_WIND_SPEED (
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
                wind_category STRING,
                measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # batch insert للبيانات اليومية
        insert_query = """
            INSERT INTO NASA_DAILY_WIND_SPEED 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_wind_speed, max_wind_speed, min_wind_speed, wind_speed_std, 
             wind_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                row["wind_category"],
                int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        # إدخال جماعي
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily V10M records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise


# ==========================
# DAGSTER JOB - DAILY WIND SPEED PIPELINE 2022
# ==========================

@job
def nasa_daily_wind_speed_2022_pipeline():
    """
    Pipeline لمعالجة بيانات سرعة الرياح اليومية لسنة 2022
    """
    # بحث عن الملفات لسنة 2022
    files = search_nasa_files_2022_wind()
    
    # معالجة كل ملف وحساب المتوسطات اليومية لـ V10M
    processed = files.map(process_single_file_v10m_wind)
    
    # تحويل البيانات اليومية
    transformed = processed.map(transform_daily_v10m_wind)
    
    # تحميل البيانات اليومية لـ Snowflake
    transformed.map(load_daily_v10m_to_snowflake_wind)
