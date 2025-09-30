import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime, timedelta
import math
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

VARIABLES = ["U10M", "V10M", "PS", "SLP"]  # سرعة الرياح (مكونات x, y)، الضغط السطحي، ضغط مستوى البحر

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

def calculate_wind_speed(u_component, v_component):
    """حساب سرعة الرياح الكلية من المكونات U و V"""
    return math.sqrt(u_component**2 + v_component**2)

def calculate_wind_direction(u_component, v_component):
    """حساب اتجاه الرياح من المكونات U و V (بالدرجات)"""
    direction = math.degrees(math.atan2(u_component, v_component))
    if direction < 0:
        direction += 360
    return direction

def calculate_circular_mean(angles):
    """حساب المتوسط الدائري للزوايا (لاتجاه الرياح)"""
    sin_sum = sum(math.sin(math.radians(angle)) for angle in angles)
    cos_sum = sum(math.cos(math.radians(angle)) for angle in angles)
    
    if sin_sum == 0 and cos_sum == 0:
        return 0
    
    mean_angle = math.degrees(math.atan2(sin_sum, cos_sum))
    if mean_angle < 0:
        mean_angle += 360
    
    return mean_angle

# ==========================
# DAGSTER OPS - DAILY AVERAGE
# ==========================

@op(out=DynamicOut())
def search_nasa_wind_files(context):
    """
    بحث عن ملفات NASA للفترة المطلوبة للرياح والضغط
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA wind files...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2023-01-01"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # منطقة القاهرة
    )
    
    context.log.info(f"✅ Found {len(results)} wind files")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"wind_file_{idx}"
        )


@op
def process_single_wind_file(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسط اليومي للرياح والضغط
    """
    try:
        context.log.info(f"📥 Streaming wind file: {granule['meta']['native-id']}")
        
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        for var in VARIABLES:
            if var in ds.variables:
                context.log.info(f"📊 Processing wind variable: {var}")
                
                df = ds[[var]].to_dataframe().reset_index()
                
                if "time" not in df.columns:
                    context.log.warning("⚠️ No time column found")
                    continue
                
                df["time"] = pd.to_datetime(df["time"])
                df["date"] = df["time"].dt.date
                
                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                
                all_daily_data.append(daily_avg)
            else:
                context.log.warning(f"⚠️ Wind variable {var} not found in dataset")
        
        # معالجة خاصة لبيانات الرياح لحساب سرعة واتجاه الرياح
        if "U10M" in ds.variables and "V10M" in ds.variables:
            context.log.info("🌬️ Processing wind speed and direction...")
            
            # نجلب بيانات U و V معاً
            wind_df = ds[["U10M", "V10M"]].to_dataframe().reset_index()
            
            if "time" in wind_df.columns:
                wind_df["time"] = pd.to_datetime(wind_df["time"])
                wind_df["date"] = wind_df["time"].dt.date
                
                # نحسب سرعة الرياح واتجاهها لكل نقطة
                wind_df["WIND_SPEED"] = wind_df.apply(
                    lambda row: calculate_wind_speed(row["U10M"], row["V10M"]), 
                    axis=1
                )
                
                wind_df["WIND_DIRECTION"] = wind_df.apply(
                    lambda row: calculate_wind_direction(row["U10M"], row["V10M"]), 
                    axis=1
                )
                
                # المتوسط اليومي لسرعة الرياح
                wind_speed_daily = wind_df.groupby(["date", "lat", "lon"])["WIND_SPEED"].mean().reset_index()
                wind_speed_daily["variable"] = "WIND_SPEED"
                all_daily_data.append(wind_speed_daily)
                
                # المتوسط اليومي لاتجاه الرياح (نستخدم المتوسط الدائري)
                wind_direction_daily = wind_df.groupby(["date", "lat", "lon"]).apply(
                    lambda x: pd.Series({
                        'WIND_DIRECTION': calculate_circular_mean(x['WIND_DIRECTION'])
                    })
                ).reset_index()
                wind_direction_daily["variable"] = "WIND_DIRECTION"
                all_daily_data.append(wind_direction_daily)
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No wind variables found in file")
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily wind records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing wind file: {e}")
        return pd.DataFrame()


