import uuid
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.task import Task
from backend.app.models.timeblock import DailyTimeblock
from backend.app.schemas.adaptive import (
    SchedulingSuggestion,
    AdaptiveSchedulingResponse,
    WorkingPeriodsPattern,
    WorkloadTolerancePattern,
)

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def generate_adaptive_scheduling_suggestions(
    db: Session,
    working_periods: WorkingPeriodsPattern,
    workload_tolerance: WorkloadTolerancePattern,
    reference_date: Optional[date] = None,
) -> AdaptiveSchedulingResponse:
    """
    Generates intelligent, non-destructive scheduling recommendations based on
    learned personal productivity profile and energy patterns.
    STRICT INVARIANT: Never mutates task dates or timeblocks automatically.
    User approval is strictly required.
    """
    today = reference_date or date.today()
    peak_window = working_periods.peak_time_window if working_periods.has_sufficient_data else "Morning"
    optimal_load = workload_tolerance.optimal_daily_load_minutes

    # Query active pending tasks
    pending_tasks = (
        db.query(Task)
        .filter(Task.status != "Completed")
        .order_by(Task.due_date.asc())
        .all()
    )

    # Query scheduled timeblocks over next 7 days
    forward_dates = [today + timedelta(days=i) for i in range(7)]
    timeblocks = (
        db.query(DailyTimeblock)
        .filter(DailyTimeblock.block_date.in_(forward_dates))
        .all()
    )

    # Calculate daily load
    daily_load_minutes: Dict[date, int] = {d: 0 for d in forward_dates}
    daily_tasks: Dict[date, List[Task]] = {d: [] for d in forward_dates}

    for tb in timeblocks:
        dur = tb.duration_minutes or 60
        daily_load_minutes[tb.block_date] = daily_load_minutes.get(tb.block_date, 0) + dur

    for t in pending_tasks:
        if t.due_date and t.due_date in daily_tasks:
            daily_tasks[t.due_date].append(t)
            # Add estimated 60m if not already in timeblock
            daily_load_minutes[t.due_date] = daily_load_minutes.get(t.due_date, 0) + 60

    suggestions: List[SchedulingSuggestion] = []

    # 1. Energy Window Alignment for Complex / High-Priority Tasks
    high_impact_categories = {"Coding", "Academic", "Career"}
    aligned_task_ids = set()

    for t in pending_tasks:
        if len(suggestions) >= 8:
            break
        is_high_impact = (t.priority == "High") or (t.category in high_impact_categories)
        if is_high_impact and t.due_date and t.due_date >= today:
            sugg_id = f"sugg_energy_{t.id[:8]}_{uuid.uuid4().hex[:4]}"
            target_window = f"{peak_window} (08:30 - 11:30)" if peak_window == "Morning" else f"{peak_window} (13:30 - 16:30)"
            evidence = [
                f"Task '{t.title}' is high-impact (Priority: {t.priority}, Category: {t.category}).",
                f"Learned peak productivity window: '{peak_window}' (Confidence: {working_periods.confidence:.2f}).",
            ]
            suggestions.append(
                SchedulingSuggestion(
                    id=sugg_id,
                    suggestion_type="ENERGY_WINDOW_ALIGNMENT",
                    task_id=t.id,
                    task_title=t.title,
                    current_date=t.due_date,
                    suggested_date=t.due_date,
                    suggested_window=target_window,
                    confidence_score=working_periods.confidence,
                    reason=f"Align complex deliverable '{t.title}' with your peak cognitive focus window ({peak_window}).",
                    evidence=evidence,
                    requires_user_approval=True,
                )
            )
            aligned_task_ids.add(t.id)

    # 2. Low-Energy Micro-Task Alignment
    for t in pending_tasks:
        if len(suggestions) >= 8:
            break
        if t.id in aligned_task_ids:
            continue
        is_micro_task = (t.priority == "Low") or (t.category == "Personal")
        if is_micro_task and t.due_date and t.due_date >= today:
            sugg_id = f"sugg_micro_{t.id[:8]}_{uuid.uuid4().hex[:4]}"
            low_energy_window = "Afternoon (14:00 - 15:30)" if peak_window == "Morning" else "Evening (17:00 - 18:30)"
            evidence = [
                f"Task '{t.title}' is low urgency/effort (Priority: {t.priority}, Category: {t.category}).",
                f"Reserves prime {peak_window} blocks for high-cognitive work.",
            ]
            suggestions.append(
                SchedulingSuggestion(
                    id=sugg_id,
                    suggestion_type="LOW_ENERGY_MICRO_TASK",
                    task_id=t.id,
                    task_title=t.title,
                    current_date=t.due_date,
                    suggested_date=t.due_date,
                    suggested_window=low_energy_window,
                    confidence_score=0.85,
                    reason=f"Schedule administrative or lightweight task '{t.title}' during secondary energy window ({low_energy_window}).",
                    evidence=evidence,
                    requires_user_approval=True,
                )
            )

    # 3. Workload Redistribution & Overload Prevention
    # Find overloaded days vs light days
    light_days = [d for d in forward_dates if daily_load_minutes[d] < 180 and d > today]

    for d in forward_dates:
        if len(suggestions) >= 8:
            break
        load = daily_load_minutes.get(d, 0)
        if load > optimal_load and light_days:
            # Day is overloaded; find movable non-high priority task
            day_tasks = daily_tasks.get(d, [])
            movable_tasks = [t for t in day_tasks if t.priority != "High"]
            if movable_tasks:
                task_to_move = movable_tasks[0]
                target_day = light_days[0]
                sugg_id = f"sugg_redist_{task_to_move.id[:8]}_{uuid.uuid4().hex[:4]}"
                evidence = [
                    f"Scheduled load on {d} ({load}m) exceeds calibrated capacity ({optimal_load}m).",
                    f"Target day {target_day} has surplus capacity ({daily_load_minutes[target_day]}m planned).",
                ]
                suggestions.append(
                    SchedulingSuggestion(
                        id=sugg_id,
                        suggestion_type="WORKLOAD_REDISTRIBUTION",
                        task_id=task_to_move.id,
                        task_title=task_to_move.title,
                        current_date=d,
                        suggested_date=target_day,
                        suggested_window=f"{peak_window} (Available Capacity)",
                        confidence_score=0.80,
                        reason=f"Redistribute '{task_to_move.title}' from overloaded day {d} ({load}m) to light day {target_day}.",
                        evidence=evidence,
                        requires_user_approval=True,
                    )
                )

    summary_msg = (
        f"Generated {len(suggestions)} adaptive scheduling suggestions aligned with '{peak_window}' "
        f"peak productivity and {optimal_load}m sustainable daily capacity."
    )

    return AdaptiveSchedulingResponse(
        peak_time_window=peak_window,
        optimal_daily_load_minutes=optimal_load,
        suggestions=suggestions,
        total_suggestions=len(suggestions),
        summary=summary_msg,
    )
