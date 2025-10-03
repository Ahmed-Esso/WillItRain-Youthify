# jobs/core_weather/alexandria_jobs.py
import pandas as pd
import snowflake.connector
import xarray as xr
import earthaccess
from dagster import job, op, DynamicOut, DynamicOutput
from config import SNOWFLAKE_CONFIG, ALEX_BOUNDING_BOX, VARIABLE_TO_DATASET, THERMAL_VARS

# إحداثيات الإسكندرية
ALEXANDRIA_BOUNDING_BOX = (29.5, 31.0, 30.0, 31.5)  # min_lon, min_lat, max_lon, max_lat

def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

# ==========================
# TQL Job for Alexandria
# ==========================
VARIABLE_TQL = "TQL"
DATASET_TQL = VARIABLE_TO_DATASET[VARIABLE_TQL]

@op(out=DynamicOut(), name="search_files_tql_alex")
def search_files_tql_alex(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET_TQL,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEXANDRIA_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE_TQL} in Alexandria")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_tql_alex")
def process_file_tql_alex(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE_TQL not in ds:
            context.log.warning(f"Variable {VARIABLE_TQL} not found. Available: {available_vars}")
            alternatives = ["LWP", "LIQUID_WATER_PATH", "QL", "CLDLIQ"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 31.0) & (df.lat <= 31.5) &
                        (df.lon >= 29.5) & (df.lon <= 30.0)
                    ]
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: VARIABLE_TQL})
            return pd.DataFrame()
        
        df = ds[[VARIABLE_TQL]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 31.0) & (df.lat <= 31.5) &
            (df.lon >= 29.5) & (df.lon <= 30.0)
        ]
        
        ds.close()
        context.log.info(f"Processed {len(df)} {VARIABLE_TQL} data points for Alexandria")
        return df[["time", VARIABLE_TQL]]
    except Exception as e:
        context.log.error(f"Error processing {VARIABLE_TQL} file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_tql_alex")
def transform_daily_tql_alex(context, df):
    if df.empty: 
        context.log.info("No data to transform for TQL in Alexandria")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE_TQL: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE_TQL
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE_TQL} in Alexandria")
    return result

@op(name="load_to_snowflake_tql_alex")
def load_to_snowflake_tql_alex(context, df):
    if df.empty: 
        context.log.info("No TQL data to load for Alexandria")
        return
    
    table_name = f"NASA_{VARIABLE_TQL}_ALEX"
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
        context.log.info(f"Successfully loaded {len(rows)} {VARIABLE_TQL} rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading {VARIABLE_TQL} data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def tql_alex_job():
    files = search_files_tql_alex()
    processed = files.map(process_file_tql_alex)
    transformed = processed.map(transform_daily_tql_alex)
    transformed.map(load_to_snowflake_tql_alex)

# ==========================
# TQI Job for Alexandria
# ==========================
VARIABLE_TQI = "TQI"
DATASET_TQI = VARIABLE_TO_DATASET[VARIABLE_TQI]

@op(out=DynamicOut(), name="search_files_tqi_alex")
def search_files_tqi_alex(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET_TQI,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEXANDRIA_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE_TQI} in Alexandria")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_tqi_alex")
def process_file_tqi_alex(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE_TQI not in ds:
            context.log.warning(f"Variable {VARIABLE_TQI} not found. Available: {available_vars}")
            alternatives = ["IWP", "ICE_WATER_PATH", "QI", "CLDICE"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 31.0) & (df.lat <= 31.5) &
                        (df.lon >= 29.5) & (df.lon <= 30.0)
                    ]
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: VARIABLE_TQI})
            return pd.DataFrame()
        
        df = ds[[VARIABLE_TQI]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 31.0) & (df.lat <= 31.5) &
            (df.lon >= 29.5) & (df.lon <= 30.0)
        ]
        
        ds.close()
        context.log.info(f"Processed {len(df)} {VARIABLE_TQI} data points for Alexandria")
        return df[["time", VARIABLE_TQI]]
    except Exception as e:
        context.log.error(f"Error processing {VARIABLE_TQI} file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_tqi_alex")
