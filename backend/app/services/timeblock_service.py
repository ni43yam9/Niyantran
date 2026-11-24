import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.timeblock import DailyTimeblock
from backend.app.schemas.timeblock import TimeblockCreate, TimeblockUpdate, TimeblockResponse

def _format_block_response(block: DailyTimeblock) -> TimeblockResponse:
    return TimeblockResponse.model_validate(block)

def get_timeblocks(
    db: Session,
    block_date: Optional[date] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
) -> List[TimeblockResponse]:
    query = db.query(DailyTimeblock).filter(DailyTimeblock.is_deleted == False)
    if block_date:
        query = query.filter(DailyTimeblock.block_date == block_date)
    if status:
        query = query.filter(DailyTimeblock.status == status)
    if category:
        query = query.filter(DailyTimeblock.category == category)

    blocks = query.order_by(DailyTimeblock.block_date.asc(), DailyTimeblock.time.asc()).all()
    return [_format_block_response(b) for b in blocks]

def get_timeblock_by_id(db: Session, block_id: str) -> Optional[TimeblockResponse]:
    block = db.query(DailyTimeblock).filter(DailyTimeblock.id == block_id, DailyTimeblock.is_deleted == False).first()
    if not block:
        return None
    return _format_block_response(block)

def create_timeblock(db: Session, block_in: TimeblockCreate) -> TimeblockResponse:
    block_id = block_in.id or f"blk_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:4]}"
    
    block = DailyTimeblock(
        id=block_id,
        block_date=block_in.block_date,
        title=block_in.title,
        time=block_in.time,
        duration_minutes=block_in.duration_minutes,
        actual_duration_minutes=block_in.actual_duration_minutes,
        category=block_in.category or "General",
        status=block_in.status or "Pending",
        is_break=block_in.is_break,
        task_id=block_in.task_id,
    )
    db.add(block)
    db.commit()
    db.refresh(block)

    try:
        from backend.app.services.behaviour_service import record_activity
        record_activity(
            db,
            event_type="DAILY_PLAN_CREATED",
            entity_type="timeblock",
            entity_id=block.id,
            new_date=block.block_date,
            duration_minutes=block.duration_minutes,
            actual_duration_minutes=block.actual_duration_minutes,
            details={"title": block.title, "category": block.category},
        )
    except Exception as e:
        import logging
        logging.getLogger("niyantra").warning(f"Timeblock create activity log fallback: {e}")

    return _format_block_response(block)

def update_timeblock(db: Session, block_id: str, block_in: TimeblockUpdate) -> Optional[TimeblockResponse]:
    block = db.query(DailyTimeblock).filter(DailyTimeblock.id == block_id, DailyTimeblock.is_deleted == False).first()
    if not block:
        return None

    old_status = block.status
    old_date = block.block_date
    update_data = block_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(block, field, val)

    block.version = (block.version or 1) + 1
    block.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(block)

    try:
        from backend.app.services.behaviour_service import record_activity
        # Status change to In Progress
        if block.status == "In Progress" and old_status != "In Progress":
            record_activity(
                db,
                event_type="PLANNED_TASK_STARTED",
                entity_type="timeblock",
                entity_id=block.id,
                duration_minutes=block.duration_minutes,
                details={"title": block.title},
            )
        # Status change to Completed
        elif block.status == "Completed" and old_status != "Completed":
            record_activity(
                db,
                event_type="PLANNED_TASK_FINISHED",
                entity_type="timeblock",
                entity_id=block.id,
                duration_minutes=block.duration_minutes,
                actual_duration_minutes=block.actual_duration_minutes,
                details={"title": block.title, "category": block.category},
            )
        # Date change (shifting/postponing block)
        if block.block_date and old_date and block.block_date > old_date:
            record_activity(
                db,
                event_type="TIMEBLOCK_SHIFTED",
                entity_type="timeblock",
                entity_id=block.id,
                original_date=old_date,
                new_date=block.block_date,
                details={"title": block.title},
            )
    except Exception as e:
        import logging
        logging.getLogger("niyantra").warning(f"Timeblock update activity log fallback: {e}")

    return _format_block_response(block)

def delete_timeblock(db: Session, block_id: str) -> bool:
    block = db.query(DailyTimeblock).filter(DailyTimeblock.id == block_id, DailyTimeblock.is_deleted == False).first()
    if not block:
        return False
    now_utc = datetime.now(timezone.utc)
    block.is_deleted = True
    block.deleted_at = now_utc
    block.version = (block.version or 1) + 1
    block.updated_at = now_utc
    db.commit()
    return True

def get_planned_vs_actual_analytics(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Computes Planned vs Actual focus hours grouped by category.
    Directly powers Recommendation 5: Planned vs Actual Productivity Insights.
    """
    query = db.query(
        DailyTimeblock.category,
        func.sum(DailyTimeblock.duration_minutes).label("planned_mins"),
        func.sum(
            func.coalesce(DailyTimeblock.actual_duration_minutes, DailyTimeblock.duration_minutes)
        ).label("actual_mins"),
        func.count(DailyTimeblock.id).label("total_blocks"),
    ).filter(DailyTimeblock.is_break == False)

    if start_date:
        query = query.filter(DailyTimeblock.block_date >= start_date)
    if end_date:
        query = query.filter(DailyTimeblock.block_date <= end_date)

    rows = query.group_by(DailyTimeblock.category).all()
    results = []
    for r in rows:
        planned_hrs = round((r.planned_mins or 0) / 60.0, 1)
        actual_hrs = round((r.actual_mins or 0) / 60.0, 1)
        variance_hrs = round(actual_hrs - planned_hrs, 1)
        results.append({
            "category": r.category,
            "plannedHours": planned_hrs,
            "actualHours": actual_hrs,
            "varianceHours": variance_hrs,
            "underestimated": actual_hrs > planned_hrs,
            "totalBlocks": r.total_blocks,
        })
    return results
