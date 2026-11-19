from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.database import get_db
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.services import dashboard_service
from backend.app.core.config import settings

router = APIRouter(tags=["Dashboard & Health"])

@router.get("/api/dashboard/summary", response_model=DashboardSummaryResponse, response_model_by_alias=True)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Returns aggregated metrics, tasks due today, top priorities, and category distribution.
    """
    return dashboard_service.get_dashboard_summary(db)

@router.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying API and SQLite database connectivity.
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1")).scalar()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
    }
