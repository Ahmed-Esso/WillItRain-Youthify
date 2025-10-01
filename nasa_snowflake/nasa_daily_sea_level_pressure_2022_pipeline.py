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

VARIABLES = ["SLP"]  # ضغط مستوى سطح البحر

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

def get_pressure_category(pressure_hpa):
    """تصنيف ضغط مستوى سطح البحر"""
    if pressure_hpa < 980:
        return "Very Low"
    elif pressure_hpa < 1000:
        return "Low"
    elif pressure_hpa < 1020:
        return "Normal"
    elif pressure_hpa < 1040:
        return "High"
    else:
        return "Very High"

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR SLP
# ==========================

@op(out=DynamicOut())
def search_nasa_files_slp_2022(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة لكل مصر
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    
    # مصر كلها - حدود جغرافية شاملة
    # شمالاً: البحر المتوسط (32.0) - جنوباً: حدود السودان (22.0)
    # غرباً: حدود ليبيا (25.0) - شرقاً: البحر الأحمر (37.0)
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-1-31"),  # سنة 2022 كاملة
        bounding_box=(25.0, 22.0, 37.0, 32.0)  # مصر كلها
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    # نرجع كل file كـ dynamic output منفصل
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )


@op
def process_single_file_slp(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسط اليومي لـ SLP
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # فتح الملف مباشرة من الإنترنت
        file_stream = earthaccess.open([granule])[0]
        
        # فتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        # معالجة المتغير SLP
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
                
                # نتأكد أن البيانات ضمن نطاق مصر
                df = df[
                    (df["lat"] >= 22.0) & (df["lat"] <= 32.0) &
                    (df["lon"] >= 25.0) & (df["lon"] <= 37.0)
                ]
                
                if df.empty:
                    context.log.warning("⚠️ No data within Egypt boundaries")
                    continue
                
                # نجمع البيانات بالساعة ونحسب المتوسط اليومي
                df["date"] = df["time"].dt.date  # نأخذ التاريخ فقط (بدون وقت)
                
                # نحسب المتوسط اليومي لكل موقع
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No SLP variable found in file")
            return pd.DataFrame()
        
        # نجمع كل البيانات اليومية
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily SLP records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()


@op
def transform_daily_slp(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل البيانات اليومية لـ SLP للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily SLP records...")
    
    # نتأكد من وجود الأعمدة المطلوبة
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # نحسب المتوسط اليومي الشامل (لجميع المواقع في مصر)
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({
            'SLP': 'mean',  # متوسط ضغط مستوى سطح البحر
            'lat': 'count'  # عدد القياسات
        })
        .reset_index()
    )
    
    # نعيد تسمية الأعمدة
    daily_summary.rename(columns={
        'SLP': 'avg_sea_level_pressure',
        'lat': 'measurement_count'
    }, inplace=True)
    
    # نضيف معلومات إضافية
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear
    daily_summary["day_name"] = pd.to_datetime(daily_summary["date"]).dt.day_name()
    daily_summary["season"] = daily_summary["month"].apply(get_season)
    
    # نضيف تصنيف ضغط مستوى سطح البحر (نحول من Pa إلى hPa للتصنيف)
    daily_summary["pressure_hpa"] = daily_summary["avg_sea_level_pressure"] / 100.0
    daily_summary["pressure_category"] = daily_summary["pressure_hpa"].apply(get_pressure_category)
    
    # نحسب ضغط مستوى سطح البحر القصوى والدنيا لكل يوم
    daily_stats = (
        df.groupby(["date"])
        .agg({
            'SLP': ['max', 'min', 'std']
        })
        .reset_index()
    )
    daily_stats.columns = ['date', 'max_sea_level_pressure', 'min_sea_level_pressure', 'pressure_std']
    
    # ندمج الإحصائيات مع البيانات الأساسية
    final_result = pd.merge(daily_summary, daily_stats, on="date", how="left")
    
    # نرتب الأعمدة
    result = final_result[[
        "date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", 
        "avg_sea_level_pressure", "max_sea_level_pressure", "min_sea_level_pressure", "pressure_std",
        "pressure_hpa", "pressure_category", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily SLP summary records for Egypt")
    
    return result


@op
def load_daily_slp_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات ضغط مستوى سطح البحر اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily SLP records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # ننشئ الجدول لو غير موجود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_SEA_LEVEL_PRESSURE (
                date DATE,
                year INT,
                month INT,
                day INT,
                day_of_year INT,
                day_name STRING,
                season STRING,
                variable STRING,
                avg_sea_level_pressure FLOAT,
                max_sea_level_pressure FLOAT,
                min_sea_level_pressure FLOAT,
                pressure_std FLOAT,
                pressure_hpa FLOAT,
                pressure_category STRING,
                measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # batch insert للبيانات اليومية
        insert_query = """
            INSERT INTO NASA_DAILY_SEA_LEVEL_PRESSURE 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_sea_level_pressure, max_sea_level_pressure, min_sea_level_pressure, pressure_std,
             pressure_hpa, pressure_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                float(row["avg_sea_level_pressure"]),
                float(row["max_sea_level_pressure"]),
                float(row["min_sea_level_pressure"]),
                float(row["pressure_std"]),
                float(row["pressure_hpa"]),
                row["pressure_category"],
                int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        # إدخال جماعي
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily SLP records for Egypt")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise


# ==========================
# DAGSTER JOB - DAILY SEA LEVEL PRESSURE PIPELINE 2022
# ==========================

@job
def nasa_daily_sea_level_pressure_2022_pipeline():
    """
    Pipeline لمعالجة بيانات ضغط مستوى سطح البحر اليومية لسنة 2022 لكل مصر
    """
    # بحث عن الملفات لسنة 2022
    files = search_nasa_files_slp_2022()
    
    # معالجة كل ملف وحساب المتوسطات اليومية لـ SLP
    processed = files.map(process_single_file_slp)
    
    # تحويل البيانات اليومية
    transformed = processed.map(transform_daily_slp)
    
    # تحميل البيانات اليومية لـ Snowflake
    transformed.map(load_daily_slp_to_snowflake)
