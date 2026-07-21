"""Quick import verification for senamhi_datalake package."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.stdout.reconfigure(encoding="utf-8")

errors = []

try:
    from senamhi_datalake.core.config import settings
    print(f"  OK config: {settings.project_name} v{settings.project_version}")
except Exception as e:
    errors.append(f"config: {e}")

try:
    from senamhi_datalake.models.orm import Station, User, ExtractionTask
    print("  OK models")
except Exception as e:
    errors.append(f"models: {e}")

try:
    from senamhi_datalake.schemas.dto import StationOut, ExtractionTaskOut, SystemStatusOut
    print("  OK schemas")
except Exception as e:
    errors.append(f"schemas: {e}")

try:
    from senamhi_datalake.services.catalog import StationCatalog, DataReader
    from senamhi_datalake.services.extraction import ExtractionRunner
    print("  OK services")
except Exception as e:
    errors.append(f"services: {e}")

try:
    from senamhi_datalake.routers import auth, stations, extractions, system
    print("  OK routers")
except Exception as e:
    errors.append(f"routers: {e}")

try:
    from senamhi_datalake.app import create_app
    print("  OK app factory")
except Exception as e:
    errors.append(f"app: {e}")

if errors:
    print(f"\nERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll imports OK -- package is ready!")
