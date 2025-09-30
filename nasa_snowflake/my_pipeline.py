import io
import requests
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op

# ==========================
# NASA + Snowflake Config
# ==========================
BASE_URL = "https://data.gesdisc.earthdata.nasa.gov/data/GLDAS/GLDAS_NOAH025_M.2.1/2022/"
FILE_TEMPLATE = "GLDAS_NOAH025_M.A{year}{month:02d}.021.nc4"

EARTHDATA_TOKEN = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ..."

# Snowflake Config
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_PASSWORD = "Ahmedesso@2005"
SNOWFLAKE_AUTHENTICATOR = "snowflake"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

# ==========================
# DAGSTER OPS
# ==========================
@op
def extract_temperature_daily():
    """يسحب ملفات سنة 2022 كاملة من NASA Earthdata ويحسب درجة الحرارة اليومية"""
    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}
    all_days = []

    year = 2022
    for month in range(1, 13):
        file_name = FILE_TEMPLATE.format(year=year, month=month)
        url = BASE_URL + file_name
        print(f"⬇️ Fetching {url}")

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = io.BytesIO(response.content)
        ds = xr.open_dataset(data, engine="h5netcdf")

        if "Tair_f_inst" in ds.variables:
            daily_avg = ds["Tair_f_inst"].mean(dim=["lat", "lon"]).to_dataframe()
            daily_avg.reset_index(inplace=True)

            for _, row in daily_avg.iterrows():
                all_days.append({
                    "date": row["time"].strftime("%Y-%m-%d"),
                    "avg_temperature": float(row["Tair_f_inst"])
                })

    df = pd.DataFrame(all_days)
    return df


@op
def transform_temperature(df: pd.DataFrame):
    """يرجع الـ DataFrame زي ما هو (ممكن تزود معالجات هنا)"""
    return df


@op
def load_temperature_to_snowflake(df: pd.DataFrame):
    """تحميل البيانات لـ Snowflake"""
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=SNOWFLAKE_ROLE
    )

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS DAILY_TEMPERATURE (
            date DATE,
            avg_temperature FLOAT
        )
    """)

    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO DAILY_TEMPERATURE (date, avg_temperature) VALUES (%s, %s)",
            (row["date"], float(row["avg_temperature"])),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Year 2022 daily averages loaded into Snowflake.")


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_temperature_pipeline():
    data = extract_temperature_daily()
    transformed = transform_temperature(data)
    load_temperature_to_snowflake(transformed)
