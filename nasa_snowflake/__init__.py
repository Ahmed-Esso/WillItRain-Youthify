from dagster import Definitions
from .my_pipeline import nasa_climate_pipeline

# ده اللي Dagster هيستخدمه عشان يلاقي الـ jobs
defs = Definitions(
    jobs=[nasa_climate_pipeline]  # غيرنا الاسم للصحيح
)
