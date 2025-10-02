import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import earthaccess
from datetime import datetime

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

# ==========================
# VARIABLES - غيريها حسب الحاجة
# ==========================
VARIABLES = ["PRECTOT", "CLDTOT"]  
# PRECTOT → معدل الأمطار
# CLDTOT  → نسبة الغيوم (cloud fraction)
# تقدر تحطي ["T2MDEW"] أو أي variable تاني

# ==========================
# Helper Function
# ==========================
def get_snowflake_connection():
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
# DAGSTER OPS
# ==========================

@op(out=DynamicOut())
def search_nasa_files(context):
    """بحث عن ملفات NASA لسنة 2022"""
    context.log.info("🔍 Logging into NASA Earthdata...")
    earthaccess.login(strategy="environment")

    context.log.info("🔍 Searching for NASA files for 2022...")
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",  # MERRA-2 (atmospheric single-level data)
        version="5.12.4",
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # القاهرة
    )

    context.log.info(f"✅ Found {len(results)} files for 2022")

    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )


@op
def process_single_file(context, granule) -> pd.DataFrame:
    """معالجة ملف واحد وحساب المتوسط اليومي للمتغيرات المطلوبة"""
    try:
        context.log.info(f"📥 Streaming file: {granule['meta']['native-id']}")
        file_stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(file_stream, engine="h5netcdf")

        all_daily_data = []

        for var in VARIABLES:
            if var in ds.variables:
                context.log.info(f"📊 Processing variable: {var}")
                df = ds[[var]].to_dataframe().reset_index()

                if "time" not in df.columns:
                    continue

                df["time"] = pd.to_datetime(df["time"])
                df["date"] = df["time"].dt.date

                daily_avg = df.groupby(["date", "lat", "lon"])[var].mean().reset_index()
                daily_avg["variable"] = var
                all_daily_data.append(daily_avg)

        ds.close()

        if not all_daily_data:
            context.log.warning("⚠️ No variables found in file")
            return pd.DataFrame()

        return pd.concat(all_daily_data, ignore_index=True)

    except Exception as e:
        context.log.error(f"❌ Error processing file: {e}")
        return pd.DataFrame()


@op
def transform_daily_data(context, df: pd.DataFrame) -> pd.DataFrame:
    """تحويل البيانات للتخزين في Snowflake"""
    if df.empty:
        return df

    var_col = df.columns[3]  # اسم العمود اللي فيه قيمة المتغير (PRECTOT, CLDTOT, ...)
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({var_col: "mean", "lat": "count"})
        .reset_index()
    )

    daily_summary.rename(columns={
        var_col: "avg_value",
        "lat": "measurement_count"
    }, inplace=True)

    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    daily_summary["day_of_year"] = pd.to_datetime(daily_summary["date"]).dt.dayofyear

    return daily_summary[
        ["date", "year", "month", "day", "day_of_year", "variable", "avg_value", "measurement_count"]
    ]


@op
def load_daily_to_snowflake(context, df: pd.DataFrame):
    """تحميل البيانات لـ Snowflake"""
    if df.empty:
        return "skipped"

    conn = get_snowflake_connection()
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS NASA_DAILY_DATA (
            date DATE,
            year INT,
            month INT,
            day INT,
            day_of_year INT,
            variable STRING,
            avg_value FLOAT,
            measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

    insert_query = """
        INSERT INTO NASA_DAILY_DATA 
        (date, year, month, day, day_of_year, variable, avg_value, measurement_count) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    data_to_insert = [
        (
            row["date"],
            int(row["year"]),
            int(row["month"]),
            int(row["day"]),
            int(row["day_of_year"]),
            row["variable"],
            float(row["avg_value"]),
            int(row["measurement_count"])
        )
        for _, row in df.iterrows()
    ]

    cur.executemany(insert_query, data_to_insert)
    conn.commit()
    cur.close()
    conn.close()

    context.log.info(f"✅ Loaded {len(df)} records to Snowflake")
    return "success"


# ==========================
# DAGSTER JOB
# ==========================

@job
def nasa_daily_pipeline():
    files = search_nasa_files()
    processed = files.map(process_single_file)
    transformed = processed.map(transform_daily_data)
    transformed.map(load_daily_to_snowflake)