def transform_daily_tqi_alex(context, df):
    if df.empty: 
        context.log.info("No data to transform for TQI in Alexandria")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE_TQI: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE_TQI
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE_TQI} in Alexandria")
    return result

@op(name="load_to_snowflake_tqi_alex")
def load_to_snowflake_tqi_alex(context, df):
    if df.empty: 
        context.log.info("No TQI data to load for Alexandria")
        return
    
    table_name = f"NASA_{VARIABLE_TQI}_ALEX"
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
        context.log.info(f"Successfully loaded {len(rows)} {VARIABLE_TQI} rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading {VARIABLE_TQI} data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def tqi_alex_job():
    files = search_files_tqi_alex()
    processed = files.map(process_file_tqi_alex)
    transformed = processed.map(transform_daily_tqi_alex)
    transformed.map(load_to_snowflake_tqi_alex)

# ==========================
# T2MWET Job for Alexandria
# ==========================
VARIABLE_T2MWET = "T2MWET"
DATASET_T2MWET = VARIABLE_TO_DATASET[VARIABLE_T2MWET]

@op(out=DynamicOut(), name="search_files_t2mwet_alex")
def search_files_t2mwet_alex(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET_T2MWET,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEXANDRIA_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE_T2MWET} in Alexandria")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_t2mwet_alex")
def process_file_t2mwet_alex(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE_T2MWET not in ds:
            context.log.warning(f"Variable {VARIABLE_T2MWET} not found. Available: {available_vars}")
            alternatives = ["WET_BULB_TEMP", "WET_TEMP", "TW"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 31.0) & (df.lat <= 31.5) &
                        (df.lon >= 29.5) & (df.lon <= 30.0)
                    ]
                    # Convert from Kelvin to Celsius if needed
                    if df[alt_var].max() > 200:  # Likely in Kelvin
                        df[alt_var] = df[alt_var] - 273.15
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: VARIABLE_T2MWET})
            return pd.DataFrame()
        
        df = ds[[VARIABLE_T2MWET]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 31.0) & (df.lat <= 31.5) &
            (df.lon >= 29.5) & (df.lon <= 30.0)
        ]
        
        # Convert from Kelvin to Celsius if needed
        if df[VARIABLE_T2MWET].max() > 200:  # Likely in Kelvin
            df[VARIABLE_T2MWET] = df[VARIABLE_T2MWET] - 273.15
        
        ds.close()
        context.log.info(f"Processed {len(df)} {VARIABLE_T2MWET} data points for Alexandria")
        return df[["time", VARIABLE_T2MWET]]
    except Exception as e:
        context.log.error(f"Error processing {VARIABLE_T2MWET} file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_t2mwet_alex")
def transform_daily_t2mwet_alex(context, df):
    if df.empty: 
        context.log.info("No data to transform for T2MWET in Alexandria")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE_T2MWET: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE_T2MWET
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE_T2MWET} in Alexandria")
    return result

@op(name="load_to_snowflake_t2mwet_alex")
def load_to_snowflake_t2mwet_alex(context, df):
    if df.empty: 
        context.log.info("No T2MWET data to load for Alexandria")
        return
    
    table_name = f"NASA_{VARIABLE_T2MWET}_ALEX"
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
        context.log.info(f"Successfully loaded {len(rows)} {VARIABLE_T2MWET} rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading {VARIABLE_T2MWET} data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def t2mwet_alex_job():
    files = search_files_t2mwet_alex()
    processed = files.map(process_file_t2mwet_alex)
    transformed = processed.map(transform_daily_t2mwet_alex)
    transformed.map(load_to_snowflake_t2mwet_alex)

# ==========================
# T2MDEW Job for Alexandria
# ==========================
VARIABLE_T2MDEW = "T2MDEW"
DATASET_T2MDEW = VARIABLE_TO_DATASET[VARIABLE_T2MDEW]

@op(out=DynamicOut(), name="search_files_t2mdew_alex")
def search_files_t2mdew_alex(context):
    auth = earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=DATASET_T2MDEW,
        temporal=("2022-01-01", "2022-12-31"),
        bounding_box=ALEXANDRIA_BOUNDING_BOX
    )
    context.log.info(f"Found {len(results)} files for {VARIABLE_T2MDEW} in Alexandria")
    for i, g in enumerate(results):
        yield DynamicOutput(g, mapping_key=f"file_{i}")

