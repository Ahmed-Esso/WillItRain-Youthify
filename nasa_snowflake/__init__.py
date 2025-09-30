from dagster import Definitions
from .nasa_daily_weather_pipeline import nasa_daily_weather_pipeline
from .nasa_daily_wind_pipeline import nasa_daily_wind_pipeline

# ده اللي Dagster هيستخدمه عشان يلاقي الـ jobs
defs = Definitions(
    jobs=[nasa_daily_weather_pipeline, nasa_daily_wind_pipeline]
)
