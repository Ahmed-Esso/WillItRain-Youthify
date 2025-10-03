# jobs/core_weather/t2m_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "T2M"
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut())
def search_files(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-1-7"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op
def process_file(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        if VARIABLE not in ds:
            return pd.DataFrame()
        
        df = ds[[VARIABLE]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        if VARIABLE in THERMAL_VARS:
            df[VARIABLE] = df[VARIABLE] - 273.15  # Kelvin to Celsius
        ds.close()
        return df[["time", VARIABLE]]
    except Exception as e:
        context.log.error(f"Error: {e}")
        return pd.DataFrame()

@op
def transform_daily(context, df):
    if df.empty: return pd.DataFrame()
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE
    return result

@op
def load_to_snowflake(context, df):
    if df.empty: return
    table_name = f"NASA_{VARIABLE}_ALEX"
    conn = get_snowflake_connection()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE OR REPLACE TABLE {table_name} (
            date DATE, variable STRING, avg_value FLOAT, min_value FLOAT,
            max_value FLOAT, std_value FLOAT, measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    rows = [tuple(r) for r in df.values]
    cur.executemany(
        f"INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s, DEFAULT)",
        rows
    )
    conn.commit()
    cur.close()

@job
def t2m_job():
    files = search_files()
    processed = files.map(process_file)
    transformed = processed.map(transform_daily)
    transformed.map(load_to_snowflake)
