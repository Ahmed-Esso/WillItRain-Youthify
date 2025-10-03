# tql_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX

VARIABLE = "TQL"
DATASET = "M2T3NVCHM"  # المجموعة الصحيحة لـ TQL في MERRA-2

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut())
def search_tql_files(context):
    """البحث عن ملفات TQL في MERRA-2 لسنة 2022 للإسكندرية"""
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    for i, granule in enumerate(results):
        yield DynamicOutput(granule, mapping_key=f"file_{i}")

@op
def process_tql_file(context, granule):
    """معالجة ملف واحد واستخراج TQL للإسكندرية"""
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # التحقق من وجود المتغير
        if VARIABLE not in ds:
            context.log.warning(f"المتغير {VARIABLE} غير موجود في الملف")
            return pd.DataFrame()
        
        # تحويل لـ DataFrame وفلترة الإسكندرية
        df = ds[[VARIABLE]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        
        ds.close()
        return df[["time", VARIABLE]]
        
    except Exception as e:
        context.log.error(f"خطأ في معالجة الملف: {e}")
        return pd.DataFrame()

@op
def transform_tql_daily(context, df: pd.DataFrame):
    """حساب الإحصائيات اليومية لـ TQL"""
    if df.empty:
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    daily_stats = (
        df.groupby("date")[VARIABLE]
        .agg(
            avg_value="mean",
            min_value="min",
            max_value="max",
            std_value="std",
            measurement_count="count"
        )
        .reset_index()
    )
    daily_stats["variable"] = VARIABLE
    return daily_stats

@op
def load_tql_to_snowflake(context, df: pd.DataFrame):
    """تحميل البيانات لـ Snowflake"""
    if df.empty:
        return
    
    table_name = f"NASA_{VARIABLE}_ALEX"
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    # إنشاء الجدول
    cur.execute(f"""
        CREATE OR REPLACE TABLE {table_name} (
            date DATE,
            variable STRING,
            avg_value FLOAT,
            min_value FLOAT,
            max_value FLOAT,
            std_value FLOAT,
            measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    # ✅ ترتيب البيانات حسب أعمدة الجدول
    rows = []
    for _, row in df.iterrows():
        rows.append((
            row["date"],
            row["variable"],
            float(row["avg_value"]),
            float(row["min_value"]),
            float(row["max_value"]),
            float(row["std_value"]),
            int(row["measurement_count"])
        ))
    
    cur.executemany(
        f"INSERT INTO {table_name} (date, variable, avg_value, min_value, max_value, std_value, measurement_count) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        rows
    )
    
    conn.commit()
    cur.close()
    context.log.info(f"✅ تم تحميل {len(df)} يوم لـ TQL")

@job
def tql_job():
    """Job كامل لمعالجة TQL للإسكندرية 2022"""
    files = search_tql_files()
    processed = files.map(process_tql_file)
    transformed = processed.map(transform_tql_daily)
    transformed.map(load_tql_to_snowflake)
