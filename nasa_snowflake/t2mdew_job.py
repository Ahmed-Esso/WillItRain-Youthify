# jobs/core_weather/t2mdew_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "T2MDEW"
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut(), name="search_files_t2mdew")
def search_files_t2mdew(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE}")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_t2mdew")
def process_file_t2mdew(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # Debug: show all available variables
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE not in ds:
            context.log.warning(f"Variable {VARIABLE} not found. Available: {available_vars}")
            
            # Try common alternative names for dew point
            alternatives = ["T2M_DEW", "DEWPT", "DEWP", "TD2M", "D2M"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    # Use the alternative variable
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 30.8) & (df.lat <= 31.3) &
                        (df.lon >= 29.5) & (df.lon <= 31.5)
                    ]
                    # Convert from Kelvin to Celsius if needed
                    df[alt_var] = df[alt_var] - 273.15
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: VARIABLE})
            
            return pd.DataFrame()
        
        # If T2MDEW is found, process normally
        df = ds[[VARIABLE]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        
        # Convert from Kelvin to Celsius
        df[VARIABLE] = df[VARIABLE] - 273.15
            
        ds.close()
        return df[["time", VARIABLE]]
    except Exception as e:
        context.log.error(f"Error processing T2MDEW file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_t2mdew")
def transform_daily_t2mdew(context, df):
    if df.empty: 
        context.log.info("No data to transform for T2MDEW")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE}")
    return result

@op(name="load_to_snowflake_t2mdew")
def load_to_snowflake_t2mdew(context, df):
    if df.empty: 
        context.log.info("No T2MDEW data to load")
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
        context.log.info(f"Successfully loaded {len(rows)} T2MDEW rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading T2MDEW data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def t2mdew_job():
    files = search_files_t2mdew()
    processed = files.map(process_file_t2mdew)
    transformed = processed.map(transform_daily_t2mdew)
    transformed.map(load_to_snowflake_t2mdew)
