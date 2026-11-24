from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.sync import (
    SyncAcknowledgeRequest,
    SyncAcknowledgeResponse,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncStatusResponse,
    SyncConflictItem,
    SyncConflictRecordRequest,
    SyncConflictResolveRequest,
    SyncConflictListResponse,
)
from backend.app.services.sync_service import (
    acknowledge_sync,
    get_sync_status,
    process_pull,
    process_push,
    validate_device,
    record_conflict,
    resolve_server_conflict,
    list_user_conflicts,
)

sync_router = APIRouter(prefix="/api/sync", tags=["Synchronization"])


@sync_router.post(
    "/push",
    response_model=SyncPushResponse,
    status_code=status.HTTP_200_OK,
    summary="Push batch of queued local changes to cloud backend",
)
def push_changes(
    req: SyncPushRequest,
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Receives and processes an ordered batch of local change operations from an authenticated device.
    Enforces idempotency, tenant isolation, and strict device active status.
    """
    device_uuid = x_device_uuid or req.device_uuid
    device = validate_device(db, current_user, device_uuid)
    return process_push(db, current_user=current_user, device=device, operations=req.operations)


@sync_router.get(
    "/pull",
    response_model=SyncPullResponse,
    status_code=status.HTTP_200_OK,
    summary="Pull delta changes from cloud backend with monotonic cursor",
)
def pull_changes(
    cursor: int = Query(0, ge=0, description="Highest monotonic sequence ID previously processed"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of changes to return"),
    exclude_self: bool = Query(False, description="Whether to exclude changes originating from this device"),
    entity_type: Optional[str] = Query(None, description="Optional entity filter (e.g. 'task', 'goal')"),
    device_uuid: Optional[str] = Query(None, description="Requesting device UUID"),
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves changes occurring after the specified cursor.
    Enforces strict user isolation and monotonic ordering.
    """
    active_device_uuid = x_device_uuid or device_uuid
    device = None
    if active_device_uuid:
        device = validate_device(db, current_user, active_device_uuid)
    elif exclude_self:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device UUID is required when 'exclude_self' is True. Provide via 'X-Device-UUID' header or query parameter.",
        )

    return process_pull(
        db,
        current_user=current_user,
        device=device,
        cursor=cursor,
        limit=limit,
        exclude_self=exclude_self,
        entity_type=entity_type,
    )


@sync_router.get(
    "/status",
    response_model=SyncStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get synchronization status and pending change counts",
)
def sync_status(
    device_uuid: Optional[str] = Query(None, description="Device UUID to inspect"),
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns synchronization summary including registered device count, latest server cursor,
    and pending operations for the requesting device.
    """
    active_device_uuid = x_device_uuid or device_uuid
    device = None
    if active_device_uuid:
        device = validate_device(db, current_user, active_device_uuid)

    return get_sync_status(db, current_user=current_user, device=device)


@sync_router.get(
    "/changes",
    response_model=SyncPullResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect recent sync changes log",
)
def inspect_changes(
    since_cursor: int = Query(0, ge=0, alias="cursor", description="Sequence ID checkpoint"),
    limit: int = Query(50, ge=1, le=100, description="Max records to retrieve"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Inspection endpoint to inspect synchronization operations across all user devices.
    """
    return process_pull(
        db,
        current_user=current_user,
        device=None,
        cursor=since_cursor,
        limit=limit,
        exclude_self=False,
        entity_type=entity_type,
    )


@sync_router.post(
    "/acknowledge",
    response_model=SyncAcknowledgeResponse,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge pulled changes checkpoint",
)
def acknowledge(
    req: SyncAcknowledgeRequest,
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Acknowledges receipt and application of changes up to the given cursor,
    updating the client's pull checkpoint.
    """
    device_uuid = x_device_uuid or req.device_uuid
    device = validate_device(db, current_user, device_uuid)
    return acknowledge_sync(db, current_user=current_user, device=device, cursor=req.cursor)


@sync_router.get(
    "/conflicts",
    response_model=SyncConflictListResponse,
    status_code=status.HTTP_200_OK,
    summary="List synchronization conflicts for authenticated user",
)
def list_conflicts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (PENDING_RESOLUTION, RESOLVED_LOCAL, etc.)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (task, goal, etc.)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns conflict records belonging strictly to the authenticated user.
    """
    return list_user_conflicts(
        db,
        current_user=current_user,
        status_filter=status_filter,
        entity_type_filter=entity_type,
    )


@sync_router.post(
    "/conflicts/record",
    response_model=SyncConflictItem,
    status_code=status.HTTP_200_OK,
    summary="Record or update a synchronization conflict on the cloud server",
)
def record_conflict_endpoint(
    req: SyncConflictRecordRequest,
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registers a detected multi-device conflict on the server for coordination and history preservation.
    """
    device_uuid = x_device_uuid or req.detecting_device_uuid
    device = validate_device(db, current_user, device_uuid)
    return record_conflict(db, current_user=current_user, device=device, req=req)


@sync_router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=SyncConflictItem,
    status_code=status.HTTP_200_OK,
    summary="Resolve a synchronization conflict on the cloud server",
)
def resolve_conflict_endpoint(
    conflict_id: str,
    req: SyncConflictResolveRequest,
    x_device_uuid: Optional[str] = Header(None, alias="X-Device-UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Resolves a server-side conflict record using the selected strategy.
    Enforces account isolation and propagates the winning version to other devices.
    """
    device_uuid = x_device_uuid or req.device_uuid
    device = validate_device(db, current_user, device_uuid)
    return resolve_server_conflict(
        db,
        current_user=current_user,
        device=device,
        conflict_id=conflict_id,
        req=req,
    )
