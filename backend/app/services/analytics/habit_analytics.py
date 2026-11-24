import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.schemas.analytics import HabitAnalyticsDetail

logger = logging.getLogger(__name__)

def analyze_habits_in_depth(
    db: Session,
    reference_date: Optional[date] = None,
) -> HabitAnalyticsDetail:
    """
    Performs comprehensive habit execution analytics across 7d, 14d, and 30d adherence windows,
    streak durability, missed-day patterns, and behavioral trends.
    """
    today = reference_date or date.today()
    habits = db.query(Habit).filter(Habit.archived == False).all()
    total_habits = len(habits)

    if total_habits == 0:
        return HabitAnalyticsDetail(
            total_habits=0,
            active_habits=0,
            adherence_7d=0.0,
            adherence_14d=0.0,
            adherence_30d=0.0,
            longest_streak=0,
            active_streaks_count=0,
            missed_days_last_4d=0,
            habit_trend="Insufficient Data",
            has_sufficient_data=False,
            summary="No active habits configured in system.",
        )

    # Date boundaries
    start_7d = today - timedelta(days=7)
    start_14d = today - timedelta(days=14)
    start_30d = today - timedelta(days=30)
    start_4d = today - timedelta(days=4)

    # 1. Adherence metrics
    logs_7d = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= start_7d)
        .scalar()
        or 0
    )
    logs_14d = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= start_14d)
        .scalar()
        or 0
    )
    logs_30d = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= start_30d)
        .scalar()
        or 0
    )

    possible_7d = total_habits * 7
    possible_14d = total_habits * 14
    possible_30d = total_habits * 30

    adherence_7d = round((logs_7d / max(1, possible_7d)) * 100.0, 1)
    adherence_14d = round((logs_14d / max(1, possible_14d)) * 100.0, 1)
    adherence_30d = round((logs_30d / max(1, possible_30d)) * 100.0, 1)

    # 2. Streaks
    longest_streak = 0
    active_streaks = 0
    for h in habits:
        streak = getattr(h, "streak_count", 0) or getattr(h, "base_streak", 0) or 0
        if streak > 0:
            active_streaks += 1
        if streak > longest_streak:
            longest_streak = streak

    # 3. Missed days in last 4 days
    logs_4d = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= start_4d)
        .scalar()
        or 0
    )
    possible_4d = total_habits * 4
    missed_4d = max(0, possible_4d - logs_4d)

    # 4. Trend Determination (7d vs 14d)
    total_logs = db.query(func.count(HabitLog.id)).scalar() or 0
    if total_logs < 3:
        habit_trend = "Insufficient Data"
    elif adherence_7d > adherence_14d + 5.0:
        habit_trend = "Improving"
    elif adherence_7d < adherence_14d - 10.0:
        habit_trend = "Declining"
    else:
        habit_trend = "Steady"

    has_data = total_logs >= 3 or longest_streak >= 3
    summary = (
        f"{total_habits} active habits with {adherence_7d}% 7-day adherence and {adherence_30d}% 30-day consistency. "
        f"{active_streaks} active streaks (longest: {longest_streak} days). Trend: {habit_trend}."
    )

    return HabitAnalyticsDetail(
        total_habits=total_habits,
        active_habits=total_habits,
        adherence_7d=adherence_7d,
        adherence_14d=adherence_14d,
        adherence_30d=adherence_30d,
        longest_streak=longest_streak,
        active_streaks_count=active_streaks,
        missed_days_last_4d=missed_4d,
        habit_trend=habit_trend,
        has_sufficient_data=has_data,
        summary=summary,
    )
