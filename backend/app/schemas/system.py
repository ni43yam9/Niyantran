from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class SystemInfoResponse(BaseModel):
    app_name: str
    version: str
    environment: str
    debug: bool
    auth_enabled: bool
    database_url: str
    journal_mode: str
    table_counts: Dict[str, int]

class SystemIntegrityResponse(BaseModel):
    status: str
    integrity_check: str
    foreign_key_violations: int
    journal_mode: str
    table_counts: Dict[str, int]

class BackupMetadataResponse(BaseModel):
    status: str
    filename: str
    path: str
    size_bytes: int
    sha256: str
    created_at: str
    integrity: Optional[str] = None
    foreign_key_violations: Optional[int] = None

class RestoreRequest(BaseModel):
    backup_filename: str = Field(..., description="Name of the backup file to restore from")

class RestoreResponse(BaseModel):
    status: str
    restored_from: str
    target_database: str
    safety_snapshot: Optional[str] = None
    integrity: str
    foreign_key_violations: int
    table_counts: Optional[Dict[str, int]] = None
