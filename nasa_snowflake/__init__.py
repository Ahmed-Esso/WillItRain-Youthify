from dagster import Definitions
from .nasa_daily_weather_pipeline import nasa_daily_weather_pipeline
from .nasa_daily_wind_pipeline import nasa_daily_wind_pipeline
from .nasa_daily_dewpoint_2022_pipeline import nasa_daily_dewpoint_2022_pipeline
from .nasa_daily_wetbulb_2022_pipeline import nasa_daily_wetbulb_2022_pipeline


# ده اللي Dagster هيستخدمه عشان يلاقي الـ jobs
defs = Definitions(
    jobs=[nasa_daily_weather_pipeline, nasa_daily_wind_pipeline,nasa_daily_dewpoint_2022_pipeline,nasa_daily_wetbulb_2022_pipeline]
)


