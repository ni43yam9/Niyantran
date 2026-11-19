from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.schemas.task import TaskResponse
from backend.app.schemas.dashboard import DashboardSummaryResponse, DashboardMetrics

CATEGORY_COLORS = {
    "Coding": "#6366F1",
    "Academic": "#3B82F6",
    "Career": "#10B981",
    "Reading": "#06B6D4",
    "Health": "#F59E0B",
    "Personal": "#8B5CF6",
    "Technical": "#6366F1",
}

def get_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    today = date.today()

    total_tasks = db.query(func.count(Task.id)).scalar() or 0
    completed_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.status == "Completed")
        .scalar()
        or 0
    )
    pending_tasks = total_tasks - completed_tasks
    active_goals = (
        db.query(func.count(Goal.id))
        .filter(Goal.status != "Completed")
        .scalar()
        or 0
    )
    completion_rate = (
        round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    )
    overdue_count = (
        db.query(func.count(Task.id))
        .filter(and_(Task.status != "Completed", Task.due_date < today))
        .scalar()
        or 0
    )
    due_today_count = (
        db.query(func.count(Task.id))
        .filter(and_(Task.status != "Completed", Task.due_date == today))
        .scalar()
        or 0
    )

    metrics = DashboardMetrics(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        active_goals=active_goals,
        completion_rate=completion_rate,
        overdue_count=overdue_count,
        due_today_count=due_today_count,
    )

    # Tasks due today or starting today
    tasks_today_orm = (
        db.query(Task)
        .filter(or_(Task.due_date == today, Task.start_date == today))
        .order_by(Task.status.desc(), Task.priority.asc())
        .limit(20)
        .all()
    )
    tasks_due_today = [TaskResponse.from_orm_model(t) for t in tasks_today_orm]

    # Top priorities
    high_tasks = (
        db.query(Task)
        .filter(and_(Task.priority == "High", Task.status != "Completed"))
        .order_by(Task.due_date.asc())
        .limit(3)
        .all()
    )
    top_priorities: List[Dict[str, Any]] = [
        {
            "id": f"p-{t.id}",
            "title": t.title,
            "reason": t.description or "High-priority active deliverable",
            "priority": t.priority,
            "category": t.category,
            "progress": 50 if t.status == "In Progress" else 20,
        }
        for t in high_tasks
    ]

    if len(top_priorities) < 3:
        needed = 3 - len(top_priorities)
        high_goals = (
            db.query(Goal)
            .filter(and_(Goal.priority == "High", Goal.status != "Completed"))
            .order_by(Goal.target_date.asc())
            .limit(needed)
            .all()
        )
        for g in high_goals:
            top_priorities.append(
                {
                    "id": f"pg-{g.id}",
                    "title": g.title,
                    "reason": g.key_milestone or g.description or "High-priority goal milestone",
                    "priority": g.priority,
                    "category": g.category,
                    "progress": g.progress or 30,
                }
            )

    # Category distribution
    cat_counts = (
        db.query(Task.category, func.count(Task.id))
        .group_by(Task.category)
        .all()
    )
    category_distribution: List[Dict[str, Any]] = [
        {
            "name": "Coding & Tech" if cat == "Coding" else cat,
            "value": count,
            "color": CATEGORY_COLORS.get(cat, "#64748B"),
        }
        for cat, count in cat_counts
    ]

    return DashboardSummaryResponse(
        metrics=metrics,
        tasks_due_today=tasks_due_today,
        top_priorities=top_priorities,
        category_distribution=category_distribution,
    )
