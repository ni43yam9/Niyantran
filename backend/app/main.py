import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.middleware import RequestAuditingMiddleware
from backend.app.database import init_db
from backend.app.routers import (
    auth_router,
    devices_router,
    tasks_router,
    goals_router,
    dashboard_router,
    migration_router,
    habits_router,
    timeblocks_router,
    behaviour_router,
    analytics_router,
    recommendations_router,
    predictions_router,
    adaptive_router,
    system_router,
    daily_intents_router,
    sync_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("niyantra")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created
    logger.info("Initializing NIYANTRA database schema...")
    init_db()
    logger.info("NIYANTRA database initialized successfully.")
    yield
    # Shutdown
    logger.info("NIYANTRA API shutting down cleanly.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="High-performance backend API for NIYANTRA Personal Productivity System.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS for local development, LAN devices, and multi-device cloud access
origins = list(settings.CORS_ORIGINS)
# Ensure standard Vite & dev ports are allowed
for o in ("http://localhost:5173", "http://localhost:4173", "http://127.0.0.1:5173", "http://127.0.0.1:4173", "http://localhost:3000", "http://127.0.0.1:3000"):
    if o not in origins:
        origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lightweight request auditing and performance tracking
app.add_middleware(RequestAuditingMiddleware)

# Global unhandled exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred",
            "path": request.url.path,
            "error": str(exc) if settings.DEBUG else "Please check server logs",
        },
    )

# Include Routers
app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(dashboard_router)
app.include_router(tasks_router)
app.include_router(goals_router)
app.include_router(migration_router)
app.include_router(habits_router)
app.include_router(timeblocks_router)
app.include_router(behaviour_router)
app.include_router(analytics_router)
app.include_router(recommendations_router)
app.include_router(predictions_router)
app.include_router(adaptive_router)
app.include_router(system_router)
app.include_router(daily_intents_router)
app.include_router(sync_router)

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "tagline": "I for N@49_89#41_84@73",
    }

@app.get("/health")
def root_health():
    """
    Direct health check for cloud load balancers and deployment orchestrators.
    """
    from sqlalchemy import text
    from backend.app.database import engine
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check probe failed: {e}")
        db_status = f"unhealthy: {str(e)}" if settings.DEBUG else "unhealthy"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
