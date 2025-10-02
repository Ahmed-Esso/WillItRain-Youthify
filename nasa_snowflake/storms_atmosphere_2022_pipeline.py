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

# المتغيرات المطلوبة
VARIABLES = ["PRECTOT", "CLDTT", "SLP"]  # معدل الأمطار، الغطاء السحابي، ضغط سطح البحر

# ==========================
# Helper Functions
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

def get_rain_intensity(precipitation_mm_day):
    """تصنيف شدة الأمطار"""
    if precipitation_mm_day == 0:
        return "No Rain"
    elif precipitation_mm_day < 2.5:
        return "Light Rain"
    elif precipitation_mm_day < 7.5:
        return "Moderate Rain"
    elif precipitation_mm_day < 15:
        return "Heavy Rain"
    else:
        return "Very Heavy Rain"

def get_cloud_coverage(cloud_fraction):
    """تصنيف الغطاء السحابي"""
    if cloud_fraction < 0.1:
        return "Clear"
    elif cloud_fraction < 0.25:
        return "Few Clouds"
    elif cloud_fraction < 0.5:
        return "Scattered Clouds"
    elif cloud_fraction < 0.75:
        return "Broken Clouds"
    else:
        return "Overcast"

def get_pressure_category(pressure_hpa):
    """تصنيف ضغط سطح البحر"""
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
# DAGSTER OPS - STORMS & ATMOSPHERE DATA
# ==========================

