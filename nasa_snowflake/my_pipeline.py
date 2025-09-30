# nasa_snowflake/my_pipeline.py

import os
import pandas as pd
import xarray as xr
import earthaccess
from dagster import op, job, Out

# المتغيرات اللي عايزة تشتغلي عليها
VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

# بيانات Snowflake من الـ Environment Variables
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")

# ---- Step 1: Extract ----
@op(out=Out(pd.DataFrame))
def extract_variables() -> pd.DataFrame:
    # البحث في NASA Earthdata
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",   # dataset الخاص بـ MERRA-2
        temporal=("2020-01-01", "2020-01-31"),  # سنة واحدة كاختبار
        bounding_box=(-10, 20, 10, 30)  # مثال: شمال أفريقيا
    )

    datasets = []
    for granule in results:
        with earthaccess.open(granule) as f:
            ds = xr.open_dataset(f)
            # ناخد المتغيرات اللي احنا محددنها
            df = ds[VARIABLES].to_dataframe().reset_index()
            datasets.append(df)

    if not datasets:
        raise ValueError("No data returned from NASA search")

    final_df = pd.concat(datasets, ignore_index=True)
    return final_df


# ---- Step 2: Load to Snowflake ----
@op
def load_to_snowflake(df: pd.DataFrame):
    import snowflake.connector

    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )

    cur = conn.cursor()

    # إنشاء جدول لو مش موجود
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS nasa_weather_data (
            time TIMESTAMP,
            lat FLOAT,
            lon FLOAT,
            {", ".join([f"{var} FLOAT" for var in VARIABLES])}
        )
    """)

    # إدخال البيانات
    for _, row in df.iterrows():
        cur.execute(
            f"""
            INSERT INTO nasa_weather_data (time, lat, lon, {", ".join(VARIABLES)})
            VALUES (%s, %s, %s, {", ".join(['%s']*len(VARIABLES))})
            """,
            [row["time"], row["lat"], row["lon"]] + [row[var] for var in VARIABLES],
        )

    conn.commit()
    cur.close()
    conn.close()


# ---- Step 3: Define Pipeline ----
@job
def nasa_variables_pipeline():
    df = extract_variables()
    load_to_snowflake(df)
