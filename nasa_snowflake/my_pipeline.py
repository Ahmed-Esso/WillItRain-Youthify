import io
import requests
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op

# ==========================
# NASA + Snowflake Config
# ==========================
BASE_URL = "https://data.gesdisc.earthdata.nasa.gov/data/GLDAS/GLDAS_NOAH025_M.2.1/"
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
def extract_temperature(year: int, month: int):
    """يسحب ملف شهر وسنة محددين من NASA Earthdata ويحسب متوسط درجة الحرارة اليومية"""
    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}
    all_days = []

    file_name = FILE_TEMPLATE.format(year=year, month=month)
    url = BASE_URL + f"{year}/{file_name}"
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
                "avg_temperature": float(row["Tair_f_inst"]),
                "month": month,
                "year": year
            })

    df = pd.DataFrame(all_days)
    return df


@op
def transform_temperature(df: pd.DataFrame):
    """يرجع الـ DataFrame كما هو (ممكن تضيف معالجات هنا)"""
    return df


@op
def load_temperature_to_snowflake(df: pd.DataFrame):
    """تحميل بيانات الشهر والسنة لـ Snowflake"""
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
        CREATE TABLE IF NOT EXISTS MONTHLY_TEMPERATURE (
            date DATE,
            avg_temperature FLOAT,
            month INT,
            year INT
        )
    """)

    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO MONTHLY_TEMPERATURE (date, avg_temperature, month, year) VALUES (%s, %s, %s, %s)",
            (row["date"], float(row["avg_temperature"]), row["month"], row["year"]),
        )

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ بيانات الشهر {df['month'].iloc[0]} من سنة {df['year'].iloc[0]} تم تحميلها إلى Snowflake.")


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_temperature_custom_pipeline():
    year = 2022  # ممكن تغيّريه لأي سنة
    month = 3    # ممكن تغيّريه لأي شهر (1-12)

    data = extract_temperature(year, month)
    transformed = transform_temperature(data)
    load_temperature_to_snowflake(transformed)
