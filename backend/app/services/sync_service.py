from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.activity_log import ActivityLog
from backend.app.models.daily_intent import DailyIntent
from backend.app.models.device import Device
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.recommendation import Recommendation
from backend.app.models.sync import SyncCursor, SyncEntityVersion, SyncOperation, SyncConflict
from backend.app.models.task import Task
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.user import User
from backend.app.schemas.sync import (
    SyncAcknowledgeResponse,
    SyncChangeItem,
    SyncOperationItem,
    SyncPullResponse,
    SyncPushResponse,
    SyncPushResultItem,
    SyncStatusResponse,
    SyncConflictItem,
    SyncConflictRecordRequest,
    SyncConflictResolveRequest,
    SyncConflictListResponse,
)

logger = logging.getLogger("niyantra.sync")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_date(val: Any) -> Optional[date]:
    """Safely parses a date string, datetime, or date object."""
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        # Handle ISO strings like 2026-11-22 or 2026-11-22T00:00:00Z
        clean_str = val.split("T")[0]
        try:
            return date.fromisoformat(clean_str)
        except Exception:
            return None
    return None


def parse_datetime(val: Any) -> Optional[datetime]:
    """Safely parses an ISO datetime string or datetime object."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


SUPPORTED_ENTITIES = {
    "task": "task",
    "goal": "goal",
    "habit": "habit",
    "habit_log": "habit_log",
    "daily_timeblock": "daily_timeblock",
    "timeblock": "daily_timeblock",
    "daily_intent": "daily_intent",
    "recommendation": "recommendation",
    "activity_log": "activity_log",
}


def normalize_entity_type(raw_type: str) -> Optional[str]:
    """Normalizes client entity type strings into canonical table identifiers."""
    if not raw_type:
        return None
    cleaned = raw_type.strip().lower()
    return SUPPORTED_ENTITIES.get(cleaned)


def validate_device(db: Session, user: User, device_uuid: Optional[str]) -> Device:
    """
    Validates that the device UUID exists, belongs to the authenticated user,
    and has not been revoked. Updates last_active_at on success.
    """
    if not device_uuid or not device_uuid.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client device UUID is required for synchronization. Provide via 'X-Device-UUID' header or request body.",
        )

    device = db.query(Device).filter(Device.device_uuid == device_uuid.strip()).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_uuid}' is not registered. Please register this device first via POST /api/devices/register.",
        )

    if device.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device ownership mismatch. This device belongs to a different user account.",
        )

    if device.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device access has been revoked. Synchronization operations are disabled for revoked devices.",
        )

    device.last_active_at = utc_now()
    return device


def _apply_entity_mutation(
    db: Session,
    user_id: str,
    entity_type: str,
    entity_id: str,
    operation_type: str,
    version: int,
    payload: Dict[str, Any],
) -> None:
    """
    Applies the mutation to the target domain model while respecting soft-deletion and version invariants.
    """
    op_upper = operation_type.upper()
    now = utc_now()

    # 1. TASK
    if entity_type == "task":
        existing = db.query(Task).filter(Task.id == entity_id, Task.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            start_d = parse_date(payload.get("start_date")) or now.date()
            due_d = parse_date(payload.get("due_date")) or start_d
            comp_at = parse_datetime(payload.get("completed_at"))

            if not existing:
                task = Task(
                    id=entity_id,
                    user_id=user_id,
                    title=payload.get("title", "Untitled Task"),
                    description=payload.get("description"),
                    task_type=payload.get("task_type", "Daily"),
                    category=payload.get("category", "Coding"),
                    priority=payload.get("priority", "Medium"),
                    status=payload.get("status", "Pending"),
                    start_date=start_d,
                    due_date=due_d,
                    goal_id=payload.get("goal_id"),
                    completed_at=comp_at,
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(task)
            else:
                if version >= existing.version:
                    for field in ("title", "description", "task_type", "category", "priority", "status", "goal_id"):
                        if field in payload:
                            setattr(existing, field, payload[field])
                    if "start_date" in payload:
                        existing.start_date = start_d
                    if "due_date" in payload:
                        existing.due_date = due_d
                    if "completed_at" in payload:
                        existing.completed_at = comp_at
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 2. GOAL
    elif entity_type == "goal":
        existing = db.query(Goal).filter(Goal.id == entity_id, Goal.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            start_d = parse_date(payload.get("start_date")) or now.date()
            target_d = parse_date(payload.get("target_date")) or start_d
            progress = max(0, min(100, int(payload.get("progress", 0))))

            if not existing:
                goal = Goal(
                    id=entity_id,
                    user_id=user_id,
                    title=payload.get("title", "Untitled Goal"),
                    description=payload.get("description"),
                    goal_type=payload.get("goal_type", "Short-Term"),
                    category=payload.get("category", "Coding"),
                    priority=payload.get("priority", "Medium"),
                    status=payload.get("status", "In Progress"),
                    start_date=start_d,
                    target_date=target_d,
                    progress=progress,
                    key_milestone=payload.get("key_milestone"),
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(goal)
            else:
                if version >= existing.version:
                    for field in ("title", "description", "goal_type", "category", "priority", "status", "key_milestone"):
                        if field in payload:
                            setattr(existing, field, payload[field])
                    if "start_date" in payload:
                        existing.start_date = start_d
                    if "target_date" in payload:
                        existing.target_date = target_d
                    if "progress" in payload:
                        existing.progress = progress
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 3. HABIT
    elif entity_type == "habit":
        existing = db.query(Habit).filter(Habit.id == entity_id, Habit.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            if not existing:
                habit = Habit(
                    id=entity_id,
                    user_id=user_id,
                    name=payload.get("name", "Untitled Habit"),
                    target=payload.get("target"),
                    category=payload.get("category", "General"),
                    frequency=payload.get("frequency", "Daily"),
                    base_streak=int(payload.get("base_streak", 0)),
                    archived=bool(payload.get("archived", False)),
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(habit)
            else:
                if version >= existing.version:
                    for field in ("name", "target", "category", "frequency", "base_streak", "archived"):
                        if field in payload:
                            setattr(existing, field, payload[field])
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 4. HABIT LOG
    elif entity_type == "habit_log":
        existing = db.query(HabitLog).filter(HabitLog.id == entity_id, HabitLog.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            log_d = parse_date(payload.get("log_date")) or now.date()
            if not existing:
                # Ensure referenced habit exists to preserve foreign keys
                habit_id = payload.get("habit_id")
                if habit_id and db.query(Habit).filter(Habit.id == habit_id).first():
                    habit_log = HabitLog(
                        id=entity_id,
                        user_id=user_id,
                        habit_id=habit_id,
                        log_date=log_d,
                        completed=bool(payload.get("completed", True)),
                        notes=payload.get("notes"),
                        version=version,
                        is_deleted=False,
                        deleted_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(habit_log)
            else:
                if version >= existing.version:
                    if "completed" in payload:
                        existing.completed = bool(payload["completed"])
                    if "notes" in payload:
                        existing.notes = payload["notes"]
                    if "log_date" in payload:
                        existing.log_date = log_d
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 5. DAILY TIMEBLOCK
    elif entity_type == "daily_timeblock":
        existing = db.query(DailyTimeblock).filter(DailyTimeblock.id == entity_id, DailyTimeblock.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            b_date = parse_date(payload.get("block_date")) or now.date()
            if not existing:
                tb = DailyTimeblock(
                    id=entity_id,
                    user_id=user_id,
                    block_date=b_date,
                    title=payload.get("title", "Timeblock"),
                    time=payload.get("time", "09:00 AM"),
                    duration_minutes=int(payload.get("duration_minutes", 60)),
                    actual_duration_minutes=payload.get("actual_duration_minutes"),
                    category=payload.get("category", "General"),
                    status=payload.get("status", "Pending"),
                    is_break=bool(payload.get("is_break", False)),
                    task_id=payload.get("task_id"),
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(tb)
            else:
                if version >= existing.version:
                    for field in ("title", "time", "duration_minutes", "actual_duration_minutes", "category", "status", "is_break", "task_id"):
                        if field in payload:
                            setattr(existing, field, payload[field])
                    if "block_date" in payload:
                        existing.block_date = b_date
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 6. DAILY INTENT
    elif entity_type == "daily_intent":
        intent_d = parse_date(payload.get("intent_date")) or now.date()
        existing = db.query(DailyIntent).filter(DailyIntent.id == entity_id, DailyIntent.user_id == user_id).first()
        if not existing:
            # Also check by user_id and intent_date to respect unique constraint
            existing = db.query(DailyIntent).filter(DailyIntent.user_id == user_id, DailyIntent.intent_date == intent_d).first()

        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            if not existing:
                di = DailyIntent(
                    id=entity_id,
                    user_id=user_id,
                    intent_date=intent_d,
                    intent_text=payload.get("intent_text", ""),
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(di)
            else:
                if version >= existing.version:
                    existing.intent_text = payload.get("intent_text", existing.intent_text)
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 7. RECOMMENDATION
    elif entity_type == "recommendation":
        existing = db.query(Recommendation).filter(Recommendation.id == entity_id, Recommendation.user_id == user_id).first()
        if op_upper == "DELETE":
            if existing:
                existing.is_deleted = True
                existing.deleted_at = now
                existing.version = max(existing.version + 1, version)
                existing.updated_at = now
        elif op_upper in ("CREATE", "UPDATE"):
            tgt_d = parse_date(payload.get("target_date"))
            if not existing:
                rec = Recommendation(
                    id=entity_id,
                    user_id=user_id,
                    type=payload.get("type", "PRIORITIZATION"),
                    category=payload.get("category", "Task"),
                    title=payload.get("title", "Recommendation"),
                    description=payload.get("description", ""),
                    reason=payload.get("reason", ""),
                    priority=payload.get("priority", "MEDIUM"),
                    status=payload.get("status", "PENDING"),
                    action_type=payload.get("action_type"),
                    action_payload=payload.get("action_payload"),
                    entity_id=payload.get("entity_id"),
                    target_date=tgt_d,
                    version=version,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(rec)
            else:
                if version >= existing.version:
                    for field in ("type", "category", "title", "description", "reason", "priority", "status", "action_type", "action_payload", "entity_id"):
                        if field in payload:
                            setattr(existing, field, payload[field])
                    if "target_date" in payload:
                        existing.target_date = tgt_d
                    existing.version = version
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.updated_at = now

    # 8. ACTIVITY LOG
    elif entity_type == "activity_log":
        existing = db.query(ActivityLog).filter(ActivityLog.id == entity_id, ActivityLog.user_id == user_id).first()
        if not existing and op_upper in ("CREATE", "UPDATE"):
            ev_ts = parse_datetime(payload.get("timestamp")) or now
            act = ActivityLog(
                id=entity_id,
                user_id=user_id,
                device_id=payload.get("device_id", "synced_device"),
                event_type=payload.get("event_type", "unknown"),
                entity_type=payload.get("entity_type", "task"),
                entity_id=payload.get("entity_id"),
                timestamp=ev_ts,
                original_date=parse_date(payload.get("original_date")),
                new_date=parse_date(payload.get("new_date")),
                duration_minutes=payload.get("duration_minutes"),
                actual_duration_minutes=payload.get("actual_duration_minutes"),
                details=payload.get("details"),
                created_at=now,
            )
            db.add(act)


def process_push(
    db: Session,
    current_user: User,
    device: Device,
    operations: List[SyncOperationItem],
) -> SyncPushResponse:
    """
    Processes an incoming batch of synchronization operations.
    Enforces idempotency, entity validation, version resolution, and database persistence.
    """
    results: List[SyncPushResultItem] = []
    applied_count = 0
    rejected_count = 0
    latest_op_id = None
    now = utc_now()

    for op_item in operations:
        # Check idempotency first: if operation_uuid was already processed for this user
        existing_op = (
            db.query(SyncOperation)
            .filter(
                SyncOperation.operation_uuid == op_item.operation_uuid,
                SyncOperation.user_id == current_user.id,
            )
            .first()
        )
        if existing_op:
            if existing_op.status == "APPLIED":
                applied_count += 1
            else:
                rejected_count += 1
            results.append(
                SyncPushResultItem(
                    operation_uuid=op_item.operation_uuid,
                    status=existing_op.status,
                    entity_type=existing_op.entity_type,
                    entity_id=existing_op.entity_id,
                    server_version=existing_op.entity_version,
                    message="Operation already processed (idempotent duplicate)",
                )
            )
            continue

        # Validate entity type
        norm_type = normalize_entity_type(op_item.entity_type)
        if not norm_type:
            rejected_count += 1
            results.append(
                SyncPushResultItem(
                    operation_uuid=op_item.operation_uuid,
                    status="REJECTED",
                    entity_type=op_item.entity_type,
                    entity_id=op_item.entity_id,
                    server_version=op_item.entity_version,
                    message=f"Unsupported entity_type '{op_item.entity_type}'",
                )
            )
            continue

        # Validate operation type
        op_type = op_item.operation_type.strip().upper()
        if op_type not in ("CREATE", "UPDATE", "DELETE"):
            rejected_count += 1
            results.append(
                SyncPushResultItem(
                    operation_uuid=op_item.operation_uuid,
                    status="REJECTED",
                    entity_type=norm_type,
                    entity_id=op_item.entity_id,
                    server_version=op_item.entity_version,
                    message=f"Invalid operation_type '{op_item.operation_type}'. Must be CREATE, UPDATE, or DELETE.",
                )
            )
            continue

        # Manage canonical entity version
        sync_ev = (
            db.query(SyncEntityVersion)
            .filter(
                SyncEntityVersion.user_id == current_user.id,
                SyncEntityVersion.entity_type == norm_type,
                SyncEntityVersion.entity_id == op_item.entity_id,
            )
            .first()
        )

        if not sync_ev:
            target_version = max(1, op_item.entity_version)
            sync_ev = SyncEntityVersion(
                user_id=current_user.id,
                entity_type=norm_type,
                entity_id=op_item.entity_id,
                current_version=target_version,
                last_modified_device=device.device_uuid,
                is_deleted=(op_type == "DELETE"),
                created_at=now,
                updated_at=now,
            )
            db.add(sync_ev)
        else:
            target_version = max(sync_ev.current_version + 1, op_item.entity_version)
            sync_ev.current_version = target_version
            sync_ev.last_modified_device = device.device_uuid
            sync_ev.is_deleted = (op_type == "DELETE")
            sync_ev.updated_at = now

        try:
            # Apply to underlying model table
            _apply_entity_mutation(
                db=db,
                user_id=current_user.id,
                entity_type=norm_type,
                entity_id=op_item.entity_id,
                operation_type=op_type,
                version=target_version,
                payload=op_item.payload or {},
            )

            # Record append-only sync operation log
            sync_op = SyncOperation(
                operation_uuid=op_item.operation_uuid,
                user_id=current_user.id,
                device_uuid=device.device_uuid,
                entity_type=norm_type,
                entity_id=op_item.entity_id,
                operation_type=op_type,
                entity_version=target_version,
                payload=op_item.payload or {},
                client_created_at=op_item.created_at,
                received_at=now,
                processed_at=now,
                status="APPLIED",
            )
            db.add(sync_op)
            db.flush()  # Populates sync_op.id

            latest_op_id = sync_op.id
            applied_count += 1
            results.append(
                SyncPushResultItem(
                    operation_uuid=op_item.operation_uuid,
                    status="APPLIED",
                    entity_type=norm_type,
                    entity_id=op_item.entity_id,
                    server_version=target_version,
                    message="Operation applied successfully",
                )
            )
        except Exception as exc:
            logger.warning(f"Failed to apply sync operation {op_item.operation_uuid}: {exc}")
            db.rollback()
            # In atomic or per-operation handling, rollback failed mutation and record rejection
            rejected_count += 1
            results.append(
                SyncPushResultItem(
                    operation_uuid=op_item.operation_uuid,
                    status="REJECTED",
                    entity_type=norm_type,
                    entity_id=op_item.entity_id,
                    server_version=op_item.entity_version,
                    message=f"Failed to apply: {str(exc)}",
                )
            )

    # Update SyncCursor for this device
    cursor_rec = (
        db.query(SyncCursor)
        .filter(
            SyncCursor.user_id == current_user.id,
            SyncCursor.device_uuid == device.device_uuid,
        )
        .first()
    )
    if not cursor_rec:
        cursor_rec = SyncCursor(
            user_id=current_user.id,
            device_uuid=device.device_uuid,
            last_pushed_cursor=latest_op_id or 0,
            last_sync_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(cursor_rec)
    else:
        if latest_op_id and latest_op_id > cursor_rec.last_pushed_cursor:
            cursor_rec.last_pushed_cursor = latest_op_id
        cursor_rec.last_sync_at = now
        cursor_rec.updated_at = now

    device.last_synced_at = now
    db.commit()

    return SyncPushResponse(
        applied=applied_count,
        rejected=rejected_count,
        results=results,
        server_timestamp=utc_now(),
    )


def process_pull(
    db: Session,
    current_user: User,
    device: Optional[Device],
    cursor: int = 0,
    limit: int = 50,
    exclude_self: bool = False,
    entity_type: Optional[str] = None,
) -> SyncPullResponse:
    """
    Returns delta sync operations for the user whose sequence ID > cursor.
    Supports pagination, device self-filtering, and entity filtering.
    """
    query = db.query(SyncOperation).filter(
        SyncOperation.user_id == current_user.id,
        SyncOperation.id > cursor,
    )

    if exclude_self and device:
        query = query.filter(SyncOperation.device_uuid != device.device_uuid)

    if entity_type:
        norm = normalize_entity_type(entity_type)
        if norm:
            query = query.filter(SyncOperation.entity_type == norm)

    query = query.order_by(SyncOperation.id.asc())

    fetch_limit = min(max(1, limit), 100)
    records = query.limit(fetch_limit + 1).all()

    has_more = len(records) > fetch_limit
    changes_batch = records[:fetch_limit]
    next_cursor = changes_batch[-1].id if changes_batch else cursor

    change_items = [
        SyncChangeItem(
            id=r.id,
            operation_uuid=r.operation_uuid,
            device_uuid=r.device_uuid,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            operation_type=r.operation_type,
            entity_version=r.entity_version,
            payload=r.payload,
            client_created_at=r.client_created_at,
            received_at=r.received_at,
            status=r.status,
        )
        for r in changes_batch
    ]

    return SyncPullResponse(
        changes=change_items,
        next_cursor=next_cursor,
        has_more=has_more,
        server_timestamp=utc_now(),
    )


def get_sync_status(
    db: Session,
    current_user: User,
    device: Optional[Device] = None,
) -> SyncStatusResponse:
    """
    Returns synchronization status summary for the user and (optionally) the requesting device.
    """
    reg_count = db.query(Device).filter(Device.user_id == current_user.id).count()
    latest_cursor = (
        db.query(func.max(SyncOperation.id))
        .filter(SyncOperation.user_id == current_user.id)
        .scalar()
        or 0
    )

    last_pulled = 0
    last_pushed = 0
    pending_count = 0
    last_synced = None

    if device:
        cursor_rec = (
            db.query(SyncCursor)
            .filter(
                SyncCursor.user_id == current_user.id,
                SyncCursor.device_uuid == device.device_uuid,
            )
            .first()
        )
        if cursor_rec:
            last_pulled = cursor_rec.last_pulled_cursor
            last_pushed = cursor_rec.last_pushed_cursor
            last_synced = cursor_rec.last_sync_at

        # Pending changes for this device are those with id > last_pulled originating from other devices
        pending_count = (
            db.query(SyncOperation)
            .filter(
                SyncOperation.user_id == current_user.id,
                SyncOperation.id > last_pulled,
                SyncOperation.device_uuid != device.device_uuid,
            )
            .count()
        )
    else:
        pending_count = 0

    return SyncStatusResponse(
        user_id=current_user.id,
        device_uuid=device.device_uuid if device else None,
        registered_devices_count=reg_count,
        device_status=device.status if device else None,
        last_pulled_cursor=last_pulled,
        last_pushed_cursor=last_pushed,
        latest_server_cursor=latest_cursor,
        pending_pull_count=pending_count,
        last_synced_at=last_synced,
        server_timestamp=utc_now(),
    )


def acknowledge_sync(
    db: Session,
    current_user: User,
    device: Device,
    cursor: int,
) -> SyncAcknowledgeResponse:
    """
    Updates the device's synchronization cursor checkpoint.
    """
    now = utc_now()
    cursor_rec = (
        db.query(SyncCursor)
        .filter(
            SyncCursor.user_id == current_user.id,
            SyncCursor.device_uuid == device.device_uuid,
        )
        .first()
    )

    if not cursor_rec:
        cursor_rec = SyncCursor(
            user_id=current_user.id,
            device_uuid=device.device_uuid,
            last_pulled_cursor=cursor,
            last_sync_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(cursor_rec)
    else:
        cursor_rec.last_pulled_cursor = max(cursor_rec.last_pulled_cursor, cursor)
        cursor_rec.last_sync_at = now
        cursor_rec.updated_at = now

    device.last_synced_at = now
    db.commit()

    return SyncAcknowledgeResponse(
        acknowledged=True,
        device_uuid=device.device_uuid,
        last_pulled_cursor=cursor_rec.last_pulled_cursor,
        acknowledged_at=now,
    )


def record_conflict(
    db: Session,
    current_user: User,
    device: Device,
    req: SyncConflictRecordRequest,
) -> SyncConflictItem:
    """
    Registers or updates a synchronization conflict record on the server.
    Enforces user isolation and device ownership.
    """
    now = utc_now()
    existing = (
        db.query(SyncConflict)
        .filter(SyncConflict.id == req.id, SyncConflict.user_id == current_user.id)
        .first()
    )
    if not existing:
        existing = SyncConflict(
            id=req.id,
            user_id=current_user.id,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            base_version=req.base_version,
            local_version=req.local_version,
            remote_version=req.remote_version,
            detecting_device_uuid=device.device_uuid,
            conflicting_device_uuid=req.conflicting_device_uuid,
            status="PENDING_RESOLUTION",
            local_data=req.local_data,
            remote_data=req.remote_data,
            detected_at=now,
        )
        db.add(existing)
    else:
        existing.local_version = req.local_version
        existing.remote_version = req.remote_version
        existing.local_data = req.local_data
        existing.remote_data = req.remote_data

    db.commit()
    db.refresh(existing)
    return SyncConflictItem.model_validate(existing)


def resolve_server_conflict(
    db: Session,
    current_user: User,
    device: Device,
    conflict_id: str,
    req: SyncConflictResolveRequest,
) -> SyncConflictItem:
    """
    Resolves a server-side conflict record using the selected strategy.
    Enforces that devices cannot resolve conflicts belonging to another account.
    Propagates resolved mutations and increments canonical entity versions.
    """
    now = utc_now()
    conflict = (
        db.query(SyncConflict)
        .filter(SyncConflict.id == conflict_id)
        .first()
    )
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict '{conflict_id}' not found.",
        )

    # Strictly enforce account isolation
    if conflict.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conflict belongs to a different account. Cross-tenant conflict resolution is forbidden.",
        )

    strategy = req.strategy.upper()
    if strategy not in ("KEEP_LOCAL", "KEEP_REMOTE", "MANUAL_MERGE"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resolution strategy '{req.strategy}'. Must be KEEP_LOCAL, KEEP_REMOTE, or MANUAL_MERGE.",
        )

    status_map = {
        "KEEP_LOCAL": "RESOLVED_LOCAL",
        "KEEP_REMOTE": "RESOLVED_REMOTE",
        "MANUAL_MERGE": "RESOLVED_MERGED",
    }
    conflict.status = status_map[strategy]
    conflict.resolution_strategy = strategy
    conflict.resolved_at = now
    if req.resolved_data:
        conflict.resolved_data = req.resolved_data

    # If local or merged winner was chosen, ensure canonical version is bumped and mutation applied
    if strategy in ("KEEP_LOCAL", "MANUAL_MERGE") and req.resolved_data:
        import uuid
        winning_payload = req.resolved_data
        sync_ev = (
            db.query(SyncEntityVersion)
            .filter(
                SyncEntityVersion.user_id == current_user.id,
                SyncEntityVersion.entity_type == conflict.entity_type,
                SyncEntityVersion.entity_id == conflict.entity_id,
            )
            .first()
        )
        target_version = (sync_ev.current_version + 1) if sync_ev else max(conflict.local_version, conflict.remote_version) + 1

        if not sync_ev:
            sync_ev = SyncEntityVersion(
                user_id=current_user.id,
                entity_type=conflict.entity_type,
                entity_id=conflict.entity_id,
                current_version=target_version,
                last_modified_device=device.device_uuid,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            )
            db.add(sync_ev)
        else:
            sync_ev.current_version = target_version
            sync_ev.last_modified_device = device.device_uuid
            sync_ev.is_deleted = False
            sync_ev.updated_at = now

        # Apply to domain model
        _apply_entity_mutation(
            db=db,
            user_id=current_user.id,
            entity_type=conflict.entity_type,
            entity_id=conflict.entity_id,
            operation_type="UPDATE",
            version=target_version,
            payload=winning_payload,
        )

        # Broadcast as append-only sync operation so other devices pull it
        res_op = SyncOperation(
            operation_uuid=f"res-{uuid.uuid4()}",
            user_id=current_user.id,
            device_uuid=device.device_uuid,
            entity_type=conflict.entity_type,
            entity_id=conflict.entity_id,
            operation_type="UPDATE",
            entity_version=target_version,
            payload=winning_payload,
            client_created_at=now,
            received_at=now,
            processed_at=now,
            status="APPLIED",
        )
        db.add(res_op)

    db.commit()
    db.refresh(conflict)
    return SyncConflictItem.model_validate(conflict)


def list_user_conflicts(
    db: Session,
    current_user: User,
    status_filter: Optional[str] = None,
    entity_type_filter: Optional[str] = None,
) -> SyncConflictListResponse:
    """
    Lists conflict records for the authenticated user with optional status and entity filtering.
    """
    q = db.query(SyncConflict).filter(SyncConflict.user_id == current_user.id)
    if status_filter:
        q = q.filter(SyncConflict.status == status_filter.upper())
    if entity_type_filter:
        q = q.filter(SyncConflict.entity_type == entity_type_filter.lower())

    records = q.order_by(SyncConflict.detected_at.desc()).all()
    unresolved_count = (
        db.query(SyncConflict)
        .filter(
            SyncConflict.user_id == current_user.id,
            SyncConflict.status == "PENDING_RESOLUTION",
        )
        .count()
    )

    items = [SyncConflictItem.model_validate(rec) for rec in records]
    return SyncConflictListResponse(
        conflicts=items,
        total_unresolved=unresolved_count,
    )
