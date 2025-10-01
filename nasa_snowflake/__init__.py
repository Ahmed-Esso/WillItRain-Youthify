from dagster import Definitions, job
import pkgutil, importlib, inspect, sys

# هنجيب اسم الباكيج (مثلاً nasa_snowflake)
package_name = __name__

jobs = []

# نعمل import لكل modules في الباكيج
for _, module_name, _ in pkgutil.iter_modules(sys.modules[package_name].__path__):
    module = importlib.import_module(f"{package_name}.{module_name}")
    # ندور على أي object معمول له decorator @job
    for name, obj in inspect.getmembers(module):
        if isinstance(obj, job):
            jobs.append(obj)

# نعرف الـ definitions
defs = Definitions(jobs=jobs)
