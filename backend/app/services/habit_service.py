import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.schemas.habit import HabitCreate, HabitUpdate, HabitResponse, HabitLogResponse

def _format_habit_response(habit: Habit) -> HabitResponse:
    completed_dates: Dict[str, bool] = {}
    logs_resp = []
    if habit.logs:
        for log in habit.logs:
            if getattr(log, "is_deleted", False):
                continue
            date_str = log.log_date.isoformat()
            if log.completed:
                completed_dates[date_str] = True
            logs_resp.append(HabitLogResponse.model_validate(log))

    return HabitResponse(
        id=habit.id,
        name=habit.name,
        target=habit.target,
        category=habit.category,
        frequency=habit.frequency,
        base_streak=habit.base_streak,
        archived=habit.archived,
        created_at=habit.created_at,
        updated_at=habit.updated_at,
        completed_dates=completed_dates,
        logs=logs_resp,
    )

def get_habits(db: Session, include_archived: bool = False, user_id: Optional[str] = None) -> List[HabitResponse]:
    query = db.query(Habit).filter(Habit.is_deleted == False)
    if user_id:
        query = query.filter(Habit.user_id == user_id)
    if not include_archived:
        query = query.filter(Habit.archived == False)
    habits = query.order_by(Habit.created_at.asc()).all()
    return [_format_habit_response(h) for h in habits]

def get_habit_by_id(db: Session, habit_id: str, user_id: Optional[str] = None) -> Optional[HabitResponse]:
    query = db.query(Habit).filter(Habit.id == habit_id, Habit.is_deleted == False)
    if user_id:
        query = query.filter(Habit.user_id == user_id)
    habit = query.first()
    if not habit:
        return None
    return _format_habit_response(habit)

def create_habit(db: Session, habit_in: HabitCreate, user_id: Optional[str] = None) -> HabitResponse:
    habit_id = habit_in.id or f"h-{uuid.uuid4().hex[:8]}"
    
    habit = Habit(
        id=habit_id,
        user_id=user_id or "default_user",
        name=habit_in.name,
        target=habit_in.target,
        category=habit_in.category or "General",
        frequency=habit_in.frequency or "Daily",
        base_streak=habit_in.base_streak,
        archived=False,
    )
    db.add(habit)
    db.flush()

    # If completed_dates dictionary is provided, insert logs
    if habit_in.completed_dates:
        for date_str, is_done in habit_in.completed_dates.items():
            if is_done:
                try:
                    d = date.fromisoformat(date_str)
                    log = HabitLog(
                        id=f"hl-{uuid.uuid4().hex[:12]}",
                        user_id=user_id or "default_user",
                        habit_id=habit.id,
                        log_date=d,
                        completed=True,
                    )
                    db.add(log)
                except ValueError:
                    continue

    db.commit()
    db.refresh(habit)
    return _format_habit_response(habit)

def update_habit(db: Session, habit_id: str, habit_in: HabitUpdate, user_id: Optional[str] = None) -> Optional[HabitResponse]:
    query = db.query(Habit).filter(Habit.id == habit_id, Habit.is_deleted == False)
    if user_id:
        query = query.filter(Habit.user_id == user_id)
    habit = query.first()
    if not habit:
        return None

    update_data = habit_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(habit, field, val)

    habit.version = (habit.version or 1) + 1
    habit.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(habit)
    return _format_habit_response(habit)

def delete_habit(db: Session, habit_id: str, soft_delete: bool = False, user_id: Optional[str] = None) -> bool:
    query = db.query(Habit).filter(Habit.id == habit_id)
    if user_id:
        query = query.filter(Habit.user_id == user_id)
    habit = query.first()
    if not habit:
        return False
    if soft_delete:
        now_utc = datetime.now(timezone.utc)
        habit.is_deleted = True
        habit.deleted_at = now_utc
        habit.version = (habit.version or 1) + 1
        habit.updated_at = now_utc
        # Soft delete associated habit logs
        db.query(HabitLog).filter(HabitLog.habit_id == habit_id).update({
            "is_deleted": True,
            "deleted_at": now_utc,
            "updated_at": now_utc,
        })
        db.commit()
        return True
    else:
        # Cascade delete for full schema compliance
        db.delete(habit)
        db.commit()
        return True

def soft_delete_habit(db: Session, habit_id: str, user_id: Optional[str] = None) -> bool:
    return delete_habit(db, habit_id, soft_delete=True, user_id=user_id)

def toggle_habit_log(db: Session, habit_id: str, log_date: date, completed: Optional[bool] = None, user_id: Optional[str] = None) -> Optional[HabitResponse]:
    query = db.query(Habit).filter(Habit.id == habit_id, Habit.is_deleted == False)
    if user_id:
        query = query.filter(Habit.user_id == user_id)
    habit = query.first()
    if not habit:
        return None

    existing_log = db.query(HabitLog).filter(
        HabitLog.habit_id == habit_id,
        HabitLog.log_date == log_date,
    ).first()

    now_utc = datetime.now(timezone.utc)
    final_completed = True
    if existing_log:
        if completed is not None:
            existing_log.completed = completed
        else:
            existing_log.completed = not existing_log.completed
        final_completed = existing_log.completed
        existing_log.version = (existing_log.version or 1) + 1
        existing_log.updated_at = now_utc
        existing_log.is_deleted = False
        existing_log.deleted_at = None
    else:
        new_val = completed if completed is not None else True
        new_log = HabitLog(
            id=f"hl-{uuid.uuid4().hex[:12]}",
            user_id=user_id or "default_user",
            habit_id=habit.id,
            log_date=log_date,
            completed=new_val,
            version=1,
            is_deleted=False,
            deleted_at=None,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(new_log)
        final_completed = new_val

    habit.version = (habit.version or 1) + 1
    habit.updated_at = now_utc
    db.commit()
    db.refresh(habit)

    try:
        from backend.app.services.behaviour_service import record_activity
        record_activity(
            db,
            event_type="HABIT_COMPLETED" if final_completed else "HABIT_MISSED",
            entity_type="habit",
            entity_id=habit.id,
            new_date=log_date,
            details={"habit_name": habit.name, "category": habit.category},
        )
    except Exception as e:
        import logging
        logging.getLogger("niyantra").warning(f"Habit activity logging fallback: {e}")

    return _format_habit_response(habit)
