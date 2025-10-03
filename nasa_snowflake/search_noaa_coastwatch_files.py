# my_pipeline_chlora_earthaccess.py
import xarray as xr
import pandas as pd
from dagster import job, op, DynamicOut, DynamicOutput, get_dagster_logger
from dagster import ConfigurableResource, EnvVar
import earthaccess
from datetime import datetime
from typing import List, Optional
import os

# ==========================
# CONFIGURATION USING ENV VARS (Fixed)
# ==========================
class SnowflakeResource(ConfigurableResource):
    """Snowflake configuration using environment variables"""
    account: str
    user: str 
    password: str
    warehouse: str = "NASA_WH"  # استخدام default value مباشرة
    database: str = "NASA_DB"   # بدون EnvVar
    schema: str = "PUBLIC"
    role: str = "ACCOUNTADMIN"

class EarthdataConfig(ConfigurableResource):
    """NASA Earthdata configuration"""
    username: str
    password: str

# ==========================
# HELPER FUNCTIONS
# ==========================
def init_earthaccess():
    """Initialize earthaccess with environment credentials"""
    try:
        auth = earthaccess.login(
            strategy="environment",
            persist=True
        )
        return auth
    except Exception as e:
        get_dagster_logger().error(f"Earthdata login failed: {e}")
        raise

# ==========================
# DAGSTER OPS
# ==========================
@op(out=DynamicOut())
def search_nasa_chlor_a_2022():
    """Search for MODIS Aqua Chlorophyll files"""
    logger = get_dagster_logger()
    
    logger.info("🔍 Logging into NASA Earthdata...")
    auth = init_earthaccess()
    
    logger.info("🔍 Searching for MODIS Aqua Chlorophyll L3 files for 2022...")
    
    results = earthaccess.search_data(
        short_name="MODISA_L3m_CHL",
        cloud_hosted=True,
        temporal=("2022-01-01", "2022-01-10"),  # 10 days for testing
        bounding_box=(25.0, 22.0, 37.0, 32.0),  # Egypt/East Med
        count=5  # Limit for testing
    )
    
    logger.info(f"✅ Found {len(results)} chlor_a files")
    
    for idx, granule in enumerate(results):
        yield DynamicOutput(
            value=granule,
            mapping_key=f"file_{idx}"
        )

@op
def process_chlor_a_stream(context, granule) -> pd.DataFrame:
    """Process file directly using earthaccess stream"""
    logger = get_dagster_logger()
    
    try:
        logger.info(f"🔗 Streaming file: {granule['meta']['native-id']}")
        
        # Open file as stream
        files = earthaccess.open([granule])
        file_stream = files[0]
        
        logger.info("📖 Reading NetCDF stream...")
        
        # Read data directly from stream
        with xr.open_dataset(file_stream) as ds:
            if "chlor_a" not in ds.variables:
                logger.warning("⚠️ chlor_a not found in file")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = ds[["chlor_a"]].to_dataframe().reset_index()
            
            # Extract date from metadata
            start_time = granule['meta'].get('start-time')
            if start_time:
                file_date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%fZ").date()
            else:
                # Fallback: from filename
                filename = granule['meta']['native-id']
                date_str = filename[1:9]  # YYYYMMDD from A20220101...
                file_date = datetime.strptime(date_str, "%Y%m%d").date()
            
            df["date"] = file_date
            df["variable"] = "chlor_a"
            
            # Calculate daily averages
            daily_avg = df.groupby(["date", "lat", "lon"])["chlor_a"].mean().reset_index()
            
            logger.info(f"✅ Processed {len(daily_avg)} chlor_a records from stream")
            return daily_avg
        
    except Exception as e:
        logger.error(f"❌ Error processing stream: {e}")
        return pd.DataFrame()
    finally:
        # Ensure stream is closed
        if 'file_stream' in locals():
            file_stream.close()

