"""
Utility functions for loading and processing weather data
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta


def load_weather_data(source='demo'):
    """
    Load weather data from various sources
    
    Parameters:
    -----------
    source : str
        Data source ('demo', 'snowflake', 'csv')
    
    Returns:
    --------
    pd.DataFrame with weather data
    """
    if source == 'demo':
        return generate_demo_data()
    elif source == 'csv':
        return load_from_csv()
    elif source == 'snowflake':
        return load_from_snowflake()
    else:
        raise ValueError(f"Unknown data source: {source}")


def generate_demo_data(days=365):
    """Generate synthetic weather data for demo purposes"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate realistic weather patterns
    np.random.seed(42)
    
    data = {
        'DATE': dates,
        'TEMP': np.random.normal(25, 8, days),  # Temperature around 25°C
        'DEWPOINT': np.random.normal(18, 6, days),  # Dew point
        'HUMIDITY': np.clip(np.random.normal(65, 15, days), 20, 100),  # Humidity %
        'LIQUID_WATER': np.abs(np.random.normal(0.005, 0.01, days)),  # Liquid water
        'ICE_CONTENT': np.abs(np.random.normal(0.002, 0.005, days)),  # Ice content
        'WIND_SPEED': np.abs(np.random.normal(8, 4, days)),  # Wind speed m/s
        'SURFACE_PRESSURE': np.random.normal(101.3, 2, days),  # Pressure kPa
        'SEA_LEVEL_PRESSURE': np.random.normal(101.3, 2, days),  # SLP kPa
        'OMEGA500': np.random.normal(0, 0.05, days)  # Vertical velocity
    }
    
    df = pd.DataFrame(data)
    
    # Add some seasonal variation
    df['TEMP'] += 10 * np.sin(2 * np.pi * np.arange(days) / 365)
    
    # Ensure physical constraints
    df['DEWPOINT'] = df['TEMP'] - np.abs(df['TEMP'] - df['DEWPOINT'])
    df['HUMIDITY'] = df['HUMIDITY'].clip(0, 100)
    
    return df


def load_from_csv(filepath='data/weather_data.csv'):
    """Load weather data from CSV file"""
    if not os.path.exists(filepath):
        print(f"⚠️ CSV file not found: {filepath}")
        print("📊 Generating demo data instead...")
        return generate_demo_data()
    
    df = pd.read_csv(filepath)
    df['DATE'] = pd.to_datetime(df['DATE'])
    return df


def load_from_snowflake():
    """Load weather data from Snowflake database"""
    try:
        import snowflake.connector
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA'),
            role=os.getenv('SNOWFLAKE_ROLE')
        )
        
        query = """
        SELECT 
            t.date,
            t.avg_value AS temp,
            d.avg_value AS dewpoint,
            q.avg_value AS humidity,
            tql.avg_value AS liquid_water,
            tqi.avg_value AS ice_content,
            w.avg_value AS wind_speed,
            ps.avg_value AS surface_pressure,
            slp.avg_value AS sea_level_pressure,
            o.avg_value AS omega500
        FROM NASA_T2M_ALEX t
        JOIN NASA_T2MDEW_ALEX d ON t.date = d.date
        JOIN NASA_QV2M_ALEX q ON t.date = q.date
        JOIN NASA_TQL_ALEX tql ON t.date = tql.date
        JOIN NASA_TQI_ALEX tqi ON t.date = tqi.date
        JOIN NASA_WIND_SPEED_ALEX w ON t.date = w.date
        JOIN NASA_PS_ALEX ps ON t.date = ps.date
        JOIN NASA_SLP_ALEX slp ON t.date = slp.date
        JOIN NASA_OMEGA500_ALEX o ON t.date = o.date
        ORDER BY t.date
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        # Standardize column names
        df.columns = [col.upper() for col in df.columns]
        
        return df
        
    except Exception as e:
        print(f"⚠️ Error loading from Snowflake: {str(e)}")
        print("📊 Generating demo data instead...")
        return generate_demo_data()


def prepare_features(df):
    """
    Prepare features for model prediction
    
    Parameters:
    -----------
    df : pd.DataFrame
        Raw weather data
    
    Returns:
    --------
    pd.DataFrame with engineered features
    """
    df_features = df.copy()
    
    # Date features
    if 'DATE' in df_features.columns:
        df_features['DATE'] = pd.to_datetime(df_features['DATE'])
        df_features['YEAR'] = df_features['DATE'].dt.year
        df_features['MONTH'] = df_features['DATE'].dt.month
        df_features['DAY'] = df_features['DATE'].dt.day
        df_features['DAY_OF_YEAR'] = df_features['DATE'].dt.dayofyear
        df_features['SEASON'] = (df_features['MONTH'] % 12 // 3) + 1
    
    # Temperature features
    df_features['TEMP_DEW_DIFF'] = df_features['TEMP'] - df_features['DEWPOINT']
    
    # Moisture features
    df_features['TOTAL_MOISTURE'] = df_features['LIQUID_WATER'] + df_features['ICE_CONTENT']
    df_features['MOISTURE_RATIO'] = df_features['LIQUID_WATER'] / (
        df_features['ICE_CONTENT'] + 0.001
    )
    
    # Interaction features
    df_features['HUMIDITY_WIND_INTERACTION'] = df_features['HUMIDITY'] * df_features['WIND_SPEED']
    df_features['TEMP_HUMIDITY'] = df_features['TEMP'] * df_features['HUMIDITY']
    df_features['PRESSURE_HUMIDITY_RATIO'] = df_features['SURFACE_PRESSURE'] / np.where(
        df_features['HUMIDITY'] == 0, 1, df_features['HUMIDITY']
    )
    
    # Clean infinite values
    df_features = df_features.replace([np.inf, -np.inf], np.nan)
    df_features = df_features.fillna(df_features.mean())
    
    return df_features


def get_current_weather(location='Alexandria'):
    """
    Get current weather for a location
    (Mock function - would integrate with real API in production)
    """
    return {
        'temp': 24.5,
        'humidity': 68,
        'dewpoint': 18.2,
        'liquid_water': 0.008,
        'ice_content': 0.002,
        'wind_speed': 12.3,
        'surface_pressure': 101.2,
        'location': location,
        'timestamp': datetime.now()
    }


def save_prediction_history(prediction, filepath='data/predictions.csv'):
    """Save prediction history to CSV"""
    os.makedirs('data', exist_ok=True)
    
    new_record = pd.DataFrame([{
        'timestamp': datetime.now(),
        'will_rain': prediction['will_rain'],
        'probability': prediction['probability']
    }])
    
    if os.path.exists(filepath):
        history = pd.read_csv(filepath)
        history = pd.concat([history, new_record], ignore_index=True)
    else:
        history = new_record
    
    history.to_csv(filepath, index=False)
