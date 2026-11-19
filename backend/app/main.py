import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.database import init_db
from backend.app.routers import (
    tasks_router,
    goals_router,
    dashboard_router,
    migration_router,
    habits_router,
    timeblocks_router,
    behaviour_router,
    analytics_router,
    recommendations_router,
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

# Configure CORS for local development and multi-device access
origins = list(settings.CORS_ORIGINS)
# Ensure standard Vite ports are allowed
for o in ("http://localhost:5173", "http://localhost:4173", "http://127.0.0.1:5173", "http://127.0.0.1:4173"):
    if o not in origins:
        origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if not settings.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(dashboard_router)
app.include_router(tasks_router)
app.include_router(goals_router)
app.include_router(migration_router)
app.include_router(habits_router)
app.include_router(timeblocks_router)
app.include_router(behaviour_router)
app.include_router(analytics_router)
app.include_router(recommendations_router)

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/api/health",
        "tagline": "I for N@49_89#41_84@73",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
