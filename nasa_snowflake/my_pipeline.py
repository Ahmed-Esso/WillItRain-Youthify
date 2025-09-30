import pandas as pd
import xarray as xr
from dagster import op, job, Out
from datetime import datetime
import calendar
import earthaccess
import snowflake.connector  # ✅ مهم

# Variables to extract from NASA MERRA2
VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

# Snowflake credentials (حطيهم من الـ env vars أو secrets manager)
SNOWFLAKE_ACCOUNT = "<your_account>"
SNOWFLAKE_USER = "<your_user>"
SNOWFLAKE_AUTHENTICATOR = "snowflake"   # أو Okta لو بتستخدميه
SNOWFLAKE_WAREHOUSE = "<your_wh>"
SNOWFLAKE_DATABASE = "<your_db>"
SNOWFLAKE_SCHEMA = "<your_schema>"
SNOWFLAKE_ROLE = "<your_role>"

def get_month_range(year):
    """Generate list of (start_date, end_date) per month"""
    months = []
    for m in range(1, 13):
        start = datetime(year, m, 1)
        end_day = calendar.monthrange(year, m)[1]
        end = datetime(year, m, end_day)
        months.append((start, end))
    return months

@op(out=Out(pd.DataFrame))
def extract_variables(context, year: int = 2023):
    context.log.info(f"Logging in to NASA Earthdata...")
    earthaccess.login(strategy="netrc")

    dfs = []
    for (start, end) in get_month_range(year):
        context.log.info(f"Processing {start.strftime('%Y-%m')} ...")

        results = earthaccess.search_data(
            short_name="M2I1NXASM",  
            temporal=(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
            bounding_box=[-180, -90, 180, 90],  
        )

        if not results:
            context.log.warning(f"No files found for {start.strftime('%Y-%m')}")
            continue

        files = earthaccess.open(results)

        for f in files:
            ds = xr.open_dataset(f, engine="netcdf4")
            df = ds[VARIABLES].to_dataframe().reset_index()
            dfs.append(df)
            ds.close()

    if dfs:
        final_df = pd.concat(dfs, ignore_index=True)
    else:
        final_df = pd.DataFrame()

    context.log.info(f"Final dataframe shape: {final_df.shape}")
    return final_df

@op
def transform_variables(context, df: pd.DataFrame):
    context.log.info("Transforming variables...")
    # مثال: حساب المتوسط الشهري لكل متغير
    if df.empty:
        return pd.DataFrame(columns=["variable", "month", "avg_value"])

    df["month"] = df["time"].dt.month
    result = (
        df.melt(id_vars=["month"], value_vars=VARIABLES, var_name="variable", value_name="value")
        .groupby(["variable", "month"], as_index=False)["value"]
        .mean()
        .rename(columns={"value": "avg_value"})
    )
    return result

@op
def load_variables_to_snowflake(context, df: pd.DataFrame):
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

        for _, row in df.iterrows():
            cur.execute(
                "INSERT INTO NASA_VARIABLES (variable, month, avg_value) VALUES (%s, %s, %s)",
                (row["variable"], int(row["month"]), float(row["avg_value"]))
            )

        conn.commit()
        context.log.info("Data loaded successfully to Snowflake ✅")

    except Exception as e:
        context.log.error(f"Error loading to Snowflake: {e}")
    finally:
        cur.close()
        conn.close()

@job
def nasa_variables_pipeline():
    df = extract_variables()
    transformed = transform_variables(df)
    load_variables_to_snowflake(transformed)
