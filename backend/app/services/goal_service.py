import time
from datetime import date, datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from backend.app.models.goal import Goal
from backend.app.models.task import Task
from backend.app.schemas.goal import GoalCreate, GoalUpdate, GoalResponse

def generate_goal_id() -> str:
    return f"g-{int(time.time() * 1000)}"

def get_goal_task_counts(db: Session, goal_id: str) -> tuple[int, int]:
    total = db.query(func.count(Task.id)).filter(Task.goal_id == goal_id).scalar() or 0
    completed = (
        db.query(func.count(Task.id))
        .filter(Task.goal_id == goal_id, Task.status == "Completed")
        .scalar()
        or 0
    )
    return total, completed

def get_goals(
    db: Session,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    goal_type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[str] = None,
) -> List[GoalResponse]:
    query = db.query(Goal).options(joinedload(Goal.tasks)).filter(Goal.is_deleted == False)
    if user_id:
        query = query.filter(Goal.user_id == user_id)

    if status:
        query = query.filter(Goal.status == status)
    if priority:
        query = query.filter(Goal.priority == priority)
    if goal_type:
        query = query.filter(Goal.goal_type == goal_type)
    if category:
        query = query.filter(Goal.category == category)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Goal.title.ilike(search_pattern),
                Goal.description.ilike(search_pattern),
                Goal.key_milestone.ilike(search_pattern),
            )
        )

    # Order: In Progress/On Track first, then target_date ascending
    goals = query.order_by(Goal.target_date.asc(), Goal.created_at.desc()).offset(skip).limit(limit).all()

    responses = []
    for g in goals:
        total_tasks = len(g.tasks) if g.tasks else 0
        completed_tasks = sum(1 for t in g.tasks if t.status == "Completed") if g.tasks else 0
        responses.append(GoalResponse.from_orm_model(g, total_tasks=total_tasks, completed_tasks=completed_tasks))
    return responses

def get_goal_by_id(db: Session, goal_id: str, user_id: Optional[str] = None) -> Optional[GoalResponse]:
    query = db.query(Goal).options(joinedload(Goal.tasks)).filter(Goal.id == goal_id, Goal.is_deleted == False)
    if user_id:
        query = query.filter(Goal.user_id == user_id)
    goal = query.first()
    if not goal:
        return None
    total_tasks = len(goal.tasks) if goal.tasks else 0
    completed_tasks = sum(1 for t in goal.tasks if t.status == "Completed") if goal.tasks else 0
    return GoalResponse.from_orm_model(goal, total_tasks=total_tasks, completed_tasks=completed_tasks)

def create_goal(db: Session, goal_in: GoalCreate, user_id: Optional[str] = None) -> GoalResponse:
    goal_id = goal_in.id or generate_goal_id()
    now = datetime.now(timezone.utc)

    goal = Goal(
        id=goal_id,
        user_id=user_id or "default_user",
        title=goal_in.title.strip(),
        description=goal_in.description.strip() if goal_in.description else "",
        goal_type=goal_in.goal_type,
        category=goal_in.category,
        priority=goal_in.priority,
        status=goal_in.status,
        start_date=goal_in.start_date,
        target_date=goal_in.target_date,
        progress=goal_in.progress,
        key_milestone=goal_in.key_milestone.strip() if goal_in.key_milestone else "",
        version=1,
        is_deleted=False,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalResponse.from_orm_model(goal, total_tasks=0, completed_tasks=0)

def update_goal(db: Session, goal_id: str, goal_in: GoalUpdate, user_id: Optional[str] = None) -> Optional[GoalResponse]:
    query = db.query(Goal).filter(Goal.id == goal_id, Goal.is_deleted == False)
    if user_id:
        query = query.filter(Goal.user_id == user_id)
    goal = query.first()
    if not goal:
        return None

    update_data = goal_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(goal, field, val)

    goal.version = (goal.version or 1) + 1
    goal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(goal)
    
    total, completed = get_goal_task_counts(db, goal_id)
    return GoalResponse.from_orm_model(goal, total_tasks=total, completed_tasks=completed)

def delete_goal(db: Session, goal_id: str, user_id: Optional[str] = None) -> bool:
    query = db.query(Goal).filter(Goal.id == goal_id, Goal.is_deleted == False)
    if user_id:
        query = query.filter(Goal.user_id == user_id)
    goal = query.first()
    if not goal:
        return False
    # Unlink associated tasks
    db.query(Task).filter(Task.goal_id == goal_id).update({"goal_id": None})
    now_utc = datetime.now(timezone.utc)
    goal.is_deleted = True
    goal.deleted_at = now_utc
    goal.version = (goal.version or 1) + 1
    goal.updated_at = now_utc
    db.commit()
    return True

def update_goal_progress(
    db: Session,
    goal_id: str,
    progress: int,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[GoalResponse]:
    query = db.query(Goal).filter(Goal.id == goal_id, Goal.is_deleted == False)
    if user_id:
        query = query.filter(Goal.user_id == user_id)
    goal = query.first()
    if not goal:
        return None

    goal.progress = progress
    if status:
        goal.status = status
    elif progress == 100:
        goal.status = "Completed"

    goal.version = (goal.version or 1) + 1
    goal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(goal)

    total, completed = get_goal_task_counts(db, goal_id)
    return GoalResponse.from_orm_model(goal, total_tasks=total, completed_tasks=completed)
