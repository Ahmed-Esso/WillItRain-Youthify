# my_pipeline_chlora_oceancolor.py
import io
import xarray as xr
import pandas as pd
import snowflake.connector
from dagster import job, op, DynamicOut, DynamicOutput
import requests
from datetime import datetime, timedelta
import os
from urllib.parse import urlencode

# ==========================
# Snowflake Config
# ==========================
SNOWFLAKE_ACCOUNT = "KBZQPZO-WX06551"
SNOWFLAKE_USER = "A7MEDESSO"
SNOWFLAKE_PASSWORD = "Ahmedesso@2005"
SNOWFLAKE_AUTHENTICATOR = "snowflake"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"

# ==========================
# Ocean Color Web Config
# ==========================
OCEAN_COLOR_BASE_URL = "https://oceancolor.gsfc.nasa.gov"
L3_BROWSER_URL = f"{OCEAN_COLOR_BASE_URL}/cgi/l3"

# ==========================
# Helper Functions
# ==========================
def get_snowflake_connection():
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        authenticator=SNOWFLAKE_AUTHENTICATOR,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=SNOWFLAKE_ROLE
    )

def search_oceancolor_files(period="MO", sensor="A", resolution=9, date_range=("2022-01-01", "2022-01-31")):
    """
    Search for Ocean Color Level-3 files using their API
    
    Parameters:
    - period: Time period (DAY, MO, 8D, etc.)
    - sensor: A (Aqua), T (Terra), S (SeaWiFS)
    - resolution: 9 (9km), 4 (4km), 1 (1km)
    - date_range: tuple of (start_date, end_date)
    """
    
    params = {
        'period': period,
        'sensor': sensor,
        'resolution': resolution,
        'prod': 'CHL',  # Chlorophyll
        'date1': date_range[0],
        'date2': date_range[1],
        'north': 37.0,   # Bounding box for Egypt/East Mediterranean
        'south': 22.0,
        'west': 25.0,
        'east': 37.0,
        'format': 'netcdf',
        'submit': 'Search'
    }
    
    search_url = f"{L3_BROWSER_URL}?{urlencode(params)}"
    
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        
        # Parse the response to extract file links
        file_links = []
        for line in response.text.split('\n'):
            if '.nc' in line and 'href' in line:
                # Extract the actual file URL
                start = line.find('href="') + 6
                end = line.find('"', start)
                if start > 5 and end > start:
                    file_url = line[start:end]
                    if file_url.startswith('/'):
                        file_url = f"{OCEAN_COLOR_BASE_URL}{file_url}"
                    file_links.append(file_url)
        
        return file_links
    
    except Exception as e:
        print(f"Error searching Ocean Color files: {e}")
        return []

def download_oceancolor_file(file_url, download_path="downloads"):
    """Download a NetCDF file from Ocean Color Web"""
    
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    
    filename = file_url.split('/')[-1]
    local_path = os.path.join(download_path, filename)
    
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return local_path
    
    except Exception as e:
        print(f"Error downloading file {filename}: {e}")
        return None

# ==========================
# DAGSTER OPS
# ==========================
@op(out=DynamicOut())
def search_oceancolor_chlor_a(context):
    """Search for Chlorophyll-a files from Ocean Color Web"""
    
    context.log.info("🔍 Searching Ocean Color Web for MODIS Aqua Chlorophyll files...")
    
    # Search for monthly composites for 2022
    file_urls = search_oceancolor_files(
        period="MO",  # Monthly
        sensor="A",   # Aqua
        resolution=9, # 9km resolution
        date_range=("2022-01-01", "2022-12-31")
    )
    
    context.log.info(f"✅ Found {len(file_urls)} chlor_a files")
    
    for idx, file_url in enumerate(file_urls):
        yield DynamicOutput(
            value=file_url,
            mapping_key=f"file_{idx}"
        )