@op(name="process_file_t2mdew_alex")
def process_file_t2mdew_alex(context, granule):
    try:
        stream = earthaccess.open([granule])[0]
        ds = xr.open_dataset(stream, engine="h5netcdf")
        
        available_vars = list(ds.data_vars.keys())
        context.log.info(f"Available variables in file: {available_vars}")
        
        if VARIABLE_T2MDEW not in ds:
            context.log.warning(f"Variable {VARIABLE_T2MDEW} not found. Available: {available_vars}")
            alternatives = ["DEWPOINT", "DEW_POINT", "TD", "T2M_DEW"]
            for alt_var in alternatives:
                if alt_var in ds:
                    context.log.info(f"Found alternative variable: {alt_var}")
                    df = ds[[alt_var]].to_dataframe().reset_index()
                    df = df[
                        (df.lat >= 31.0) & (df.lat <= 31.5) &
                        (df.lon >= 29.5) & (df.lon <= 30.0)
                    ]
                    # Convert from Kelvin to Celsius if needed
                    if df[alt_var].max() > 200:  # Likely in Kelvin
                        df[alt_var] = df[alt_var] - 273.15
                    ds.close()
                    return df[["time", alt_var]].rename(columns={alt_var: VARIABLE_T2MDEW})
            return pd.DataFrame()
        
        df = ds[[VARIABLE_T2MDEW]].to_dataframe().reset_index()
        df = df[
            (df.lat >= 31.0) & (df.lat <= 31.5) &
            (df.lon >= 29.5) & (df.lon <= 30.0)
        ]
        
        # Convert from Kelvin to Celsius if needed
        if df[VARIABLE_T2MDEW].max() > 200:  # Likely in Kelvin
            df[VARIABLE_T2MDEW] = df[VARIABLE_T2MDEW] - 273.15
        
        ds.close()
        context.log.info(f"Processed {len(df)} {VARIABLE_T2MDEW} data points for Alexandria")
        return df[["time", VARIABLE_T2MDEW]]
    except Exception as e:
        context.log.error(f"Error processing {VARIABLE_T2MDEW} file: {e}")
        return pd.DataFrame()

@op(name="transform_daily_t2mdew_alex")
def transform_daily_t2mdew_alex(context, df):
    if df.empty: 
        context.log.info("No data to transform for T2MDEW in Alexandria")
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg_dict = {VARIABLE_T2MDEW: ["mean", "min", "max", "std", "count"]}
    result = df.groupby("date").agg(agg_dict).reset_index()
    
    result.columns = ["date", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]
    result["variable"] = VARIABLE_T2MDEW
    
    result = result[["date", "variable", "avg_value", "min_value", "max_value", "std_value", "measurement_count"]]
    
    context.log.info(f"Transformed {len(result)} daily records for {VARIABLE_T2MDEW} in Alexandria")
    return result

@op(name="load_to_snowflake_t2mdew_alex")
def load_to_snowflake_t2mdew_alex(context, df):
    if df.empty: 
        context.log.info("No T2MDEW data to load for Alexandria")
        return
    
    table_name = f"NASA_{VARIABLE_T2MDEW}_ALEX"
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
        context.log.info(f"Successfully loaded {len(rows)} {VARIABLE_T2MDEW} rows into {table_name}")
        
    except Exception as e:
        context.log.error(f"Error loading {VARIABLE_T2MDEW} data to Snowflake: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@job
def t2mdew_alex_job():
    files = search_files_t2mdew_alex()
    processed = files.map(process_file_t2mdew_alex)
    transformed = processed.map(transform_daily_t2mdew_alex)
    transformed.map(load_to_snowflake_t2mdew_alex)
