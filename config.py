# config.py
import streamlit as st

SNOWFLAKE_CONFIG = {
    "account": st.secrets["SNOWFLAKE_ACCOUNT"],
    "user": st.secrets["SNOWFLAKE_USER"],
    "password": st.secrets["SNOWFLAKE_PASSWORD"],
    "authenticator": "snowflake",
    "role": "ACCOUNTADMIN",
    "warehouse": "NASA_WH",
    "database": "NASA_DB",
    "schema": "PUBLIC"
}

# Alexandria Bounding Box
ALEX_BOUNDING_BOX = (29.5, 30.8, 31.5, 31.3)  # lon_min, lat_min, lon_max, lat_max

# MERRA-2 Variable to Dataset mapping
VARIABLE_TO_DATASET = {
    # Core Weather
    "T2M": "M2I1NXASM",
    "QV2M": "M2I1NXASM",
    "T2MDEW": "M2I1NXASM",

    # Wind & Pressure
    "U10M": "M2I1NXASM",
    "V10M": "M2I1NXASM",
    "PS": "M2I1NXASM",
    "SLP": "M2I1NXASM",

    # Advanced Moisture
    "T2MWET": "M2I1NXASM",
    "TQI": "M2I1NXASM",
    "TQL": "M2I1NXASM",

    # Dynamics & Boundary
    "OMEGA500": "M2I3NVASM",
    "OMEGA": "M2I3NVASM",
    "DISPH": "M2T1NXFLX",
    "PBLH": "M2T1NXFLX",
    "TO3": "M2T1NXCHM",
    "O3": "M2T1NXCHM"
}

# Thermal Variables (for Celsius conversion)
THERMAL_VARS = {"T2M", "T2MDEW", "T2MWET"}
