import os
import sys
from pathlib import Path

# Resolve base directories
# config.py is at backend/app/core/config.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # Niyantra/
DB_PATH = BASE_DIR / "niyantra.db"

# Ensure both project root and backend dir are in sys.path for flexible importing
for path_to_add in (str(PROJECT_ROOT), str(BASE_DIR)):
    if path_to_add not in sys.path:
        sys.path.insert(0, path_to_add)

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "NIYANTRA Backend API")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    
    # CORS origins
    _cors_env: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173",
    )
    CORS_ORIGINS: list[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

settings = Settings()
