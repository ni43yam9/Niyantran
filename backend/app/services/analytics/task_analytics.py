import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.analytics import TaskAnalyticsDetail

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def analyze_tasks_in_depth(
    db: Session,
    reference_date: Optional[date] = None,
) -> TaskAnalyticsDetail:
    """
    Performs comprehensive task execution analytics across categories,
    priority tiers, overdue debts, resolution lead times, and daily patterns.
    """
    today = reference_date or date.today()
    tasks = db.query(Task).all()
    total_tasks = len(tasks)

    completed_tasks = [t for t in tasks if t.status == "Completed"]
    pending_tasks = [t for t in tasks if t.status != "Completed"]
    overdue_tasks = [t for t in pending_tasks if t.due_date and t.due_date < today]

    total_completed = len(completed_tasks)
    total_pending = len(pending_tasks)
    total_overdue = len(overdue_tasks)

    # Postponement count
    postponed_count = (
        db.query(func.count(func.distinct(ActivityLog.entity_id)))
        .filter(ActivityLog.event_type == "TASK_POSTPONED")
        .scalar()
        or 0
    )

    completion_rate = round((total_completed / max(1, total_tasks)) * 100.0, 1) if total_tasks > 0 else 0.0

    # 1. Priority-Wise Completion Rates
    priority_total: Counter = Counter()
    priority_done: Counter = Counter()
    for t in tasks:
        p = t.priority or "Medium"
        priority_total[p] += 1
        if t.status == "Completed":
            priority_done[p] += 1

    priority_completion_rates: Dict[str, float] = {}
    for p in ["High", "Medium", "Low"]:
        tot = priority_total[p]
        done = priority_done[p]
        priority_completion_rates[p] = round((done / max(1, tot)) * 100.0, 1) if tot > 0 else 0.0

    # 2. Category-Wise Completion Rates
    cat_total: Counter = Counter()
    cat_done: Counter = Counter()
    for t in tasks:
        c = t.category or "General"
        cat_total[c] += 1
        if t.status == "Completed":
            cat_done[c] += 1

    category_completion_rates: Dict[str, float] = {}
    for c, tot in cat_total.items():
        done = cat_done[c]
        category_completion_rates[c] = round((done / max(1, tot)) * 100.0, 1)

    # 3. Daily Completion Pattern (Day of Week)
    day_counts: Dict[str, int] = {d: 0 for d in DAY_NAMES}
    durations_hours: List[float] = []

    for t in completed_tasks:
        if t.completed_at:
            day_name = DAY_NAMES[t.completed_at.weekday()]
            day_counts[day_name] += 1
            if t.created_at and t.completed_at >= t.created_at:
                durations_hours.append((t.completed_at - t.created_at).total_seconds() / 3600.0)

    avg_lead_time = round(sum(durations_hours) / len(durations_hours), 1) if durations_hours else None
    has_data = total_tasks >= 2

    summary = (
        f"Analyzed {total_tasks} deliverables ({total_completed} completed, {total_pending} pending, "
        f"{total_overdue} overdue). Overall completion rate: {completion_rate}%. "
        f"High-priority execution rate: {priority_completion_rates.get('High', 0.0)}%."
    )

    return TaskAnalyticsDetail(
        total_tasks=total_tasks,
        completed_tasks=total_completed,
        pending_tasks=total_pending,
        overdue_tasks=total_overdue,
        postponed_tasks=postponed_count,
        completion_rate=completion_rate,
        priority_completion_rates=priority_completion_rates,
        category_completion_rates=category_completion_rates,
        completions_by_day_of_week=day_counts,
        average_lead_time_hours=avg_lead_time,
        has_sufficient_data=has_data,
        summary=summary,
    )
