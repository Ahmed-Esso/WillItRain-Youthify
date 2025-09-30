from dagster import Definitions
from .my_pipeline import nasa_daily_temperature_pipeline

# ده اللي Dagster هيستخدمه عشان يلاقي الـ jobs
defs = Definitions(
    jobs=[nasa_daily_temperature_pipeline]
)