@op(out=DynamicOut())
def search_nasa_files_storms_2022(context):
    """
    بحث عن ملفات NASA لسنة 2022 كاملة لكل مصر
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA storm/atmosphere files for 2022...")
    
    # مصر كلها - حدود جغرافية شاملة
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",  # أو استخدم dataset مناسب للعواصف
        version="5.12.4",
        temporal=("2022-01-01", "2022-02-01"),
        bounding_box=(25.0, 22.0, 37.0, 32.0)  # مصر كلها
    )
    
    context.log.info(f"✅ Found {len(results)} storm/atmosphere files for 2022")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

@op
def process_single_file_storms(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسطات اليومية للعواصف والغلاف الجوي
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # فتح الملف مباشرة من الإنترنت
        file_stream = earthaccess.open([granule])[0]
        
        # فتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        # معالجة كل متغير
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
            context.log.warning(f"⚠️ No storm/atmosphere variables found in file")
            return pd.DataFrame()
        
        # نجمع كل البيانات اليومية
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily storm/atmosphere records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()

@op
def transform_daily_storms(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل بيانات العواصف والغلاف الجوي للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily storm/atmosphere records...")
    
    # نتأكد من وجود الأعمدة المطلوبة
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # نحسب المتوسط اليومي الشامل لكل متغير
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({
            list(df.columns)[3]: 'mean',  # أول عمود بيانات
            'lat': 'count'
        })
        .reset_index()
    )
    
    # نعيد تسمية الأعمدة بناءً على المتغير
    if 'PRECTOT' in df['variable'].values:
        prec_data = daily_summary[daily_summary['variable'] == 'PRECTOT'].copy()
        prec_data.rename(columns={list(df.columns)[3]: 'avg_precipitation', 'lat': 'measurement_count'}, inplace=True)
        prec_data["precipitation_mm_day"] = prec_data["avg_precipitation"] * 86400  # تحويل من kg/m²/s إلى mm/day
        prec_data["rain_intensity"] = prec_data["precipitation_mm_day"].apply(get_rain_intensity)
    
    if 'CLDTT' in df['variable'].values:
        cloud_data = daily_summary[daily_summary['variable'] == 'CLDTT'].copy()
        cloud_data.rename(columns={list(df.columns)[3]: 'avg_cloud_fraction', 'lat': 'measurement_count'}, inplace=True)
        cloud_data["cloud_coverage"] = cloud_data["avg_cloud_fraction"].apply(get_cloud_coverage)
        cloud_data["cloud_percentage"] = cloud_data["avg_cloud_fraction"] * 100
    
    if 'SLP' in df['variable'].values:
        slp_data = daily_summary[daily_summary['variable'] == 'SLP'].copy()
        slp_data.rename(columns={list(df.columns)[3]: 'avg_sea_level_pressure', 'lat': 'measurement_count'}, inplace=True)
        slp_data["pressure_hpa"] = slp_data["avg_sea_level_pressure"] / 100.0
        slp_data["pressure_category"] = slp_data["pressure_hpa"].apply(get_pressure_category)
    
    # نجمع كل البيانات
    all_transformed = []
    if 'PRECTOT' in df['variable'].values:
        all_transformed.append(prec_data)
    if 'CLDTT' in df['variable'].values:
        all_transformed.append(cloud_data)
    if 'SLP' in df['variable'].values:
        all_transformed.append(slp_data)
    
    if not all_transformed:
        return pd.DataFrame()
    
    combined_result = pd.concat(all_transformed, ignore_index=True)
    
    # نضيف معلومات إضافية
    combined_result["year"] = pd.to_datetime(combined_result["date"]).dt.year
    combined_result["month"] = pd.to_datetime(combined_result["date"]).dt.month
    combined_result["day"] = pd.to_datetime(combined_result["date"]).dt.day
    combined_result["day_of_year"] = pd.to_datetime(combined_result["date"]).dt.dayofyear
    combined_result["day_name"] = pd.to_datetime(combined_result["date"]).dt.day_name()
    combined_result["season"] = combined_result["month"].apply(get_season)
    
    # نرتب الأعمدة بناءً على نوع المتغير
    result_columns = ["date", "year", "month", "day", "day_of_year", "day_name", "season", "variable", "measurement_count"]
    
    # نضيف أعمدة إضافية حسب المتغير
    if 'PRECTOT' in df['variable'].values:
        result_columns.extend(["avg_precipitation", "precipitation_mm_day", "rain_intensity"])
    if 'CLDTT' in df['variable'].values:
        result_columns.extend(["avg_cloud_fraction", "cloud_percentage", "cloud_coverage"])
    if 'SLP' in df['variable'].values:
        result_columns.extend(["avg_sea_level_pressure", "pressure_hpa", "pressure_category"])
    
    # نأخذ الأعمدة المتاحة فقط
    available_columns = [col for col in result_columns if col in combined_result.columns]
    result = combined_result[available_columns]
    
    context.log.info(f"✅ Transformed to {len(result)} daily storm/atmosphere summary records")
    
    return result

@op
def load_daily_storms_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات العواصف والغلاف الجوي لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily storm/atmosphere records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # ننشئ الجدول لو غير موجود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_STORMS_ATMOSPHERE (
                date DATE,
                year INT,
                month INT,
                day INT,
                day_of_year INT,
                day_name STRING,
                season STRING,
                variable STRING,
                avg_precipitation FLOAT,
                precipitation_mm_day FLOAT,
                rain_intensity STRING,
                avg_cloud_fraction FLOAT,
                cloud_percentage FLOAT,
                cloud_coverage STRING,
                avg_sea_level_pressure FLOAT,
                pressure_hpa FLOAT,
                pressure_category STRING,
                measurement_count INT,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # batch insert للبيانات اليومية
        insert_query = """
            INSERT INTO NASA_DAILY_STORMS_ATMOSPHERE 
            (date, year, month, day, day_of_year, day_name, season, variable, 
             avg_precipitation, precipitation_mm_day, rain_intensity,
             avg_cloud_fraction, cloud_percentage, cloud_coverage,
             avg_sea_level_pressure, pressure_hpa, pressure_category, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # نحضر البيانات للإدخال (مع تعويض القيم المفقودة بـ NULL)
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                row["date"], 
                int(row["year"]), 
                int(row["month"]), 
                int(row["day"]), 
                int(row["day_of_year"]),
                row["day_name"],
                row["season"],
                row["variable"], 
                float(row["avg_precipitation"]) if "avg_precipitation" in row and pd.notna(row["avg_precipitation"]) else None,
                float(row["precipitation_mm_day"]) if "precipitation_mm_day" in row and pd.notna(row["precipitation_mm_day"]) else None,
                row["rain_intensity"] if "rain_intensity" in row and pd.notna(row["rain_intensity"]) else None,
                float(row["avg_cloud_fraction"]) if "avg_cloud_fraction" in row and pd.notna(row["avg_cloud_fraction"]) else None,
                float(row["cloud_percentage"]) if "cloud_percentage" in row and pd.notna(row["cloud_percentage"]) else None,
                row["cloud_coverage"] if "cloud_coverage" in row and pd.notna(row["cloud_coverage"]) else None,
                float(row["avg_sea_level_pressure"]) if "avg_sea_level_pressure" in row and pd.notna(row["avg_sea_level_pressure"]) else None,
                float(row["pressure_hpa"]) if "pressure_hpa" in row and pd.notna(row["pressure_hpa"]) else None,
                row["pressure_category"] if "pressure_category" in row and pd.notna(row["pressure_category"]) else None,
                int(row["measurement_count"])
            ))
        
        # إدخال جماعي
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily storm/atmosphere records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise

# ==========================
# DAGSTER JOB - STORMS & ATMOSPHERE PIPELINE 2022
# ==========================

@job
def nasa_daily_storms_atmosphere_2022_pipeline():
    """
    Pipeline لمعالجة بيانات العواصف والغلاف الجوي اليومية لسنة 2022 لكل مصر
    """
    # بحث عن الملفات لسنة 2022
    files = search_nasa_files_storms_2022()
    
    # معالجة كل ملف وحساب المتوسطات اليومية
    processed = files.map(process_single_file_storms)
    
    # تحويل البيانات اليومية
    transformed = processed.map(transform_daily_storms)
    
    # تحميل البيانات اليومية لـ Snowflake
    transformed.map(load_daily_storms_to_snowflake)
