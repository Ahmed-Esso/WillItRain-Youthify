import pandas as pd
import xarray as xr
import os
from dagster import op, job, Out
from datetime import datetime
import calendar

# المتغيرات اللي عايزين نسحبها
VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

# مكان ملفات NASA
DATA_DIR = "/path/to/nasa/files"

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
    """
    بدل ما نحمل السنة كلها مرة واحدة → نرجع DataFrame لكل ملف/شهر بـ yield
    """
    for (start, end) in get_month_range(year):
        context.log.info(f"Processing {start.strftime('%Y-%m')} ...")

        # نختار الملفات الخاصة بالشهر
        monthly_files = [
            f for f in os.listdir(DATA_DIR) 
            if f.endswith(".nc4") and start.strftime("%Y%m") in f
        ]

        for f in monthly_files:
            file_path = os.path.join(DATA_DIR, f)
            context.log.info(f"Opening file {file_path}")

            # نفتح الملف
            ds = xr.open_dataset(file_path, engine="h5netcdf")

            # ناخد المتغيرات المطلوبة
            df = ds[VARIABLES].to_dataframe().reset_index()
            ds.close()

            context.log.info(f"Yielding dataframe of shape {df.shape}")
            yield df   # نرجع جزء واحد في المرة

@op
def transform_variables(context, df: pd.DataFrame):
    context.log.info(f"Transforming batch with shape {df.shape}")
    # ممكن تضيفي أي transformations هنا
    return df

@op
def load_variables_to_snowflake(context, df: pd.DataFrame):
    context.log.info(f"Loading {len(df)} rows to Snowflake...")
    # الكود الخاص بـ Snowflake هنا
    return "done"

@job
def nasa_variables_pipeline():
    extracted = extract_variables()
    transformed = transform_variables(extracted)
    load_variables_to_snowflake(transformed)
