from dagster import job, op, Field, Int
import io
import requests
import xarray as xr
import pandas as pd
import snowflake.connector

# ... خلي باقي الإعدادات (BASE_URL, FILE_TEMPLATE, etc) زي ما هم ...

@op(config_schema={
    "year": Field(Int, description="السنة"),
    "month": Field(Int, description="الشهر (1-12)")
})
def extract_temperature(context):
    year = context.op_config["year"]
    month = context.op_config["month"]

    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}
    all_days = []

    file_name = FILE_TEMPLATE.format(year=year, month=month)
    url = BASE_URL + f"{year}/{file_name}"
    context.log.info(f"⬇️ Fetching {url}")

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
    return df


@op
def load_temperature_to_snowflake(df: pd.DataFrame):
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


@job
def nasa_temperature_custom_pipeline():
    df = extract_temperature()
    transformed = transform_temperature(df)
    load_temperature_to_snowflake(transformed)