@op
def transform_daily_data(df: pd.DataFrame) -> pd.DataFrame:
    """Transform chlorophyll data"""
    logger = get_dagster_logger()
    
    if df.empty:
        return df
    
    # Aggregate daily statistics
    daily_summary = (
        df.groupby(["date", "variable"])
        .agg({
            "chlor_a": ["mean", "count", "std"],
            "lat": "nunique",
            "lon": "nunique"
        })
        .reset_index()
    )
    
    # Flatten column names
    daily_summary.columns = [
        "date", "variable", "avg_value", "measurement_count", 
        "std_value", "unique_lats", "unique_lons"
    ]
    
    # Add date dimensions
    daily_summary["year"] = pd.to_datetime(daily_summary["date"]).dt.year
    daily_summary["month"] = pd.to_datetime(daily_summary["date"]).dt.month
    daily_summary["day"] = pd.to_datetime(daily_summary["date"]).dt.day
    
    # Add quality indicator
    daily_summary["data_quality"] = (
        daily_summary["measurement_count"] / 
        (daily_summary["unique_lats"] * daily_summary["unique_lons"])
    )
    
    result = daily_summary[[
        "date", "year", "month", "day", "variable", 
        "avg_value", "std_value", "measurement_count",
        "unique_lats", "unique_lons", "data_quality"
    ]]
    
    logger.info(f"📊 Transformed {len(result)} daily summaries")
    return result

@op
def load_daily_to_snowflake(df: pd.DataFrame, snowflake: SnowflakeResource):
    """Load data to Snowflake"""
    logger = get_dagster_logger()
    
    if df.empty:
        logger.info("⏭️ No data to load")
        return "skipped"
    
    import snowflake.connector
    
    conn = None
    try:
        conn = snowflake.connector.connect(
            account=snowflake.account,
            user=snowflake.user,
            password=snowflake.password,
            warehouse=snowflake.warehouse,
            database=snowflake.database,
            schema=snowflake.schema,
            role=snowflake.role
        )
        cur = conn.cursor()
        
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS NASA_CHLOR_A_STREAM (
                date DATE,
                year INT,
                month INT,
                day INT,
                variable STRING,
                avg_value FLOAT,
                std_value FLOAT,
                measurement_count INT,
                unique_lats INT,
                unique_lons INT,
                data_quality FLOAT,
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
                float(row["std_value"]) if pd.notna(row["std_value"]) else None,
                int(row["measurement_count"]),
                int(row["unique_lats"]),
                int(row["unique_lons"]),
                float(row["data_quality"]),
                "DAGSTER_CLOUD_STREAM"
            )
            for _, row in df.iterrows()
        ]
        
        # Insert data
        insert_query = """
            INSERT INTO NASA_CHLOR_A_STREAM 
            (date, year, month, day, variable, avg_value, std_value, 
             measurement_count, unique_lats, unique_lons, data_quality, file_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        logger.info(f"✅ Successfully loaded {len(df)} records to Snowflake")
        return "success"
        
    except Exception as e:
        logger.error(f"❌ Error loading to Snowflake: {e}")
        return "failed"
    finally:
        if conn:
            cur.close()
            conn.close()

# ==========================
# DAGSTER JOBS
# ==========================
@job
def nasa_chlor_a_daily_pipeline():
    """Daily pipeline for chlorophyll data processing"""
    
    # Search for files
    files = search_nasa_chlor_a_2022()
    
    # Process each file using stream
    processed = files.map(process_chlor_a_stream)
    
    # Transform data
    transformed = processed.map(transform_daily_data)
    
    # Load to Snowflake
    transformed.map(load_daily_to_snowflake)

# ==========================
# بديل أبسط إذا واجهت مشاكل مع ConfigurableResource
# ==========================
@job
def simple_nasa_chlor_a_pipeline():
    """Simple pipeline without complex configurations"""
    logger = get_dagster_logger()
    logger.info("🚀 Starting simple NASA Chlorophyll pipeline...")
    
    files = search_nasa_chlor_a_2022()
    processed = files.map(process_chlor_a_stream)
    transformed = processed.map(transform_daily_data)
    
    # سنتعامل مع Snowflake بشكل منفصل في البداية
    for df in transformed:
        if not df.empty:
            logger.info(f"📊 Processed {len(df)} records ready for Snowflake")
