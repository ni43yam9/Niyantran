from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SyncOperationItem(BaseModel):
    """
    Individual synchronization operation item submitted by a client device.
    """
    model_config = ConfigDict(extra="ignore")

    operation_uuid: str = Field(..., min_length=1, max_length=64, description="Unique client idempotency token (UUIDv4)")
    device_uuid: Optional[str] = Field(None, max_length=64, description="Client device UUID")
    entity_type: str = Field(..., min_length=1, max_length=32, description="Productivity entity type")
    entity_id: str = Field(..., min_length=1, max_length=64, description="ID of entity being mutated")
    operation_type: str = Field(..., min_length=1, max_length=16, description="Operation: CREATE, UPDATE, or DELETE")
    entity_version: int = Field(1, ge=1, description="Entity version at modification time")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Entity attributes snapshot")
    created_at: Optional[datetime] = Field(None, description="Client timestamp when change was logged")


class SyncPushRequest(BaseModel):
    """
    Batch push request containing queued changes from an authenticated client device.
    """
    model_config = ConfigDict(extra="ignore")

    device_uuid: Optional[str] = Field(None, max_length=64, description="Client device UUID if omitted from header")
    operations: List[SyncOperationItem] = Field(default_factory=list, description="Ordered batch of sync operations")


class SyncPushResultItem(BaseModel):
    """
    Status report for an individual operation within a push batch.
    """
    model_config = ConfigDict(from_attributes=True)

    operation_uuid: str
    status: str = Field(..., description="'APPLIED', 'REJECTED', 'CONFLICT', or 'SUPERSEDED'")
    entity_type: str
    entity_id: str
    server_version: int
    message: Optional[str] = None


class SyncPushResponse(BaseModel):
    """
    Server response for a batch push synchronization request.
    """
    model_config = ConfigDict(from_attributes=True)

    applied: int
    rejected: int
    results: List[SyncPushResultItem]
    server_timestamp: datetime


class SyncChangeItem(BaseModel):
    """
    Individual change item returned to a client during a pull synchronization request.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    operation_uuid: str
    device_uuid: str
    entity_type: str
    entity_id: str
    operation_type: str
    entity_version: int
    payload: Optional[Dict[str, Any]] = None
    client_created_at: Optional[datetime] = None
    received_at: datetime
    status: str


class SyncPullResponse(BaseModel):
    """
    Paginated server response containing delta changes since the provided cursor.
    """
    model_config = ConfigDict(from_attributes=True)

    changes: List[SyncChangeItem]
    next_cursor: int
    has_more: bool
    server_timestamp: datetime


class SyncStatusResponse(BaseModel):
    """
    Synchronization status summary for an authenticated user and device.
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    device_uuid: Optional[str] = None
    registered_devices_count: int
    device_status: Optional[str] = None
    last_pulled_cursor: int = 0
    last_pushed_cursor: int = 0
    latest_server_cursor: int = 0
    pending_pull_count: int = 0
    last_synced_at: Optional[datetime] = None
    server_timestamp: datetime


class SyncAcknowledgeRequest(BaseModel):
    """
    Client acknowledgment indicating successfully pulled and locally applied changes.
    """
    model_config = ConfigDict(extra="ignore")

    cursor: int = Field(..., ge=0, description="Highest sequence ID received and processed")
    device_uuid: Optional[str] = Field(None, max_length=64, description="Device UUID if omitted from header")


class SyncAcknowledgeResponse(BaseModel):
    """
    Server confirmation of client pull checkpoint acknowledgment.
    """
    model_config = ConfigDict(from_attributes=True)

    acknowledged: bool = True
    device_uuid: str
    last_pulled_cursor: int
    acknowledged_at: datetime


class SyncConflictItem(BaseModel):
    """
    Conflict record item stored on the server for tracking and multi-device coordination.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    entity_type: str
    entity_id: str
    base_version: int
    local_version: int
    remote_version: int
    detecting_device_uuid: str
    conflicting_device_uuid: Optional[str] = None
    status: str
    resolution_strategy: Optional[str] = None
    local_data: Optional[Dict[str, Any]] = None
    remote_data: Optional[Dict[str, Any]] = None
    resolved_data: Optional[Dict[str, Any]] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None


class SyncConflictRecordRequest(BaseModel):
    """
    Client request to register a detected conflict on the cloud server.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., max_length=64, description="Unique conflict UUID")
    entity_type: str = Field(..., max_length=32)
    entity_id: str = Field(..., max_length=64)
    base_version: int = Field(1, ge=1)
    local_version: int = Field(1, ge=1)
    remote_version: int = Field(1, ge=1)
    detecting_device_uuid: Optional[str] = Field(None, max_length=64)
    conflicting_device_uuid: Optional[str] = Field(None, max_length=64)
    local_data: Optional[Dict[str, Any]] = None
    remote_data: Optional[Dict[str, Any]] = None


class SyncConflictResolveRequest(BaseModel):
    """
    Client request to record conflict resolution on the cloud server.
    """
    model_config = ConfigDict(extra="ignore")

    strategy: str = Field(..., description="Resolution strategy: KEEP_LOCAL, KEEP_REMOTE, MANUAL_MERGE")
    resolved_data: Optional[Dict[str, Any]] = Field(default=None, description="Resolved entity attributes snapshot")
    device_uuid: Optional[str] = Field(None, max_length=64)


class SyncConflictListResponse(BaseModel):
    """
    List of active and resolved conflicts for the user.
    """
    model_config = ConfigDict(from_attributes=True)

    conflicts: List[SyncConflictItem]
    total_unresolved: int
