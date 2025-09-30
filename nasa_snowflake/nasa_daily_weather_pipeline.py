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

VARIABLES = ["QV2M", "T2MDEW", "T2MWET"]  # الرطوبة، نقطة الندى، الحرارة الرطبة

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
# DAGSTER OPS - DAILY AVERAGE
# ==========================

@op(out=DynamicOut())
def search_nasa_weather_files(context):
    """
    بحث عن ملفات NASA للفترة المطلوبة للرطوبة ودرجة الحرارة
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA weather files...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2023-01-01"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # منطقة القاهرة
    )
    
    context.log.info(f"✅ Found {len(results)} weather files")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"weather_file_{idx}"
        )


@op
def process_single_weather_file(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد وحساب المتوسط اليومي للرطوبة ودرجة الحرارة
    """
    try:
        context.log.info(f"📥 Streaming weather file: {granule['meta']['native-id']}")
        
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_daily_data = []
        
        for var in VARIABLES:
            if var in ds.variables:
                context.log.info(f"📊 Processing weather variable: {var}")
                
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
                context.log.warning(f"⚠️ Weather variable {var} not found in dataset")
        
        ds.close()
        
        if not all_daily_data:
            context.log.warning(f"⚠️ No weather variables found in file")
            return pd.DataFrame()
        
        combined = pd.concat(all_daily_data, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} daily weather records from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing weather file: {e}")
        return pd.DataFrame()


@op
def transform_weather_data(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    تحويل بيانات الرطوبة ودرجة الحرارة اليومية للتخزين في Snowflake
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} daily weather records...")
    
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
    
    context.log.info(f"✅ Transformed to {len(result)} daily weather summary records")
    
    return result


@op
def load_weather_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل بيانات الرطوبة ودرجة الحرارة اليومية لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty weather dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} daily weather records to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_DAILY_HUMIDITY_TEMPERATURE (
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
            INSERT INTO NASA_DAILY_HUMIDITY_TEMPERATURE 
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
        
        context.log.info(f"✅ Successfully loaded {len(df)} daily weather records")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading weather data to Snowflake: {e}")
        raise


@job
def nasa_daily_weather_pipeline():
    """
    Pipeline لمعالجة بيانات الرطوبة ودرجة الحرارة اليومية
    """
    files = search_nasa_weather_files()
    processed = files.map(process_single_weather_file)
    transformed = processed.map(transform_weather_data)
    transformed.map(load_weather_to_snowflake)


if __name__ == "__main__":
    from dagster import execute_pipeline
    result = execute_pipeline(nasa_daily_weather_pipeline)
    print(f"✅ Weather pipeline finished: {result.success}")
