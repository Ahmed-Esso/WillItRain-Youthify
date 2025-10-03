# jobs/core_weather/pbltop_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "PBLH"  # غير من PBLTOP إلى PBLH
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut(), name="search_files_pbltop")
def search_files_pbltop(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE}")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_pbltop")
def process_file_pbltop(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # Debug: show all available variables
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE not in ds:
            context.log.warning(f"Variable {VARIABLE} not found. Available: {available_vars}")
            
            # Try common alternative names for PBL height
            alternatives = ["HPBL", "PBL_HEIGHT", "BLH", "BOUNDARY_LAYER_HEIGHT", "PBL"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 30.8) & (df.lat <= 31.3) &
                        (df.lon >= 29.5) & (df.lon <= 31.5)
                    ]
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: "PBLTOP"})  # احتفظ باسم PBLTOP للتخزين
            
            context.log.info("No PBL height variable found, returning empty DataFrame")
            return pd.DataFrame()
        
        # If PBLH is found, process normally
        df = ds[[VARIABLE]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        
        # PBLH is planetary boundary layer height, usually in meters
        # Check if unit conversion is needed (some models use Pa)
        if df[VARIABLE].max() > 10000:  # Likely in Pa
            context.log.info("Converting PBLH from Pa to meters")
            # Approximate conversion using hypsometric equation
            surface_pressure = 101325  # Standard surface pressure in Pa
            df[VARIABLE] = ((surface_pressure - df[VARIABLE]) / 12.5)  # Rough conversion
        
        # Rename to PBLTOP for storage
        df = df.rename(columns={VARIABLE: "PBLTOP"})
        
        ds.close()
        context.log.info(f"Processed {len(df)} PBLTOP data points")
        return df[["time", "PBLTOP"]]
        
    except Exception as e:
        context.log.error(f"Error processing PBLTOP file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_pbltop")
def transform_daily_pbltop(context, df):
    if df.empty: 
        context.log.info("No data to transform for PBLTOP")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {"PBLTOP": ["mean", "min", "max", "std", "count"]}  # استخدم PBLTOP هنا
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = "PBLTOP"  # استخدم PBLTOP هنا
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for PBLTOP")
    return result

@op(name="load_to_snowflake_pbltop")
def load_to_snowflake_pbltop(context, df):
    if df.empty: 
        context.log.info("No PBLTOP data to load")
        return
    
    table_name = "NASA_PBLTOP_ALEX"  # استخدم PBLTOP هنا
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
        context.log.info(f"Successfully loaded {len(rows)} PBLTOP rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading PBLTOP data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def pbltop_job():
    files = search_files_pbltop()
    processed = files.map(process_file_pbltop)
    transformed = processed.map(transform_daily_pbltop)
    transformed.map(load_to_snowflake_pbltop)
