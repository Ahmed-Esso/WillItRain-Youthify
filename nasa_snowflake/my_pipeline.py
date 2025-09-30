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

EARTHDATA_TOKEN = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6ImE3bWVkX2Vzc28iLCJleHAiOjE3NjQzNzQzOTksImlhdCI6MTc1OTE1NjcwNSwiaXNzIjoiaHR0cHM6Ly91cnMuZWFydGhkYXRhLm5hc2EuZ292IiwiaWRlbnRpdHlfcHJvdmlkZXIiOiJlZGxfb3BzIiwiYWNyIjoiZWRsIiwiYXNzdXJhbmNlX2xldmVsIjozfQ.37ornZlS0nY1ri4VPKlCpKs763OHwQi0iCFmZ_wp80i_jm_g4OoBMBO8PuzEn6bth9MiUDDO0N3VTClWwJyzr9-ohRCAhnwllaCM0PLJVr7OKQ8nZF7MjjvFXJu4CUh5IPs9ojxGrroY27o-pWRQK7LCv7gstr6xF3szQt3wL0YBrki4EABFxNzm2KetIlkyplYBpGp2HIpfofAZcTFECNIC11qE6L8KwhlTDSi4-OTRGXSOTe3Wd6Ol6QsO6RmyU9iUIbuhb-mBqSVXRxd8s8HFlKqcLHBtT4j1f4qG5P7lpB1wEYTYyAZjI3bppLkYEP6ybYj4Kaoe6moCYqMwAg"

# Snowflake Config
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_PASSWORD = "Ahmedesso@2005"  # 🔐 أضيفي الباسورد هنا
SNOWFLAKE_AUTHENTICATOR = "snowflake"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

# ==========================
# DAGSTER OPS
# ==========================
@op
def extract_temperature():
    """يسحب ملفات سنة 2022 كاملة من NASA Earthdata"""
    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}
    all_months = []

    year = 2022
    for month in range(1, 13):
        file_name = FILE_TEMPLATE.format(year=year, month=month)
        url = BASE_URL + file_name
        print(f"⬇️ Fetching {url}")

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = io.BytesIO(response.content)
        ds = xr.open_dataset(data, engine="h5netcdf")

        # ناخد المتوسط لكل شهر
        if "Tair_f_inst" in ds.variables:
            temp = ds["Tair_f_inst"].mean(dim=["lat", "lon", "time"])
            avg_val = float(temp.values)
            all_months.append({"year": year, "month": month, "avg_temperature": avg_val})

    df = pd.DataFrame(all_months)
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
        CREATE TABLE IF NOT EXISTS TEMPERATURE (
            year INT,
            month INT,
            avg_temperature FLOAT
        )
    """)

    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO TEMPERATURE (year, month, avg_temperature) VALUES (%s, %s, %s)",
            (int(row["year"]), int(row["month"]), float(row["avg_temperature"])),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Year 2022 monthly averages loaded into Snowflake.")


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_temperature_pipeline():
    data = extract_temperature()
    transformed = transform_temperature(data)
    load_temperature_to_snowflake(transformed)
