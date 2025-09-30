import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, Out, Output
import earthaccess

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

VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

# ==========================
# DAGSTER OPS
# ==========================
@op(out=Out(pd.DataFrame))
def extract_variables():
    all_data = []

    # ✅ Login to NASA Earthdata using env vars
    earthaccess.login(strategy="environment")

    # Search dataset
    results = earthaccess.search_data(
        short_name="M2T1NXSLV",
        version="5.12.4",
        temporal=("2022-01-01", "2023-01-01"),
        bounding_box=(24.70, 22.00, 37.35, 31.67)  # القاهرة
    )

    print(f"Found {len(results)} files.")

    # ✅ Open datasets as HTTPFile objects
    files = earthaccess.open(results)

    for f in files:
        # نفتح الـ HTTPFile بـ xarray
        with xr.open_dataset(f, engine="h5netcdf") as ds:
            for var in VARIABLES:
                if var in ds.variables:
                    df = ds[var].to_dataframe().reset_index()
                    df["variable"] = var
                    df["timestamp"] = pd.to_datetime(ds.time.values[0])
                    all_data.append(df)

    if not all_data:
        raise ValueError("No data found. Check search parameters!")

    combined_df = pd.concat(all_data, ignore_index=True)

    return Output(combined_df, "result")


@op(out=Out(pd.DataFrame))
def transform_variables(df: pd.DataFrame):
    transformed = (
        df.groupby(["variable", df["timestamp"].dt.month])
        .mean(numeric_only=True)
        .reset_index()
    )
    transformed.rename(columns={"timestamp": "month"}, inplace=True)
    transformed["month"] = transformed["month"].astype(int)
    transformed["avg_value"] = transformed.iloc[:, 2]
    final = transformed[["variable", "month", "avg_value"]]

    return Output(final, "result")


@op
def load_variables_to_snowflake(df: pd.DataFrame):
    conn = None
    cur = None
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
            CREATE TABLE IF NOT EXISTS NASA_VARIABLES (
                variable STRING,
                month INT,
                avg_value FLOAT
            )
        """)

        rows = df.to_records(index=False).tolist()
        insert_sql = "INSERT INTO NASA_VARIABLES (variable, month, avg_value) VALUES (%s, %s, %s)"
        cur.executemany(insert_sql, rows)

        conn.commit()
        print(f"Inserted {len(rows)} rows into NASA_VARIABLES ✅")

    except Exception as e:
        print(f"❌ Error loading to Snowflake: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_variables_pipeline():
    data = extract_variables()
    transformed = transform_variables(data)
    load_variables_to_snowflake(transformed)
