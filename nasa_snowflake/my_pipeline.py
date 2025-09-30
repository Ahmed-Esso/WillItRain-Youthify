import pandas as pd
import xarray as xr
import os
from dagster import op, job, Out
from datetime import datetime
import calendar

VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

DATA_DIR = "/path/to/nasa/files"   # مكان الملفات

def get_month_range(year):
    """Generate list of (start_date, end_date) per month"""
    months = []
    for m in range(1, 13):
        start = datetime(year, m, 1)
        end_day = calendar.monthrange(year, m)[1]
        end = datetime(year, m, end_day)
        months.append((start, end))
    return months

@op(out=Out(pd.DataFrame))
def extract_variables(context, year: int = 2023):
    dfs = []
    for (start, end) in get_month_range(year):
        context.log.info(f"Processing {start.strftime('%Y-%m')} ...")
        
        # اختاري الملفات الخاصة بالشهر ده
        monthly_files = [
            f for f in os.listdir(DATA_DIR) 
            if f.endswith(".nc4") and start.strftime("%Y%m") in f
        ]
        
        for f in monthly_files:
            ds = xr.open_dataset(os.path.join(DATA_DIR, f), engine="h5netcdf", chunks={})
            df = ds[VARIABLES].to_dataframe().reset_index()
            dfs.append(df)
            ds.close()
    
    # نجمع كل الشهور بعد ما نعمل لهم concat
    final_df = pd.concat(dfs, ignore_index=True)
    context.log.info(f"Final dataframe shape: {final_df.shape}")
    return final_df

@op
def transform_variables(context, df: pd.DataFrame):
    context.log.info("Transforming variables...")
    # أي transformations
    return df

@op
def load_variables_to_snowflake(context, df: pd.DataFrame):
    context.log.info(f"Loading {len(df)} rows to Snowflake...")
    # هنا الكود اللي يلود في Snowflake
    return "done"

@job
def nasa_variables_pipeline():
    df = extract_variables()
    transformed = transform_variables(df)
    load_variables_to_snowflake(transformed)
