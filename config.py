# config.py
SNOWFLAKE_CONFIG = {
    "account": "KBZQPZO-WX06551",
    "user": "A7MEDESSO",
    "password": "Ahmedesso@2005",
    "authenticator": "snowflake",
    "role": "ACCOUNTADMIN",
    "warehouse": "NASA_WH",
    "database": "NASA_DB",
    "schema": "PUBLIC"
}

# مربع الإسكندرية
ALEX_BOUNDING_BOX = (29.5, 30.8, 31.5, 31.3)  # lon_min, lat_min, lon_max, lat_max

# خريطة المتغيرات لمجموعات MERRA-2
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
    "TQI": "M2I1NXASM",  # جرب هذا الداتاسيت,
    "TQL": "M2I1NXASM",
    
    # Dynamics & Boundary
    "OMEGA500": "M2I3NVASM",
    "DISPH": "M2T1NXFLX",
    "PBLH": "M2T1NXFLX",      # PBLTOP في طلبك = PBLH في MERRA-2
    "TO3": "M2T1NXCHM",       # TOX (الأوزون الكلي) = TO3 في MERRA-2
    "O3": "M2T1NXCHM"         # TO3 (الأوزون السطحي) = O3 في MERRA-2
}

# المتغيرات الحرارية (لتحويلها لمئوية)
THERMAL_VARS = {"T2M", "T2MDEW", "T2MWET"}
