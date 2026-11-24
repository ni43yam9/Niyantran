import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.config import settings
from backend.app.core.security import verify_api_key, is_auth_required
from backend.app.services import backup_service
from backend.app.schemas.system import (
    SystemInfoResponse,
    SystemIntegrityResponse,
    BackupMetadataResponse,
    RestoreRequest,
    RestoreResponse,
)

logger = logging.getLogger("niyantra.system")
router = APIRouter(prefix="/api/system", tags=["System & Reliability"])

@router.get("/info", response_model=SystemInfoResponse)
def get_system_info(
    user: Optional[str] = Depends(verify_api_key),
):
    """
    Returns system runtime configuration, environment flags, and database statistics.
    """
    integrity_data = backup_service.verify_database_integrity()
    return SystemInfoResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
        auth_enabled=is_auth_required(),
        database_url=settings.DATABASE_URL.split("?")[0],  # Mask query params if any
        journal_mode=integrity_data.get("journal_mode", "UNKNOWN"),
        table_counts=integrity_data.get("table_counts", {}),
    )

@router.get("/integrity", response_model=SystemIntegrityResponse)
def get_system_integrity(
    user: Optional[str] = Depends(verify_api_key),
):
    """
    Runs SQLite integrity_check and foreign_key_check.
    Returns status: 'healthy' or 'unhealthy'.
    """
    report = backup_service.verify_database_integrity()
    if report.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=report.get("message", "Integrity check failed"),
        )
    return SystemIntegrityResponse(
        status=report.get("status", "unknown"),
        integrity_check=report.get("integrity_check", "unknown"),
        foreign_key_violations=report.get("foreign_key_violations", 0),
        journal_mode=report.get("journal_mode", "UNKNOWN"),
        table_counts=report.get("table_counts", {}),
    )

@router.post("/backup", response_model=BackupMetadataResponse)
def trigger_backup(
    label: Optional[str] = Query(None, description="Optional label for the backup file"),
    user: Optional[str] = Depends(verify_api_key),
):
    """
    Creates an atomic online backup of the SQLite database.
    Computes SHA-256 checksum and verifies backup integrity before returning.
    """
    try:
        meta = backup_service.create_database_backup(label=label)
        return BackupMetadataResponse(**meta)
    except Exception as exc:
        logger.error(f"Failed to create online backup: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup operation failed: {str(exc)}",
        )

@router.get("/backups", response_model=List[dict])
def list_backups(
    user: Optional[str] = Depends(verify_api_key),
):
    """
    Lists existing database backups sorted newest first.
    """
    return backup_service.list_backups()

@router.post("/restore", response_model=RestoreResponse)
def restore_database(
    payload: RestoreRequest,
    user: Optional[str] = Depends(verify_api_key),
):
    """
    Restores the database from a specified backup file.
    Automatically captures a pre-restore safety snapshot of the target database.
    """
    try:
        result = backup_service.restore_database_from_backup(payload.backup_filename)
        return RestoreResponse(
            status=result["status"],
            restored_from=result["restored_from"],
            target_database=result["target_database"],
            safety_snapshot=result.get("safety_snapshot"),
            integrity=result["integrity"],
            foreign_key_violations=result["foreign_key_violations"],
            table_counts=result.get("table_counts"),
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        logger.error(f"Database restoration failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restoration failed: {str(exc)}",
        )
