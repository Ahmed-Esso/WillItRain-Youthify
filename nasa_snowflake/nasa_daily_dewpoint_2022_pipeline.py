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

VARIABLES = ["precipitation", "cloud_fraction"]  # معدل الأمطار ونسبة السحب

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

# ==========================
# DAGSTER OPS - DAILY AVERAGE FOR PRECIPITATION AND CLOUD_FRACTION
# ==========================

@op(out=DynamicOut())
def search_nasa_files_precip_cloud_2022(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files for 2022...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)  # مصر كلها
    )
    
    context.log.info(f"✅ Found {len(results)} files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )


@op
def process_single_file_precip_cloud(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسط اليومي
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # فتح الملف مباشرة من الإنترنت
        file_stream = earthaccess.open([granule])[0]
        
        # فتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        # معالجة المتغيرات
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
                df["date"] = df["time"].dt.date
                
                # نحسب المتوسط اليومي لكل موقع
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                
                all_daily_data.append(daily_avg)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No variables found in file")
            return pd.DataFrame()
        
        # نجمع كل البيانات اليومية
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()


@op
def transform_daily_precip_cloud(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل البيانات اليومية للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily records...")
    
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
            list(df.columns)[3]: 'mean',  # أول عمود بيانات
            'lat': 'count'
        })
        .reset_index()
    )
    
    # نعيد تسمية الأعمدة بناءً على المتغير
    if 'precipitation' in df['variable'].values:
        daily_summary.rename(columns={list(df.columns)[3]: 'avg_precipitation'}, inplace=True)
    elif 'cloud_fraction' in df['variable'].values:
        daily_summary.rename(columns={list(df.columns)[3]: 'avg_cloud_fraction'}, inplace=True)
    
    daily_summary.rename(columns={'lat': 'measurement_count'}, inplace=True)
    
    # نضيف معلومات أساسية فقط
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    # نرتب الأعمدة
    result = daily_summary[[
        "date", "year", "month", "day", "variable", 
        daily_summary.columns[2], "measurement_count"  # العمود الثاني هو avg_precipitation أو avg_cloud_fraction
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily summary records")
    
    return result


@op
def load_daily_precip_cloud_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل البيانات اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # ننشئ الجدول لو غير موجود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_PRECIP_CLOUD (
                date DATE,
                year INT,
                month INT,
                day INT,
                variable STRING,
                avg_value FLOAT,
                measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # batch insert للبيانات اليومية
        insert_query = """
            INSERT INTO NASA_DAILY_PRECIP_CLOUD 
            (date, year, month, day, variable, avg_value, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # نحضر البيانات للإدخال
        data_to_insert = [
            (
                row["date"], 
                int(row["year"]), 
                int(row["month"]), 
                int(row["day"]), 
                row["variable"], 
                float(row[df.columns[2]]),  # العمود الثاني هو القيمة المتوسطة
                int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        # إدخال جماعي
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise


# ==========================
# DAGSTER JOB - DAILY PRECIPITATION AND CLOUD FRACTION PIPELINE 2022
# ==========================

@job
def nasa_daily_precip_cloud_2022_pipeline():
    """
    Pipeline لمعالجة بيانات الأمطار ونسبة السحب اليومية لسنة 2022
    """
    # بحث عن الملفات لسنة 2022
    files = search_nasa_files_precip_cloud_2022()
    
    # معالجة كل ملف وحساب المتوسطات اليومية
    processed = files.map(process_single_file_precip_cloud)
    
    # تحويل البيانات اليومية
    transformed = processed.map(transform_daily_precip_cloud)
    
    # تحميل البيانات اليومية لـ Snowflake
    transformed.map(load_daily_precip_cloud_to_snowflake)
    
