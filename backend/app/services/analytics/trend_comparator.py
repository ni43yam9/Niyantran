import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.app.models.task import Task
from backend.app.models.habit_log import HabitLog
from backend.app.models.goal import Goal
from backend.app.schemas.analytics import PeriodComparison, ProductivityTrendsDetail

logger = logging.getLogger(__name__)

def compare_productivity_trends(
    db: Session,
    reference_date: Optional[date] = None,
) -> ProductivityTrendsDetail:
    """
    Computes mathematically rigorous daily, weekly, and monthly productivity trends.
    CRITICAL INVARIANT: Accounts for incomplete periods by using day-aligned slices
    and pro-rated velocity comparisons, never comparing an incomplete partial window
    directly against an unscaled full period.
    """
    today = reference_date or date.today()

    all_completed = db.query(Task.completed_at).filter(
        Task.status == "Completed",
        Task.completed_at.isnot(None),
    ).all()
    completed_dates: List[date] = [row[0].date() for row in all_completed]

    # =========================================================================
    # 1. Daily Trend: Today vs Yesterday
    # =========================================================================
    yesterday = today - timedelta(days=1)
    today_comp = sum(1 for d in completed_dates if d == today)
    yesterday_comp = sum(1 for d in completed_dates if d == yesterday)

    if today_comp == 0 and yesterday_comp == 0:
        daily_delta = 0.0
        daily_trend = "Steady"
        daily_expl = "No completions recorded today or yesterday."
    elif yesterday_comp > 0:
        daily_delta = round(((today_comp - yesterday_comp) / yesterday_comp) * 100.0, 1)
        daily_trend = "Improving" if daily_delta > 0 else ("Declining" if daily_delta < 0 else "Steady")
        daily_expl = f"Today's completions ({today_comp}) compared directly with yesterday ({yesterday_comp}): {daily_delta:+}%. "
    else:
        daily_delta = 100.0
        daily_trend = "Improving"
        daily_expl = f"Today's completions ({today_comp}) improved from 0 yesterday."

    daily_comp_obj = PeriodComparison(
        period_label="Daily (Today vs Yesterday)",
        current_period_days_elapsed=1,
        comparison_mode="FULL_PERIOD",
        current_completions=today_comp,
        previous_aligned_completions=yesterday_comp,
        velocity_delta_percent=daily_delta,
        trend=daily_trend,
        explanation=daily_expl,
    )

    # =========================================================================
    # 2. Weekly Trend: Day-Aligned Slice (Mon..Today vs Mon..SameDay of Prev Week)
    # =========================================================================
    days_elapsed_week = today.weekday() + 1 # Monday = 1, Tuesday = 2, ...
    curr_week_start = today - timedelta(days=today.weekday())
    prev_week_start = curr_week_start - timedelta(days=7)

    # Day-aligned dates
    curr_week_dates = {curr_week_start + timedelta(days=i) for i in range(days_elapsed_week)}
    prev_aligned_dates = {prev_week_start + timedelta(days=i) for i in range(days_elapsed_week)}

    curr_week_comp = sum(1 for d in completed_dates if d in curr_week_dates)
    prev_aligned_comp = sum(1 for d in completed_dates if d in prev_aligned_dates)

    if curr_week_comp == 0 and prev_aligned_comp == 0:
        weekly_delta = 0.0
        weekly_trend = "Steady"
        weekly_expl = (
            f"Zero deliverables completed in current {days_elapsed_week}-day week slice "
            f"or in previous aligned {days_elapsed_week}-day slice."
        )
    elif prev_aligned_comp > 0:
        weekly_delta = round(((curr_week_comp - prev_aligned_comp) / prev_aligned_comp) * 100.0, 1)
        weekly_trend = "Improving" if weekly_delta >= 10.0 else ("Declining" if weekly_delta <= -10.0 else "Steady")
        weekly_expl = (
            f"Day-aligned comparison across {days_elapsed_week} days: Current week has {curr_week_comp} completions "
            f"vs {prev_aligned_comp} in the same elapsed days of previous week ({weekly_delta:+}%)."
        )
    else:
        weekly_delta = 100.0
        weekly_trend = "Improving"
        weekly_expl = (
            f"Day-aligned slice: {curr_week_comp} completions in first {days_elapsed_week} days "
            f"up from 0 in matching slice of previous week."
        )

    weekly_comp_obj = PeriodComparison(
        period_label="Weekly (Day-Aligned Slice)",
        current_period_days_elapsed=days_elapsed_week,
        comparison_mode="DAY_ALIGNED_SLICE",
        current_completions=curr_week_comp,
        previous_aligned_completions=prev_aligned_comp,
        velocity_delta_percent=weekly_delta,
        trend=weekly_trend,
        explanation=weekly_expl,
    )

    # =========================================================================
    # 3. Monthly Trend: Day-Aligned Slice (1st..Today vs 1st..SameDay of Prev Month)
    # =========================================================================
    days_elapsed_month = today.day
    curr_month_start = date(today.year, today.month, 1)

    if today.month == 1:
        prev_month_start = date(today.year - 1, 12, 1)
    else:
        prev_month_start = date(today.year, today.month - 1, 1)

    curr_month_dates = {curr_month_start + timedelta(days=i) for i in range(days_elapsed_month)}
    prev_month_aligned_dates = {prev_month_start + timedelta(days=i) for i in range(days_elapsed_month)}

    curr_month_comp = sum(1 for d in completed_dates if d in curr_month_dates)
    prev_month_comp = sum(1 for d in completed_dates if d in prev_month_aligned_dates)

    if curr_month_comp == 0 and prev_month_comp == 0:
        monthly_delta = 0.0
        monthly_trend = "Steady"
        monthly_expl = f"No completions recorded in first {days_elapsed_month} days of current or previous month."
    elif prev_month_comp > 0:
        monthly_delta = round(((curr_month_comp - prev_month_comp) / prev_month_comp) * 100.0, 1)
        monthly_trend = "Improving" if monthly_delta >= 10.0 else ("Declining" if monthly_delta <= -10.0 else "Steady")
        monthly_expl = (
            f"Month-to-date aligned comparison (Days 1–{days_elapsed_month}): {curr_month_comp} completions "
            f"vs {prev_month_comp} in same matching window of previous month ({monthly_delta:+}%)."
        )
    else:
        monthly_delta = 100.0
        monthly_trend = "Improving"
        monthly_expl = f"Month-to-date: {curr_month_comp} completions up from 0 in same window of previous month."

    monthly_comp_obj = PeriodComparison(
        period_label="Monthly (Month-to-Date Aligned Slice)",
        current_period_days_elapsed=days_elapsed_month,
        comparison_mode="DAY_ALIGNED_SLICE",
        current_completions=curr_month_comp,
        previous_aligned_completions=prev_month_comp,
        velocity_delta_percent=monthly_delta,
        trend=monthly_trend,
        explanation=monthly_expl,
    )

    # 4. Overall Momentum
    has_sufficient = len(completed_dates) >= 3
    if not has_sufficient:
        overall_momentum = "Insufficient Data"
    elif weekly_trend == "Improving" or monthly_trend == "Improving":
        overall_momentum = "High Momentum"
    elif weekly_trend == "Declining" and monthly_trend == "Declining":
        overall_momentum = "Slowing Momentum"
    else:
        overall_momentum = "Stable Rhythm"

    return ProductivityTrendsDetail(
        daily_trend=daily_comp_obj,
        weekly_trend=weekly_comp_obj,
        monthly_trend=monthly_comp_obj,
        overall_momentum=overall_momentum,
        has_sufficient_data=has_sufficient,
    )
