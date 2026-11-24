import time
from datetime import date, datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

def generate_task_id() -> str:
    return f"t-{int(time.time() * 1000)}"

def get_tasks(
    db: Session,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    task_type: Optional[str] = None,
    search: Optional[str] = None,
    is_today: Optional[bool] = None,
    is_overdue: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[str] = None,
) -> List[TaskResponse]:
    query = db.query(Task).options(joinedload(Task.goal)).filter(Task.is_deleted == False)
    if user_id:
        query = query.filter(Task.user_id == user_id)
    today = date.today()

    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if category:
        query = query.filter(Task.category == category)
    if task_type:
        query = query.filter(Task.task_type == task_type)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern),
            )
        )
    if is_today is True:
        query = query.filter(or_(Task.due_date == today, Task.start_date == today))
    if is_overdue is True:
        query = query.filter(and_(Task.status != "Completed", Task.due_date < today))

    # Order: Pending/In Progress first, then high priority first, then due_date ascending
    tasks = query.order_by(
        Task.status.desc(),  # In SQLite, "Pending" / "In Progress" vs "Completed"
        Task.due_date.asc(),
        Task.created_at.desc(),
    ).offset(skip).limit(limit).all()

    return [TaskResponse.from_orm_model(t) for t in tasks]

def get_task_by_id(db: Session, task_id: str, user_id: Optional[str] = None) -> Optional[TaskResponse]:
    query = db.query(Task).options(joinedload(Task.goal)).filter(Task.id == task_id, Task.is_deleted == False)
    if user_id:
        query = query.filter(Task.user_id == user_id)
    task = query.first()
    if not task:
        return None
    return TaskResponse.from_orm_model(task)

def _safe_record_activity(db: Session, **kwargs):
    try:
        from backend.app.services.behaviour_service import record_activity
        record_activity(db, **kwargs)
    except Exception as e:
        import logging
        logging.getLogger("niyantra").warning(f"Activity logging fallback: {e}")

def create_task(db: Session, task_in: TaskCreate, user_id: Optional[str] = None) -> TaskResponse:
    task_id = task_in.id or generate_task_id()

    # Validate goal exists if goal_id provided
    goal_id = task_in.goal_id
    if goal_id:
        goal_exists = db.query(Goal.id).filter(Goal.id == goal_id).first()
        if not goal_exists:
            goal_id = None  # Detach invalid reference safely

    now = datetime.now(timezone.utc)
    completed_at = now if task_in.status == "Completed" else None

    task = Task(
        id=task_id,
        user_id=user_id or "default_user",
        title=task_in.title.strip(),
        description=task_in.description.strip() if task_in.description else "",
        task_type=task_in.task_type,
        category=task_in.category,
        priority=task_in.priority,
        status=task_in.status,
        start_date=task_in.start_date,
        due_date=task_in.due_date,
        goal_id=goal_id,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _safe_record_activity(
        db,
        event_type="TASK_CREATED",
        entity_type="task",
        entity_id=task.id,
        new_date=task.due_date,
        details={"title": task.title, "priority": task.priority, "category": task.category},
    )

    if task.status == "Completed":
        _safe_record_activity(
            db,
            event_type="TASK_COMPLETED",
            entity_type="task",
            entity_id=task.id,
            details={"title": task.title, "category": task.category},
        )

    return TaskResponse.from_orm_model(task)

def update_task(db: Session, task_id: str, task_in: TaskUpdate, user_id: Optional[str] = None) -> Optional[TaskResponse]:
    query = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False)
    if user_id:
        query = query.filter(Task.user_id == user_id)
    task = query.first()
    if not task:
        return None

    old_due_date = task.due_date
    old_status = task.status
    update_data = task_in.model_dump(exclude_unset=True)

    # Check goal_id validity if explicitly updated
    if "goal_id" in update_data and update_data["goal_id"] is not None:
        goal_exists = db.query(Goal.id).filter(Goal.id == update_data["goal_id"], Goal.is_deleted == False).first()
        if not goal_exists:
            update_data["goal_id"] = None

    # Handle status change completion timestamp
    if "status" in update_data:
        if update_data["status"] == "Completed" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif update_data["status"] != "Completed":
            task.completed_at = None

    for field, val in update_data.items():
        setattr(task, field, val)

    task.version = (task.version or 1) + 1
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    # Activity Logging for postponements and status transitions
    if task.due_date and old_due_date and task.due_date > old_due_date:
        _safe_record_activity(
            db,
            event_type="TASK_POSTPONED",
            entity_type="task",
            entity_id=task.id,
            original_date=old_due_date,
            new_date=task.due_date,
            details={"title": task.title, "old_due_date": old_due_date.isoformat(), "new_due_date": task.due_date.isoformat()},
        )

    if "status" in update_data:
        if update_data["status"] == "Completed" and old_status != "Completed":
            _safe_record_activity(
                db,
                event_type="TASK_COMPLETED",
                entity_type="task",
                entity_id=task.id,
                details={"title": task.title, "category": task.category},
            )
        elif old_status == "Completed" and update_data["status"] != "Completed":
            _safe_record_activity(
                db,
                event_type="TASK_REOPENED",
                entity_type="task",
                entity_id=task.id,
                details={"title": task.title, "status": update_data["status"]},
            )

    return TaskResponse.from_orm_model(task)

def delete_task(db: Session, task_id: str, user_id: Optional[str] = None) -> bool:
    query = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False)
    if user_id:
        query = query.filter(Task.user_id == user_id)
    task = query.first()
    if not task:
        return False
    from backend.app.models.timeblock import DailyTimeblock
    db.query(DailyTimeblock).filter(DailyTimeblock.task_id == task_id).update({"task_id": None})
    _safe_record_activity(
        db,
        event_type="TASK_DELETED",
        entity_type="task",
        entity_id=task_id,
        details={"title": task.title},
    )
    now_utc = datetime.now(timezone.utc)
    task.is_deleted = True
    task.deleted_at = now_utc
    task.version = (task.version or 1) + 1
    task.updated_at = now_utc
    db.commit()
    return True

def set_task_status(db: Session, task_id: str, status: str, user_id: Optional[str] = None) -> Optional[TaskResponse]:
    query = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False)
    if user_id:
        query = query.filter(Task.user_id == user_id)
    task = query.first()
    if not task:
        return None

    old_status = task.status
    task.status = status
    if status == "Completed":
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = None

    task.version = (task.version or 1) + 1
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    if status == "Completed" and old_status != "Completed":
        _safe_record_activity(
            db,
            event_type="TASK_COMPLETED",
            entity_type="task",
            entity_id=task.id,
            details={"title": task.title, "category": task.category},
        )
    elif old_status == "Completed" and status != "Completed":
        _safe_record_activity(
            db,
            event_type="TASK_REOPENED",
            entity_type="task",
            entity_id=task.id,
            details={"title": task.title, "status": status},
        )

    return TaskResponse.from_orm_model(task)
