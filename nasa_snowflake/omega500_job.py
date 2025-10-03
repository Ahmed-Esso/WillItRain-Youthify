# jobs/core_weather/omega500_job.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "OMEGA500"
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

@op(out=DynamicOut(), name="search_files_omega500")
def search_files_omega500(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE}")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_omega500")
def process_file_omega500(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # Debug: show all available variables and levels
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if 'OMEGA' not in ds:
            context.log.warning(f"OMEGA variable not found. Available: {available_vars}")
            return pd.DataFrame()
        
        # Check available pressure levels
        pressure_coord = None
        pressure_levels = None
        
        # Check different possible coordinate names for pressure
        for coord_name in ['lev', 'plev', 'pressure', 'level']:
            if coord_name in ds.coords:
                pressure_coord = coord_name
                pressure_levels = ds[coord_name].values
                context.log.info(f"Found pressure coordinate '{coord_name}': {pressure_levels}")
                break
        
        if pressure_levels is None:
            context.log.warning("No pressure levels found in dataset")
            return pd.DataFrame()
        
        # Find available pressure levels
        target_level_pa = 50000  # 500 hPa in Pa
        target_level_hpa = 500   # 500 hPa
        
        # Check if levels are in Pa or hPa
        if pressure_levels.max() > 10000:  # Likely in Pa
            available_levels = [lev for lev in pressure_levels if 30000 <= lev <= 70000]
            context.log.info(f"Looking for levels near 50000 Pa. Available: {available_levels}")
        else:  # Likely in hPa
            available_levels = [lev for lev in pressure_levels if 300 <= lev <= 700]
            context.log.info(f"Looking for levels near 500 hPa. Available: {available_levels}")
        
        if available_levels:
            if pressure_levels.max() > 10000:  # Pa
                closest_level = min(available_levels, key=lambda x: abs(x - target_level_pa))
                context.log.info(f"Selected pressure level: {closest_level} Pa (closest to 500 hPa)")
            else:  # hPa
                closest_level = min(available_levels, key=lambda x: abs(x - target_level_hpa))
                context.log.info(f"Selected pressure level: {closest_level} hPa (closest to 500 hPa)")
            
            # Select OMEGA data at the closest level
            ds_omega = ds[['OMEGA']].sel({pressure_coord: closest_level})
            df = ds_omega.to_dataframe().reset_index()
            
        else:
            # If no levels near 500 hPa, use the highest available level
            highest_level = pressure_levels.min() if pressure_levels.max() > 10000 else pressure_levels.max()
            context.log.warning(f"No levels near 500 hPa found. Using highest level: {highest_level}")
            
            ds_omega = ds[['OMEGA']].sel({pressure_coord: highest_level})
            df = ds_omega.to_dataframe().reset_index()
                
        # Filter by bounding box
        df = df[
            (df.lat >= 30.8) & (df.lat <= 31.3) &
            (df.lon >= 29.5) & (df.lon <= 31.5)
        ]
        
        # Rename OMEGA to OMEGA500
        df = df.rename(columns={'OMEGA': VARIABLE})
        
        ds.close()
        context.log.info(f"Processed {len(df)} OMEGA500 data points")
        return df[["time", VARIABLE]]
        
    except Exception as e:
        context.log.error(f"Error processing OMEGA500 file: {e}")
        return pd.DataFrame()

# باقي الكود بدون تغيير...
@op(name="transform_daily_omega500")
def transform_daily_omega500(context, df):
    if df.empty: 
        context.log.info("No data to transform for OMEGA500")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE}")
    return result

@op(name="load_to_snowflake_omega500")
def load_to_snowflake_omega500(context, df):
    if df.empty: 
        context.log.info("No OMEGA500 data to load")
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
        context.log.info(f"Successfully loaded {len(rows)} OMEGA500 rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading OMEGA500 data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def omega500_job():
    files = search_files_omega500()
    processed = files.map(process_file_omega500)
    transformed = processed.map(transform_daily_omega500)
    transformed.map(load_to_snowflake_omega500)
