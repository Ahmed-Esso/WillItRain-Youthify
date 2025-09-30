import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime, timedelta
import math

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
def load_wind_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات الرياح والضغط اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty wind dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily wind records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
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
        
        data_to_insert = [
            (
                row["date"], 
                int(row["year"]), 
                int(row["month"]), 
                int(row["day"]), 
                row["variable"], 
                float(row["avg_value"]), 
                int(row["measurement_count"])
            )
            for _, row in df.iterrows()
        ]
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily wind records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading wind data to Snowflake: {e}")
        raise


@job
def nasa_daily_wind_pipeline():
    """
    Pipeline لمعالجة بيانات الرياح والضغط اليومية
    """
    files = search_nasa_wind_files()
    processed = files.map(process_single_wind_file)
    transformed = processed.map(transform_wind_data)
    transformed.map(load_wind_to_snowflake)


if __name__ == "__main__":
    from dagster import execute_pipeline
    result = execute_pipeline(nasa_daily_wind_pipeline)
    print(f"✅ Wind pipeline finished: {result.success}")
