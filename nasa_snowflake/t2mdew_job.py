# jobs/core_weather/t2mdew_job.py
import pandas as pd
import numpy as np
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

VARIABLE = "T2MDEW"
DATASET = VARIABLE_TO_DATASET[VARIABLE]

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

def calculate_dew_point(temperature_k, specific_humidity):
    """
    Calculate dew point temperature from temperature and specific humidity
    
    Parameters:
    temperature_k: Temperature in Kelvin
    specific_humidity: Specific humidity in kg/kg
    
    Returns:
    dew_point: Dew point temperature in Celsius
    """
    # Convert temperature to Celsius
    temperature_c = temperature_k - 273.15
    
    # Calculate vapor pressure from specific humidity
    # Using approximation: e = (q * P) / (0.622 + 0.378 * q)
    # Assuming standard surface pressure ~101325 Pa
    P = 101325  # Pa
    e = (specific_humidity * P) / (0.622 + 0.378 * specific_humidity)
    
    # Calculate dew point using Magnus formula
    # Td = (243.5 * ln(e/6.112)) / (17.67 - ln(e/6.112))
    a = 17.27
    b = 237.7
    
    # Avoid division by zero and log of zero
    e = np.maximum(e, 0.001)
    term = np.log(e / 610.78)
    dew_point = (b * term) / (a - term)
    
    return dew_point

@op(out=DynamicOut(), name="search_files_t2mdew")
def search_files_t2mdew(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEX_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for dew point calculation")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_t2mdew")
def process_file_t2mdew(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        # Check if we have both T2M and QV2M
        if 'T2M' not in ds or 'QV2M' not in ds:
            context.log.warning("T2M or QV2M not found for dew point calculation")
            return pd.DataFrame()
        
        # Extract both temperature and specific humidity
        df_temp = ds[['T2M']].to_dataframe().reset_index()
        df_humidity = ds[['QV2M']].to_dataframe().reset_index()
        
        # Filter by bounding box
        df_temp = df_temp[
            (df_temp.lat >= 30.8) & (df_temp.lat <= 31.3) &
            (df_temp.lon >= 29.5) & (df_temp.lon <= 31.5)
        ]
        df_humidity = df_humidity[
            (df_humidity.lat >= 30.8) & (df_humidity.lat <= 31.3) &
            (df_humidity.lon >= 29.5) & (df_humidity.lon <= 31.5)
        ]
        
        # Merge the dataframes
        df = pd.merge(df_temp, df_humidity, on=['time', 'lat', 'lon'])
        
        # Calculate dew point temperature
        df[VARIABLE] = calculate_dew_point(df['T2M'], df['QV2M'])
        
        ds.close()
        
        context.log.info(f"Calculated dew point for {len(df)} data points")
        return df[["time", VARIABLE]]
        
    except Exception as e:
        context.log.error(f"Error processing file for dew point calculation: {e}")
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
