import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from collections import Counter
from sqlalchemy.orm import Session

from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.task import Task
from backend.app.schemas.analytics import TimeDistributionDetail
from backend.app.services.adaptive.confidence_manager import get_time_window_bucket

logger = logging.getLogger(__name__)

def analyze_time_distribution(
    db: Session,
    tz_offset_mins: int = 0,
) -> TimeDistributionDetail:
    """
    Analyzes duration metrics, planned versus actual tracking, deep-work sessions,
    and category breakdowns.
    CRITICAL INVARIANT: Strictly distinguishes estimated duration from tracked duration.
    Never invents or fabricates tracked actuals when only estimates exist.
    """
    timeblocks = db.query(DailyTimeblock).all()
    tasks = db.query(Task).all()

    # 1. Inspect Timeblocks for Tracked vs Estimated
    total_est_minutes = 0
    total_act_minutes = 0
    tracked_count = 0
    deep_work_mins = 0

    actual_vs_planned_ratios: List[float] = []
    category_durations: Dict[str, Dict[str, int]] = {}

    for tb in timeblocks:
        cat = tb.category or "General"
        category_durations.setdefault(cat, {"estimated_minutes": 0, "tracked_minutes": 0})

        est = tb.duration_minutes or 60
        total_est_minutes += est
        category_durations[cat]["estimated_minutes"] += est

        if tb.status == "Completed" and tb.actual_duration_minutes and tb.actual_duration_minutes > 0:
            act = tb.actual_duration_minutes
            total_act_minutes += act
            category_durations[cat]["tracked_minutes"] += act
            tracked_count += 1
            actual_vs_planned_ratios.append(float(act) / float(est))
            if act >= 45:
                deep_work_mins += act

    has_tracked_data = tracked_count > 0

    # 2. Add Task duration estimates (if task has no timeblock, default estimate is 60m)
    for t in tasks:
        t_cat = t.category or "General"
        category_durations.setdefault(t_cat, {"estimated_minutes": 0, "tracked_minutes": 0})
        # If task is not linked to any timeblock, account for estimated 60m
        has_tb = any(tb.task_id == t.id for tb in timeblocks)
        if not has_tb:
            total_est_minutes += 60
            category_durations[t_cat]["estimated_minutes"] += 60

    # 3. Estimation Bias
    if len(actual_vs_planned_ratios) >= 3:
        bias_ratio = round(sum(actual_vs_planned_ratios) / len(actual_vs_planned_ratios), 2)
        is_empirical = True
    else:
        bias_ratio = 1.25  # Standard heuristic
        is_empirical = False

    # 4. Working-Hour Diurnal Distribution
    window_counts: Counter = Counter()
    for tb in timeblocks:
        if tb.status == "Completed":
            win = get_time_window_bucket(tb.time)
            window_counts[win] += (tb.actual_duration_minutes or tb.duration_minutes or 60)

    for t in tasks:
        if t.status == "Completed" and t.completed_at:
            local_dt = t.completed_at + timedelta(minutes=tz_offset_mins)
            win = get_time_window_bucket(local_dt)
            window_counts[win] += 60

    working_hour_distribution = {
        "Morning": window_counts["Morning"],
        "Afternoon": window_counts["Afternoon"],
        "Evening": window_counts["Evening"],
        "Night": window_counts["Night"],
    }

    if has_tracked_data:
        data_notes = (
            f"Analyzed {total_est_minutes} estimated minutes across deliverables. "
            f"{total_act_minutes} minutes verified via empirical timeblock completion tracking "
            f"across {tracked_count} completed sessions."
        )
    else:
        data_notes = (
            f"Analyzed {total_est_minutes} estimated minutes based on planned task budgets. "
            "No empirical stopwatches or completed timeblock actuals logged yet. "
            "Tracked actual duration strictly reported as 0m until verified by user execution."
        )

    return TimeDistributionDetail(
        total_tracked_duration_minutes=total_act_minutes,
        total_estimated_duration_minutes=total_est_minutes,
        has_tracked_duration_data=has_tracked_data,
        estimation_bias_ratio=bias_ratio,
        is_bias_empirical=is_empirical,
        deep_work_focus_minutes=deep_work_mins,
        category_durations=category_durations,
        working_hour_distribution=working_hour_distribution,
        data_notes=data_notes,
    )
