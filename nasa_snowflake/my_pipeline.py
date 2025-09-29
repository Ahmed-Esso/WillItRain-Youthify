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
YEARS = [2023, 2024]

EARTHDATA_TOKEN = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6Im1heWFyMjAwNSIsImV4cCI6MTc2MzU5Njc5OSwiaWF0IjoxNzU4NDA4MjYwLCJpc3MiOiJodHRwczovL3Vycy5lYXJ0aGRhdGEubmFzYS5nb3YiLCJpZGVudGl0eV9wcm92aWRlciI6ImVkbF9vcHMiLCJhY3IiOiJlZGwiLCJhc3N1cmFuY2VfbGV2ZWwiOjN9.IzcEHuwMgdaH_VsYDkNDSRn5vKZ0WGXadtc8cOKlhskX9rcglRgNpmFQkHJeXpix_W5FHy86knW3Cpd7EFcVHXfUTHyjpE8nMjObiGUPEpX_UTHkuRZWMuLXsLpVUlBPXNc9wWWMa7DqTbaRovAnyv7GdTQw3juUpwnxv2-qZPxfU0hNlgeaj4TqroCFAo6eIzMqp1xCFii22ie9gu-bEe6NmprFA0PkKOwyMe-_pe19uCPZ07Bmp6u9BRrc5qO0G-lgICg16Cx7RO2Vx60pjpwa_FLhmO-04qR93C15flALxE40LyfjzW68tJVjIzQMk-2iq-bmnNlzrfcLpm6vzg"

SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "MAYARHANY1999"
SNOWFLAKE_AUTHENTICATOR = "externalbrowser"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

# ==========================
# DAGSTER OPS
# ==========================
@op
def extract_gldas_data():
    headers = {"Authorization": f"Bearer {EARTHDATA_TOKEN}"}
    all_dfs = []

    for year in YEARS:
        for month in range(1, 13):
            month_str = str(month).zfill(2)
            url = f"{BASE_URL}/{year}/GLDAS_NOAH025_M.A{year}{month_str}.021.nc4"

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = io.BytesIO(response.content)
            ds = xr.open_dataset(data, engine="h5netcdf")

            vars_needed = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M",
                           "PS", "TQV", "SLP", "T2MWET"]
            ds_sel = ds[vars_needed]

            df = ds_sel.to_dataframe().reset_index()
            df["year"] = year
            df["month"] = month
            all_dfs.append(df)

    final_df = pd.concat(all_dfs, ignore_index=True)
    return final_df


@op
def load_gldas_to_snowflake(df: pd.DataFrame):
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        role=SNOWFLAKE_ROLE,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS GLDAS_DATA (
            lat FLOAT,
            lon FLOAT,
            time TIMESTAMP,
            T2M FLOAT,
            QV2M FLOAT,
            T2MDEW FLOAT,
            U10M FLOAT,
            V10M FLOAT,
            PS FLOAT,
            TQV FLOAT,
            SLP FLOAT,
            T2MWET FLOAT,
            year INT,
            month INT
        )
    """)

    insert_sql = """
        INSERT INTO GLDAS_DATA 
        (lat, lon, time, T2M, QV2M, T2MDEW, U10M, V10M, PS, TQV, SLP, T2MWET, year, month)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    batch_size = 1000
    data_tuples = [
        (
            row["lat"], row["lon"], row["time"], row["T2M"], row["QV2M"],
            row["T2MDEW"], row["U10M"], row["V10M"], row["PS"],
            row["TQV"], row["SLP"], row["T2MWET"], row["year"], row["month"]
        )
        for _, row in df.iterrows()
    ]

    for i in range(0, len(data_tuples), batch_size):
        batch = data_tuples[i:i+batch_size]
        cur.executemany(insert_sql, batch)

    conn.commit()
    cur.close()
    conn.close()

# ==========================
# DAGSTER JOBS
# ==========================
@job
def nasa_gldas_pipeline():
    data = extract_gldas_data()
    load_gldas_to_snowflake(data)

@job
def nasa_temperature_pipeline():
    data = extract_gldas_data()
    load_gldas_to_snowflake(data)
