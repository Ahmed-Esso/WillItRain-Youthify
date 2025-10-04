from dagster import Definitions, JobDefinition
import pkgutil, importlib, inspect, sys

package_name = __name__

jobs = []

for _, module_name, _ in pkgutil.iter_modules(sys.modules[package_name].__path__):
    module = importlib.import_module(f"{package_name}.{module_name}")
    for name, obj in inspect.getmembers(module):
        if isinstance(obj, JobDefinition):  # ✅ بدلاً من job
            print(f"✅ Loaded job: {name}")
            jobs.append(obj)

defs = Definitions(jobs=jobs)
