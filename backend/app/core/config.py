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
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development" if os.getenv("DEBUG", "True").lower() in ("true", "1", "yes") else "production")
    DB_PATH: Path = DB_PATH
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    BACKUP_DIR: Path = Path(os.getenv("NIYANTRA_BACKUP_DIR", str(BASE_DIR / "backups")))

    # Optional API key for remote / protected environments.
    # When None, single-user desktop / offline operation is frictionless.
    API_KEY: str | None = os.getenv("NIYANTRA_API_KEY", None)

    # JWT & Authentication configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "niyantra-super-secret-dev-key-change-in-production-2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 days

    # Performance thresholds
    SLOW_REQUEST_THRESHOLD_MS: float = float(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "250.0"))
    
    # CORS origins
    _cors_env: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173,http://localhost:3000,http://127.0.0.1:3000",
    )
    CORS_ORIGINS: list[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

settings = Settings()
