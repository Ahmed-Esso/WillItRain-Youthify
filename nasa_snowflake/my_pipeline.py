import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput, In
import earthaccess
import os
from typing import Iterator

# ==========================
# Snowflake Config
# ==========================
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_AUTHENTICATOR = "externalbrowser"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

VARIABLES = ["T2M"]

# حجم الـ batch - قلله لو الميموري قليل
BATCH_SIZE = 50000  # rows per batch

# ==========================
# Helper Function
# ==========================
def get_snowflake_connection():
    """Create Snowflake connection"""
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=SNOWFLAKE_ROLE
    )

# ==========================
# DAGSTER OPS - STREAMING APPROACH
# ==========================

@op(out=DynamicOut())
def search_nasa_files(context):
    """
    بس بنبحث عن الملفات - مش بننزلها!
    ونرجع كل file كـ dynamic output منفصل
    """
    context.log.info("🔍 Logging into NASA Earthdata...")
    auth = earthaccess.login(strategy="environment")
    
    context.log.info("🔍 Searching for NASA files...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2023-01-01"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # القاهرة
    )
    
    context.log.info(f"✅ Found {len(results)} files")
    
    # نرجع كل file كـ dynamic output منفصل
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )


@op
def process_single_file(context, granule) -> pd.DataFrame:
    """
    معالجة ملف واحد بس - streaming من الإنترنت بدون تنزيل
    """
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        
        # بنفتح الملف مباشرة من الإنترنت بدون ما ننزله
        file_stream = earthaccess.open([granule])[0]
        
        # نفتح الـ dataset
        ds = xr.open_dataset(file_stream, engine="h5netcdf")
        
        all_vars = []
        
        # نعالج كل variable لوحده
        for var in VARIABLES:
            if var in ds.variables:
                # نحول لـ DataFrame
                df = ds[var].to_dataframe().reset_index()
                df["variable"] = var
                
                # ناخد أول timestamp من الملف
                if "time" in ds.coords:
                    df["timestamp"] = pd.to_datetime(ds.time.values[0])
                
                all_vars.append(df)
        
        ds.close()
        
        if not all_vars:
            context.log.warning(f"⚠️ No variables found in file")
            return pd.DataFrame()
        
        # نجمع الـ variables من الملف ده بس
        combined = pd.concat(all_vars, ignore_index=True)
        context.log.info(f"✅ Processed {len(combined)} rows from file")
        
        return combined
        
    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()


@op
def transform_variables(context, df: pd.DataFrame) -> pd.DataFrame:
    """
    Transformation بسيط على كل batch
    """
    if df.empty:
        return df
    
    context.log.info(f"🔄 Transforming {len(df)} rows...")
    
    # نتأكد إن timestamp موجود
    if "timestamp" not in df.columns:
        context.log.warning("⚠️ No timestamp column found")
        return pd.DataFrame()
    
    # نحسب المتوسط لكل variable ولكل شهر
    transformed = (
        df.groupby(["variable", df["timestamp"].dt.month])
        .mean(numeric_only=True)
        .reset_index()
    )
    
    transformed.rename(columns={"timestamp": "month"}, inplace=True)
    transformed["month"] = transformed["month"].astype(int)
    
    # ناخد أول عمود رقمي بعد الـ variable والـ month
    numeric_cols = transformed.select_dtypes(include=['float64', 'int64']).columns
    if len(numeric_cols) > 0:
        transformed["avg_value"] = transformed[numeric_cols[0]]
    else:
        context.log.warning("⚠️ No numeric columns found")
        return pd.DataFrame()
    
    result = transformed[["variable", "month", "avg_value"]]
    context.log.info(f"✅ Transformed to {len(result)} rows")
    
    return result


@op
def load_to_snowflake(context, df: pd.DataFrame):
    """
    تحميل batch واحد لـ Snowflake
    """
    if df.empty:
        context.log.warning("⚠️ Empty dataframe - skipping load")
        return "skipped"
    
    context.log.info(f"📤 Loading {len(df)} rows to Snowflake...")
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # نعمل الـ table لو مش موجودة (هيعمل مرة واحدة بس)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_VARIABLES (
                variable STRING,
                month INT,
                avg_value FLOAT
            )
        """)
        
        # نستخدم batch insert بدل من row-by-row (أسرع بكتير!)
        insert_query = """
            INSERT INTO NASA_VARIABLES (variable, month, avg_value) 
            VALUES (%s, %s, %s)
        """
        
        # نحضر الداتا كـ list of tuples
        data_to_insert = [
            (row["variable"], int(row["month"]), float(row["avg_value"]))
            for _, row in df.iterrows()
        ]
        
        # batch insert
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} rows")
        
        cur.close()
        conn.close()
        
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        raise


# ==========================
# DAGSTER JOB - DYNAMIC PIPELINE
# ==========================

@job
def nasa_variables_pipeline():
    """
    Pipeline بيشتغل بطريقة dynamic:
    1. بنبحث عن الملفات
    2. كل ملف بيتعالج لوحده
    3. النتيجة بتتحول
    4. وبتترفع لـ Snowflake
    
    كل ملف مستقل - لو واحد فشل باقي الملفات تكمل
    """
    files = search_nasa_files()
    
    # كل ملف هيتعالج في op منفصل
    processed = files.map(process_single_file)
    
    # كل نتيجة هتتحول وتترفع
    transformed = processed.map(transform_variables)
    transformed.map(load_to_snowflake)