@op
def clean_wind_dataframe(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تنظيف بيانات الرياح والضغط وإزالة القيم NaN
    """
    if df.empty:
        return df
    
    context.log.info(f"🧹 Cleaning {len(df)} wind records...")
    
    # نسخة من البيانات للتنظيف
    cleaned_df = df.copy()
    
    # إزالة الصفوف التي تحتوي على NaN في الأعمدة الأساسية
    initial_count = len(cleaned_df)
    cleaned_df = cleaned_df.dropna(subset=['date', 'variable', 'lat', 'lon'])
    
    # استبدال NaN في الأعمدة الرقمية بصفر
    numeric_columns = cleaned_df.select_dtypes(include=['number']).columns
    for col in numeric_columns:
        nan_count = cleaned_df[col].isna().sum()
        if nan_count > 0:
            context.log.info(f"🔧 Replacing {nan_count} NaN values in {col} with 0")
            cleaned_df[col] = cleaned_df[col].fillna(0)
    
    removed_count = initial_count - len(cleaned_df)
    if removed_count > 0:
        context.log.info(f"🗑️ Removed {removed_count} wind records with missing essential data")
    
    context.log.info(f"✅ Cleaned {len(cleaned_df)} wind records")
    
    return cleaned_df


@op
def transform_wind_data(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل بيانات الرياح والضغط اليومية للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily wind records...")
    
    required_cols = ["date", "variable", "lat", "lon"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        context.log.warning(f"⚠️ Missing columns: {missing_cols}")
        return pd.DataFrame()
    
    # نحدد اسم عمود القيمة بناءً على المتغير
    value_column = [col for col in df.columns if col not in ['date', 'variable', 'lat', 'lon', 'time']][0]
    
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({
            value_column: 'mean',
            'lat': 'count'
        })
        .reset_index()
    )
    
    daily_summary.rename(columns={
        value_column: 'avg_value',
        'lat': 'measurement_count'
    }, inplace=True)
    
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    result = daily_summary[[
        "date", "year", "month", "day", "variable", 
        "avg_value", "measurement_count"
    ]]
    
    context.log.info(f"✅ Transformed to {len(result)} daily wind summary records")
    
    return result


@op
def validate_wind_data_before_load(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    فحص بيانات الرياح والضغط قبل التحميل لاكتشاف المشاكل مبكراً
    """
    if df.empty:
        context.log.warning("⚠️ Empty wind dataframe in validation")
        return df
    
    context.log.info(f"🔍 Validating {len(df)} wind records before load...")
    
    # فحص القيم NaN
    nan_check = df.isna().sum()
    total_nan = nan_check.sum()
    
    if total_nan > 0:
        context.log.warning(f"⚠️ Found {total_nan} NaN values in wind dataframe:")
        for column, count in nan_check.items():
            if count > 0:
                context.log.warning(f"   - {column}: {count} NaN values")
    
    # فحص القيم في avg_value
    if "avg_value" in df.columns:
        avg_value_stats = df["avg_value"].describe()
        context.log.info(f"📊 avg_value statistics: count={avg_value_stats['count']}, mean={avg_value_stats['mean']:.2f}")
        
        # اكتشاف القيم غير الطبيعية
        infinite_values = np.isinf(df["avg_value"]).sum()
        if infinite_values > 0:
            context.log.warning(f"⚠️ Found {infinite_values} infinite values in avg_value")
    
    # إزالة الصفوف التي تحتوي على NaN في أعمدة أساسية
    initial_count = len(df)
    essential_columns = ['date', 'variable', 'avg_value']
    cleaned_df = df.dropna(subset=essential_columns)
    removed_count = initial_count - len(cleaned_df)
    
    if removed_count > 0:
        context.log.warning(f"🗑️ Removed {removed_count} wind records with missing essential data")
    
    context.log.info(f"✅ Wind validation complete. {len(cleaned_df)} valid records remaining")
    
    return cleaned_df


@op
def load_wind_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات الرياح والضغط اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty wind dataframe - skipping load")
        return {"status": "skipped", "loaded_count": 0, "file_info": "empty"}

    context.log.info(f"📤 Preparing to load {len(df)} daily wind records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # إنشاء الجدول إذا لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_WIND_PRESSURE (
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
        
        insert_query = """
            INSERT INTO NASA_DAILY_WIND_PRESSURE 
            (date, year, month, day, variable, avg_value, measurement_count) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # تحضير البيانات مع معالجة NaN
        successful_inserts = 0
        failed_inserts = 0
        error_messages = []
        
        for index, row in df.iterrows():
            try:
                # معالجة القيم NaN
                avg_value = row["avg_value"]
                if pd.isna(avg_value) or pd.isnull(avg_value):
                    context.log.warning(f"⚠️ Found NaN value in row {index}, skipping this row")
                    failed_inserts += 1
                    continue
                
                measurement_count = row["measurement_count"]
                if pd.isna(measurement_count) or pd.isnull(measurement_count):
                    measurement_count = 0
                
                # التحقق من البيانات الأساسية
                if pd.isna(row["date"]) or pd.isna(row["variable"]):
                    context.log.warning(f"⚠️ Missing essential data in row {index}, skipping")
                    failed_inserts += 1
                    continue
                
                # إدخال الصف
                cur.execute(insert_query, (
                    row["date"], 
                    int(row["year"]), 
                    int(row["month"]), 
                    int(row["day"]), 
                    row["variable"], 
                    float(avg_value),
                    int(measurement_count)
                ))
                successful_inserts += 1
                
            except Exception as row_error:
                failed_inserts += 1
                error_msg = f"Error in row {index}: {str(row_error)}"
                error_messages.append(error_msg)
                context.log.warning(f"⚠️ {error_msg}")
                continue  # استمرار مع الصفوف التالية
        
        conn.commit()
        
        # تسجيل النتائج
        if successful_inserts > 0:
            context.log.info(f"✅ Successfully loaded {successful_inserts} daily wind records")
        
        if failed_inserts > 0:
            context.log.warning(f"⚠️ Failed to load {failed_inserts} wind records due to errors")
        
        if error_messages:
            context.log.info("📋 Wind error summary:")
            for msg in error_messages[:5]:  # اطبع أول 5 أخطاء فقط
                context.log.info(f"   - {msg}")
            if len(error_messages) > 5:
                context.log.info(f"   ... and {len(error_messages) - 5} more errors")
        
        cur.close()
        conn.close()
        
        return {
            "status": "partial_success" if failed_inserts > 0 else "success",
            "loaded_count": successful_inserts,
            "failed_count": failed_inserts,
            "total_records": len(df)
        }
        
    except Exception as e:
        context.log.error(f"❌ Critical error loading wind data to Snowflake: {e}")
        return {
            "status": "failed",
            "loaded_count": 0,
            "failed_count": len(df),
            "error": str(e)
        }


@job
def nasa_daily_wind_pipeline():
    """
    Pipeline لمعالجة بيانات الرياح والضغط اليومية
    """
    files = search_nasa_wind_files()
    processed = files.map(process_single_wind_file)
    cleaned = processed.map(clean_wind_dataframe)
    transformed = cleaned.map(transform_wind_data)
    validated = transformed.map(validate_wind_data_before_load)
    validated.map(load_wind_to_snowflake)


if __name__ == "__main__":
    from dagster import execute_pipeline
    result = execute_pipeline(nasa_daily_wind_pipeline)
    print(f"✅ Wind pipeline finished: {result.success}")
