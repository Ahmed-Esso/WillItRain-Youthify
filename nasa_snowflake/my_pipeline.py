import io
import requests
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op

# ==========================
# NASA + Snowflake Config
# ==========================
BASE_URL = "https://data.gesdisc.earthdata.nasa.gov/data/GLDAS/GLDAS_NOAH025_M.2.1"
YEAR = "2023"

EARTHDATA_TOKEN = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6Im1heWFyMjAwNSIsImV4cCI6MTc2MzU5Njc5OSwiaWF0IjoxNzU4NDA4MjYwLCJpc3MiOiJodHRwczovL3Vycy5lYXJ0aGRhdGEubmFzYS5nb3YiLCJpZGVudGl0eV9wcm92aWRlciI6ImVkbF9vcHMiLCJhY3IiOiJlZGwiLCJhc3N1cmFuY2VfbGV2ZWwiOjN9.IzcEHuwMgdaH_VsYDkNDSRn5vKZ0WGXadtc8cOKlhskX9rcglRgNpmFQkHJeXpix_W5FHy86knW3Cpd7EFcVHXfUTHyjpE8nMjObiGUPEpX_UTHkuRZWMuLXsLpVUlBPXNc9wWWMa7DqTbaRovAnyv7GdTQw3juUpwnxv2-qZPxfU0hNlgeaj4TqroCFAo6eIzMqp1xCFii22ie9gu-bEe6NmprFA0PkKOwyMe-_pe19uCPZ07Bmp6u9BRrc5qO0G-lgICg16Cx7RO2Vx60pjpwa_FLhmO-04qR93C15flALxE40LyfjzW68tJVjIzQMk-2iq-bmnNlzrfcLpm6vzg"  # خلي التوكن هنا

# Snowflake Config
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
@op
def extract_variables():
    """يسحب بيانات متغيرات السنة كاملة"""
    all_data = []

    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}

    for month in range(1, 13):
        month_str = f"{month:02d}"
        file_url = f"{BASE_URL}/{YEAR}/GLDAS_NOAH025_M.A{YEAR}{month_str}.021.nc4"

        print(f"Fetching: {file_url}")
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()

        data = io.BytesIO(response.content)
        ds = xr.open_dataset(data, engine="h5netcdf")

        for var in VARIABLES:
            if var in ds.variables:
                df = ds[var].to_dataframe().reset_index()
                df["variable"] = var
                df["month"] = month
                all_data.append(df)

    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df


@op
def transform_variables(df: pd.DataFrame):
    """تحويل بيانات المتغيرات لحساب المتوسط لكل متغير لكل شهر"""
    transformed = df.groupby(["variable", "month"]).mean(numeric_only=True).reset_index()
    return transformed


@op
def load_variables_to_snowflake(df: pd.DataFrame):
    """تحميل البيانات لـ Snowflake"""
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        authenticator="snowflake",
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
            (row["variable"], int(row["month"]), float(row[VARIABLES[0]]))
        )

    conn.commit()
    cur.close()
    conn.close()


# ==========================
# DAGSTER JOB
# ==========================
@job
def nasa_variables_pipeline():
    data = extract_variables()
    transformed = transform_variables(data)
    load_variables_to_snowflake(transformed)