@op
def download_and_process_chlor_a(context, file_url) -> pd.DataFrame:
    """Download and process a single chlorophyll file"""
    
    try:
        context.log.info(f"📥 Downloading file: {file_url}")
        
        # Download the file
        local_path = download_oceancolor_file(file_url)
        if not local_path:
            return pd.DataFrame()
        
        # Open and process the NetCDF file
        context.log.info(f"🔬 Processing file: {local_path}")
        ds = xr.open_dataset(local_path)
        
        # Extract chlorophyll data
        if "chlor_a" in ds.variables:
            # For L3m products, we get 2D arrays (lat, lon)
            chlor_data = ds["chlor_a"]
            
            # Convert to DataFrame
            df = chlor_data.to_dataframe().reset_index()
            
            # Extract date from filename or use file metadata
            filename = os.path.basename(local_path)
            # Example filename: A20220101.L3m_MO_CHL_chlor_a_9km.nc
            date_str = filename[1:9]  # Extract YYYYMMDD from filename
            file_date = datetime.strptime(date_str, "%Y%m%d").date()
            
            df["date"] = file_date
            df["variable"] = "chlor_a"
            
            # Clean up
            ds.close()
            os.remove(local_path)  # Remove downloaded file after processing
            
            context.log.info(f"✅ Processed {len(df)} chlor_a records for date {file_date}")
            return df
            
        else:
            context.log.warning(f"⚠️ chlor_a not found in file {file_url}")
            return pd.DataFrame()
        
    except Exception as e:
        context.log.error(f"❌ Error processing file {file_url}: {e}")
        return pd.DataFrame()

@op
def transform_chlor_a_data(context, df: pd.DataFrame) -> pd.DataFrame:
    """Transform chlorophyll data for Snowflake"""
    
    if df.empty:
        return df
    
    # Calculate daily statistics
    daily_stats = df.groupby(["date", "variable"]).agg({
        "chlor_a": ["mean", "count"]
    }).reset_index()
    
    # Flatten column names
    daily_stats.columns = ["date", "variable", "avg_value", "measurement_count"]
    
    # Extract date components
    daily_stats["year"] = pd.to_datetime(daily_stats["date"]).dt.year
    daily_stats["month"] = pd.to_datetime(daily_stats["date"]).dt.month
    daily_stats["day"] = pd.to_datetime(daily_stats["date"]).dt.day
    
    result = daily_stats[["date", "year", "month", "day", "variable", "avg_value", "measurement_count"]]
    
    context.log.info(f"📊 Transformed {len(result)} daily records")
    return result

@op
def load_chlor_a_to_snowflake(context, df: pd.DataFrame):
    """Load transformed data to Snowflake"""
    
    if df.empty:
        context.log.info("⏭️ No data to load")
        return "skipped"
    
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS OCEAN_COLOR_CHLOR_A (
                date DATE,
                year INT,
                month INT,
                day INT,
                variable STRING,
                avg_value FLOAT,
                measurement_count INT,
                file_source STRING,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # Prepare data for insertion
        data_to_insert = [
            (
                row["date"],
                int(row["year"]),
                int(row["month"]),
                int(row["day"]),
                row["variable"],
                float(row["avg_value"]),
                int(row["measurement_count"]),
                "OCEAN_COLOR_WEB"
            )
            for _, row in df.iterrows()
        ]
        
        # Insert data
        insert_query = """
            INSERT INTO OCEAN_COLOR_CHLOR_A 
            (date, year, month, day, variable, avg_value, measurement_count, file_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        context.log.info(f"✅ Successfully loaded {len(df)} records to Snowflake")
        return "success"
        
    except Exception as e:
        context.log.error(f"❌ Error loading to Snowflake: {e}")
        return "failed"
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# ==========================
# DAGSTER JOB
# ==========================
@job
def ocean_color_chlor_a_pipeline():
    """Main pipeline for Ocean Color Web chlorophyll data"""
    
    # Search for files
    file_urls = search_oceancolor_chlor_a()
    
    # Download and process each file
    processed_data = file_urls.map(download_and_process_chlor_a)
    
    # Transform data
    transformed_data = processed_data.map(transform_chlor_a_data)
    
    # Load to Snowflake
    transformed_data.map(load_chlor_a_to_snowflake)

# ==========================
# Alternative: NOAA CoastWatch Version
# ==========================
def search_noaa_coastwatch_files():
    """
    Alternative method using NOAA CoastWatch
    CoastWatch provides simpler access to the same NASA data
    """
    # NOAA CoastWatch ERDDAP server
    base_url = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"
    
    # Example for MODIS Aqua Chlorophyll
    dataset_id = "erdMH1chla1day"  # Daily chlorophyll
    
    # You would construct the query based on ERDDAP's RESTful API
    # This is a simplified example
    pass

if __name__ == "__main__":
    # Test the search function
    files = search_oceancolor_files(period="MO", date_range=("2022-01-01", "2022-03-31"))
    print(f"Found {len(files)} files:")
    for file in files:
        print(f"  - {file}")
