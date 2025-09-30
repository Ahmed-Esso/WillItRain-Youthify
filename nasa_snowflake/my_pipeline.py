import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op
import earthaccess
import os

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

# ✅ المتغير اللي هنركز عليه (درجة الحرارة عند 2 متر)
VARIABLE = "T2M"

# ==========================
# SINGLE DAGSTER OP
# ==========================
@op
def etl_temperature_only():
    all_data = []

    # ✅ Login to NASA Earthdata using environment variables
    auth = earthaccess.login(strategy="environment")

    # Search NASA dataset
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2023-01-01"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # القاهرة
    )

    print(f"Found {len(results)} files.")

    files = earthaccess.download(results, "./data")

    for file in files:
        ds = xr.open_dataset(file, engine="h5netcdf")

        if VARIABLE in ds.variables:
            df = ds[VARIABLE].to_dataframe().reset_index()
            df["variable"] = VARIABLE
            df["timestamp"] = pd.to_datetime(ds.time.values[0])
            all_data.append(df)

    if not all_data:
        raise ValueError("No temperature data found. Check search parameters!")

    # ========= Transform =========
    combined_df = pd.concat(all_data, ignore_index=True)
    transformed = (
        combined_df.groupby([combined_df["timestamp"].dt.month])
        .mean(numeric_only=True)
        .reset_index()
    )
    transformed.rename(columns={"timestamp": "month"}, inplace=True)
    transformed["month"] = transformed["month"].astype(int)
    transformed["avg_temp"] = transformed.iloc[:, 1]
    final_df = transformed[["month", "avg_temp"]]

    # ========= Load to Snowflake =========
    try:
        conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            authenticator=SNOWFLAKE_AUTHENTICATOR,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA,
            role=SNOWFLAKE_ROLE
        )

        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_TEMPERATURE (
                month INT,
                avg_temp FLOAT
            )
        """)

        for _, row in final_df.iterrows():
            cur.execute(
                "INSERT INTO NASA_TEMPERATURE (month, avg_temp) VALUES (%s, %s)",
                (int(row["month"]), float(row["avg_temp"]))
            )

        conn.commit()
        print("✅ Temperature data loaded successfully into Snowflake.")

    except Exception as e:
        print(f"Error loading to Snowflake: {e}")
    finally:
        cur.close()
        conn.close()


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_temperature_pipeline():
    etl_temperature_only()
