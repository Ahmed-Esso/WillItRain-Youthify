# jobs/core_weather/qv2m_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "QV2M"
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut(), name="search_files_qv2m")
def search_files_qv2m(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_qv2m")
def process_file_qv2m(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        if VARIABLE not in ds:
            context.log.warning(f"Variable {VARIABLE} not found in dataset")
            return pd.DataFrame()
        
        df = ds[[VARIABLE]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        # QV2M doesn't need unit conversion
        ds.close()
        return df[["time", VARIABLE]]
    except Exception as e:
        context.log.error(f"Error processing QV2M file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_qv2m")
def transform_daily_qv2m(context, df):
    if df.empty: 
        context.log.info("No data to transform for QV2M")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE}")
    return result

@op(name="load_to_snowflake_qv2m")
def load_to_snowflake_qv2m(context, df):
    if df.empty: 
        context.log.info("No QV2M data to load")
        return
    
    table_name = f"NASA_{VARIABLE}_ALEX"
    conn = get_snowflake_connection()
    cur = conn.cursor()
    
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            date DATE, 
            variable STRING, 
            avg_value FLOAT, 
            min_value FLOAT,
            max_value FLOAT, 
            std_value FLOAT, 
            measurement_count INT,
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    
    rows = [tuple(r) for r in df.values]
    
    insert_query = f"""
        INSERT INTO {table_name} (date, variable, avg_value, min_value, max_value, std_value, measurement_count) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        cur.executemany(insert_query, rows)
        conn.commit()
        context.log.info(f"Successfully loaded {len(rows)} QV2M rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading QV2M data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def qv2m_job():
    files = search_files_qv2m()
    processed = files.map(process_file_qv2m)
    transformed = processed.map(transform_daily_qv2m)
    transformed.map(load_to_snowflake_qv2m)
