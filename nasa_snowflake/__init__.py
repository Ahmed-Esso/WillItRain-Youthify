from dagster import Definitions
from .my_pipeline import nasa_temperature_pipeline

# Dagster هيلاقي الـ job الجديد هنا
defs = Definitions(
    jobs=[nasa_temperature_pipeline]
)
