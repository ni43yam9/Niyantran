from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.migration import MigrationImportRequest, MigrationImportResponse, MigrationStatusResponse
from backend.app.services import migration_service

router = APIRouter(prefix="/api/migration", tags=["Data Migration"])

@router.post("/import", response_model=MigrationImportResponse, status_code=status.HTTP_200_OK, response_model_by_alias=True)
def import_local_storage_data(payload: MigrationImportRequest, db: Session = Depends(get_db)):
    """
    Safely and idempotently import existing localStorage tasks, goals, habits, and timeblocks into SQLite.
    Preserves existing IDs, unlinks invalid references safely, and prevents duplicate records.
    """
    return migration_service.import_records(
        db=db,
        tasks_data=payload.tasks,
        goals_data=payload.goals,
        habits_data=payload.habits,
        timeblocks_data=payload.timeblocks,
        overwrite=payload.overwrite,
    )

@router.get("/status", response_model=MigrationStatusResponse, response_model_by_alias=True)
def get_migration_status(db: Session = Depends(get_db)):
    """
    Returns counts of current records stored in the SQLite database.
    """
    return migration_service.get_migration_status(db)
