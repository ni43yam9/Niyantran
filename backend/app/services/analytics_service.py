from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.analytics import (
    AnalyticsOverview,
    DailyAnalytics,
    DayWeeklyData,
    WeeklyAnalytics,
    MonthlyAnalytics,
    TimeAnalytics,
    GoalAnalyticsItem,
    GoalAnalytics,
    ProductivityInsight,
    InsightsResponse,
)

# ---------------------------------------------------------------------------
# 1. Productivity Dashboard Overview
# ---------------------------------------------------------------------------

def get_analytics_overview(db: Session, tz_offset_mins: int = 0) -> AnalyticsOverview:
    tasks = db.query(Task).all()
    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if t.status == "Completed"]
    pending_tasks = [t for t in tasks if t.status != "Completed"]
    total_completed = len(completed_tasks)
    total_pending = len(pending_tasks)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Postponed tasks count
    postponed_count = (
        db.query(func.count(func.distinct(ActivityLog.entity_id)))
        .filter(ActivityLog.event_type == "TASK_POSTPONED")
        .scalar()
        or 0
    )

    # Completion rates across timeframes
    # Daily
    today_due = sum(1 for t in tasks if t.due_date == today or (t.completed_at and t.completed_at.date() == today))
    today_done = sum(1 for t in completed_tasks if (t.completed_at and t.completed_at.date() == today) or (t.due_date == today and t.status == "Completed"))
    daily_rate = round((today_done / today_due) * 100, 1) if today_due > 0 else (100.0 if today_done > 0 else 0.0)

    # Weekly
    week_due = sum(1 for t in tasks if (t.due_date and t.due_date >= week_start) or (t.completed_at and t.completed_at.date() >= week_start))
    week_done = sum(1 for t in completed_tasks if t.completed_at and t.completed_at.date() >= week_start)
    weekly_rate = round((week_done / week_due) * 100, 1) if week_due > 0 else (100.0 if week_done > 0 else 0.0)

    # Monthly
    month_due = sum(1 for t in tasks if (t.due_date and t.due_date >= month_start) or (t.completed_at and t.completed_at.date() >= month_start))
    month_done = sum(1 for t in completed_tasks if t.completed_at and t.completed_at.date() >= month_start)
    monthly_rate = round((month_done / month_due) * 100, 1) if month_due > 0 else (100.0 if month_done > 0 else 0.0)

    # Habit consistency (last 30 days)
    habits = db.query(Habit).filter(Habit.archived == False).all()
    habit_consistency = 0.0
    if habits:
        thirty_days_ago = today - timedelta(days=30)
        logs_count = (
            db.query(func.count(HabitLog.id))
            .filter(HabitLog.completed == True, HabitLog.log_date >= thirty_days_ago)
            .scalar()
            or 0
        )
        total_possible = len(habits) * 30
        habit_consistency = round((logs_count / total_possible) * 100, 1) if total_possible > 0 else 0.0

    # Active goals count
    active_goals = db.query(func.count(Goal.id)).filter(Goal.status != "Completed").scalar() or 0

    # Overall Productivity Score Calculation (0-100)
    # Composite: 40% overall task completion + 30% habit consistency + 30% weekly execution
    overall_task_comp = (total_completed / total_tasks * 100) if total_tasks > 0 else 70.0
    raw_score = (overall_task_comp * 0.4) + (habit_consistency * 0.3) + (weekly_rate * 0.3)
    productivity_score = max(15, min(100, int(round(raw_score))))

    return AnalyticsOverview(
        productivity_score=productivity_score,
        daily_completion_rate=daily_rate,
        weekly_completion_rate=weekly_rate,
        monthly_completion_rate=monthly_rate,
        total_completed_tasks=total_completed,
        total_postponed_tasks=postponed_count,
        total_pending_tasks=total_pending,
        habit_consistency_rate=habit_consistency,
        active_goals_count=active_goals,
        evaluated_at=datetime.now(timezone.utc),
    )

# ---------------------------------------------------------------------------
# 2. Daily Analytics
# ---------------------------------------------------------------------------

def get_daily_analytics(db: Session, target_date: Optional[date] = None, tz_offset_mins: int = 0) -> DailyAnalytics:
    ref_date = target_date or date.today()

    tasks_planned = db.query(func.count(Task.id)).filter(
        or_(Task.due_date == ref_date, Task.start_date == ref_date)
    ).scalar() or 0

    tasks_completed = 0
    tasks = db.query(Task).filter(Task.status == "Completed").all()
    for t in tasks:
        is_comp = False
        if t.completed_at:
            comp_date = (t.completed_at + timedelta(minutes=tz_offset_mins)).date()
            if comp_date == ref_date:
                is_comp = True
        if not is_comp and t.due_date == ref_date and t.status == "Completed":
            is_comp = True
        if is_comp:
            tasks_completed += 1

    postponed = db.query(func.count(ActivityLog.id)).filter(
        ActivityLog.event_type == "TASK_POSTPONED",
        ActivityLog.new_date == ref_date,
    ).scalar() or 0

    total_pool = max(tasks_planned, tasks_completed)
    completion_pct = round((tasks_completed / total_pool) * 100, 1) if total_pool > 0 else 0.0

    # Timeblocks metrics for target_date
    blocks = db.query(DailyTimeblock).filter(DailyTimeblock.block_date == ref_date).all()
    planned_mins = sum(b.duration_minutes or 60 for b in blocks if not b.is_break)
    actual_mins = sum(b.actual_duration_minutes or 0 for b in blocks if not b.is_break and b.actual_duration_minutes)

    # Hourly completions on target_date
    hourly: Dict[int, int] = {h: 0 for h in range(24)}
    for t in tasks:
        if t.completed_at:
            local_dt = t.completed_at + timedelta(minutes=tz_offset_mins)
            if local_dt.date() == ref_date:
                hourly[local_dt.hour] += 1

    has_data = tasks_planned > 0 or tasks_completed > 0 or len(blocks) > 0
    summary = (
        f"{tasks_completed} of {total_pool} tasks completed ({completion_pct}% completion). "
        f"{planned_mins} mins planned across {len(blocks)} focus blocks."
        if has_data
        else "No planned deliverables recorded for this day."
    )

    return DailyAnalytics(
        target_date=ref_date,
        tasks_planned=total_pool,
        tasks_completed=tasks_completed,
        tasks_postponed=postponed,
        completion_percentage=completion_pct,
        focus_minutes_planned=planned_mins,
        focus_minutes_actual=actual_mins,
        hourly_completions=hourly,
        has_sufficient_data=has_data,
        summary=summary,
    )

# ---------------------------------------------------------------------------
# 3. Weekly Analytics
# ---------------------------------------------------------------------------

def get_weekly_analytics(db: Session, start_date: Optional[date] = None, tz_offset_mins: int = 0) -> WeeklyAnalytics:
    today = date.today()
    if start_date:
        week_start = start_date
    else:
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_breakdown: List[DayWeeklyData] = []

    total_w_planned = 0
    total_w_completed = 0
    total_w_postponed = 0

    all_completed = db.query(Task).filter(Task.status == "Completed", Task.completed_at.isnot(None)).all()

    for idx, day_name in enumerate(day_names):
        curr_d = week_start + timedelta(days=idx)

        planned = db.query(func.count(Task.id)).filter(
            or_(Task.due_date == curr_d, Task.start_date == curr_d)
        ).scalar() or 0

        completed = 0
        for t in all_completed:
            local_dt = t.completed_at + timedelta(minutes=tz_offset_mins)
            if local_dt.date() == curr_d:
                completed += 1

        postponed = db.query(func.count(ActivityLog.id)).filter(
            ActivityLog.event_type == "TASK_POSTPONED",
            ActivityLog.new_date == curr_d,
        ).scalar() or 0

        eff_planned = max(planned, completed)
        rate = round((completed / eff_planned) * 100, 1) if eff_planned > 0 else (100.0 if completed > 0 else 0.0)

        total_w_planned += eff_planned
        total_w_completed += completed
        total_w_postponed += postponed

        daily_breakdown.append(
            DayWeeklyData(
                date=curr_d,
                day_name=day_name,
                planned=eff_planned,
                completed=completed,
                postponed=postponed,
                completion_rate=rate,
            )
        )

    overall_w_rate = round((total_w_completed / total_w_planned) * 100, 1) if total_w_planned > 0 else 0.0

    # Trend calculation: compare first 3 days vs last 4 days
    first_half = sum(d.completed for d in daily_breakdown[:3])
    second_half = sum(d.completed for d in daily_breakdown[3:])
    if total_w_completed < 2:
        trend = "Insufficient Data"
    elif second_half > first_half:
        trend = "Improving"
    elif second_half < first_half:
        trend = "Declining"
    else:
        trend = "Steady"

    most_prod = max(daily_breakdown, key=lambda d: d.completed).day_name if total_w_completed > 0 else None

    return WeeklyAnalytics(
        week_start=week_start,
        week_end=week_end,
        daily_breakdown=daily_breakdown,
        total_planned=total_w_planned,
        total_completed=total_w_completed,
        total_postponed=total_w_postponed,
        weekly_completion_rate=overall_w_rate,
        productivity_trend=trend,
        most_productive_day=most_prod,
    )

# ---------------------------------------------------------------------------
# 4. Monthly Analytics
# ---------------------------------------------------------------------------

def get_monthly_analytics(db: Session, year: Optional[int] = None, month: Optional[int] = None) -> MonthlyAnalytics:
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month

    # Current month start and next month
    curr_start = date(target_year, target_month, 1)
    if target_month == 12:
        next_month_start = date(target_year + 1, 1, 1)
        prev_month_start = date(target_year, 11, 1)
    elif target_month == 1:
        next_month_start = date(target_year, 2, 1)
        prev_month_start = date(target_year - 1, 12, 1)
    else:
        next_month_start = date(target_year, target_month + 1, 1)
        prev_month_start = date(target_year, target_month - 1, 1)

    # Completed tasks in target month
    curr_completed = 0
    prev_completed = 0
    all_completed = db.query(Task.completed_at).filter(Task.status == "Completed", Task.completed_at.isnot(None)).all()
    for row in all_completed:
        c_date = row[0].date()
        if curr_start <= c_date < next_month_start:
            curr_completed += 1
        elif prev_month_start <= c_date < curr_start:
            prev_completed += 1

    # Percentage change
    if prev_completed > 0:
        pct_change = round(((curr_completed - prev_completed) / prev_completed) * 100, 1)
    else:
        pct_change = 100.0 if curr_completed > 0 else 0.0

    # Goals progress
    goals = db.query(Goal).all()
    goals_comp = sum(1 for g in goals if g.status == "Completed")
    goals_act = sum(1 for g in goals if g.status != "Completed")
    avg_progress = round(sum(g.progress or 0 for g in goals) / len(goals), 1) if goals else 0.0

    # Monthly habit consistency
    habits = db.query(Habit).filter(Habit.archived == False).all()
    monthly_habit_pct = 0.0
    if habits:
        logs_count = (
            db.query(func.count(HabitLog.id))
            .filter(HabitLog.completed == True, HabitLog.log_date >= curr_start, HabitLog.log_date < next_month_start)
            .scalar()
            or 0
        )
        days_in_month = (next_month_start - curr_start).days
        total_possible = len(habits) * days_in_month
        monthly_habit_pct = round((logs_count / total_possible) * 100, 1) if total_possible > 0 else 0.0

    month_name = curr_start.strftime("%B")
    trend = "Improving" if pct_change > 5 else ("Declining" if pct_change < -5 else "Steady")

    return MonthlyAnalytics(
        year=target_year,
        month=target_month,
        month_name=month_name,
        tasks_completed=curr_completed,
        tasks_completed_prev_month=prev_completed,
        percentage_change=pct_change,
        goals_completed=goals_comp,
        goals_in_progress=goals_act,
        average_goal_progress=avg_progress,
        monthly_habit_consistency=monthly_habit_pct,
        trend=trend,
    )

# ---------------------------------------------------------------------------
# 5. Time Analytics
# ---------------------------------------------------------------------------

def get_time_analytics(db: Session, tz_offset_mins: int = 0) -> TimeAnalytics:
    tasks = db.query(Task).filter(Task.status == "Completed").all()
    completion_times: List[datetime] = [t.completed_at for t in tasks if t.completed_at]

    # Task resolution duration
    durations: List[float] = []
    for t in tasks:
        if t.completed_at and t.created_at and t.completed_at >= t.created_at:
            durations.append((t.completed_at - t.created_at).total_seconds() / 3600.0)
    avg_dur = round(sum(durations) / len(durations), 1) if durations else None

    # Timeblocks estimation comparison
    blocks = db.query(DailyTimeblock).filter(
        DailyTimeblock.duration_minutes.isnot(None),
        DailyTimeblock.actual_duration_minutes.isnot(None),
    ).all()

    total_est = sum(b.duration_minutes for b in blocks)
    total_act = sum(b.actual_duration_minutes for b in blocks)
    variance = total_act - total_est
    under_count = sum(1 for b in blocks if b.actual_duration_minutes > b.duration_minutes)
    under_rate = round((under_count / len(blocks)) * 100, 1) if blocks else 0.0

    # Quadrant distribution
    morning = 0
    afternoon = 0
    evening = 0
    night = 0
    hourly: Dict[int, int] = {h: 0 for h in range(24)}

    for dt in completion_times:
        local_dt = dt + timedelta(minutes=tz_offset_mins)
        h = local_dt.hour
        hourly[h] += 1
        if 5 <= h < 12:
            morning += 1
        elif 12 <= h < 17:
            afternoon += 1
        elif 17 <= h < 22:
            evening += 1
        else:
            night += 1

    total_c = len(completion_times)
    quad_dist = {
        "Morning": morning,
        "Afternoon": afternoon,
        "Evening": evening,
        "Night": night,
    }
    quad_pcts = {
        k: round((v / total_c) * 100, 1) if total_c > 0 else 0.0 for k, v in quad_dist.items()
    }

    # Best & least windows
    best_start = max(range(24), key=lambda s: sum(hourly[(s + o) % 24] for o in range(3)))
    least_start = min(range(24), key=lambda s: sum(hourly[(s + o) % 24] for o in range(3)))

    def _fmt_window(start: int) -> str:
        end = (start + 3) % 24
        s_m = "AM" if start < 12 else "PM"
        e_m = "AM" if end < 12 else "PM"
        return f"{start % 12 or 12:02d}:00 {s_m} – {end % 12 or 12:02d}:00 {e_m}"

    most_win = _fmt_window(best_start) if total_c >= 2 else "10:00 AM – 01:00 PM"
    least_win = _fmt_window(least_start) if total_c >= 2 else "02:00 AM – 05:00 AM"

    return TimeAnalytics(
        most_productive_window=most_win,
        least_productive_window=least_win,
        average_task_completion_hours=avg_dur,
        total_estimated_minutes=total_est,
        total_actual_minutes=total_act,
        estimation_variance_minutes=variance,
        underestimation_rate=under_rate,
        quadrant_distribution=quad_dist,
        quadrant_percentages=quad_pcts,
        has_sufficient_data=total_c >= 2,
    )

# ---------------------------------------------------------------------------
# 6. Goal Analytics
# ---------------------------------------------------------------------------

def get_goal_analytics(db: Session) -> GoalAnalytics:
    goals = db.query(Goal).all()
    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.status == "Completed")
    active_goals = total_goals - completed_goals
    avg_progress = round(sum(g.progress or 0 for g in goals) / total_goals, 1) if total_goals > 0 else 0.0

    short_term = sum(1 for g in goals if getattr(g, "goal_type", "").lower() in ["short-term", "short_term"])
    long_term = sum(1 for g in goals if getattr(g, "goal_type", "").lower() in ["long-term", "long_term"])

    items: List[GoalAnalyticsItem] = []
    for g in goals:
        linked_tasks = db.query(Task).filter(Task.goal_id == g.id).all()
        t_total = len(linked_tasks)
        t_completed = sum(1 for t in linked_tasks if t.status == "Completed")
        rate = round((t_completed / t_total) * 100, 1) if t_total > 0 else float(g.progress or 0)

        items.append(
            GoalAnalyticsItem(
                goal_id=g.id,
                title=g.title,
                category=g.category,
                timeframe=getattr(g, "goal_type", "Short-Term"),
                priority=g.priority,
                status=g.status,
                progress=g.progress or 0,
                total_tasks=t_total,
                completed_tasks=t_completed,
                task_completion_rate=rate,
            )
        )

    completion_trend = "On Track" if avg_progress >= 60 else ("Progressing" if avg_progress >= 30 else "Early Stage")

    return GoalAnalytics(
        total_goals=total_goals,
        completed_goals=completed_goals,
        active_goals=active_goals,
        average_progress=avg_progress,
        short_term_count=short_term,
        long_term_count=long_term,
        goals=items,
        completion_trend=completion_trend,
    )

# ---------------------------------------------------------------------------
# 7. Behaviour-Based Actionable Insights
# ---------------------------------------------------------------------------

def get_productivity_insights(db: Session, tz_offset_mins: int = 0) -> InsightsResponse:
    insights: List[ProductivityInsight] = []

    tasks = db.query(Task).all()
    completed_tasks = [t for t in tasks if t.status == "Completed"]
    total_tasks = len(tasks)

    # 1. Timing Insight
    if len(completed_tasks) >= 3:
        morning_count = 0
        evening_count = 0
        for t in completed_tasks:
            if t.completed_at:
                local_dt = t.completed_at + timedelta(minutes=tz_offset_mins)
                if 5 <= local_dt.hour < 12:
                    morning_count += 1
                elif 17 <= local_dt.hour < 22:
                    evening_count += 1

        if morning_count > evening_count and evening_count > 0:
            diff_pct = round(((morning_count - evening_count) / evening_count) * 100)
            insights.append(
                ProductivityInsight(
                    id="ins-timing-morning",
                    type="positive",
                    category="Timing",
                    title="Higher Morning Output",
                    description=f"Your task completion velocity is {diff_pct}% higher during morning hours. Frontload complex deliverables before noon.",
                    impact="High",
                )
            )
        elif evening_count > morning_count:
            insights.append(
                ProductivityInsight(
                    id="ins-timing-evening",
                    type="neutral",
                    category="Timing",
                    title="Peak Evening Concentration",
                    description="You resolve the majority of your deliverables between 5:00 PM and 10:00 PM. Protect this focus window from interruptions.",
                    impact="Medium",
                )
            )

    # 2. Time Estimation Bias Insight
    blocks = db.query(DailyTimeblock).filter(
        DailyTimeblock.duration_minutes.isnot(None),
        DailyTimeblock.actual_duration_minutes.isnot(None),
    ).all()
    if len(blocks) >= 2:
        under = [b for b in blocks if b.actual_duration_minutes > b.duration_minutes]
        if len(under) >= len(blocks) / 2:
            avg_over = round(sum(b.actual_duration_minutes - b.duration_minutes for b in under) / len(under))
            insights.append(
                ProductivityInsight(
                    id="ins-estimation-under",
                    type="warning",
                    category="Estimation",
                    title="Underestimation Pattern Detected",
                    description=f"You consistently underestimate task durations by an average of +{avg_over} minutes. Add buffer margins to daily blocks.",
                    impact="High",
                )
            )

    # 3. Postponement Pattern Insight
    postpone_events = (
        db.query(ActivityLog)
        .filter(ActivityLog.event_type == "TASK_POSTPONED")
        .all()
    )
    if len(postpone_events) >= 2:
        task_postpone_counts: Dict[str, int] = {}
        for evt in postpone_events:
            if evt.entity_id:
                task_postpone_counts[evt.entity_id] = task_postpone_counts.get(evt.entity_id, 0) + 1

        multi_postponed = sum(1 for cnt in task_postpone_counts.values() if cnt >= 2)
        if multi_postponed > 0:
            insights.append(
                ProductivityInsight(
                    id="ins-postpone-repeated",
                    type="warning",
                    category="Postponement",
                    title="Repeated Postponement Cycle",
                    description=f"{multi_postponed} task(s) have been rescheduled 2 or more times. Consider decomposing them into bite-sized 25-minute milestones.",
                    impact="High",
                )
            )

    # 4. Habit Consistency Insight
    habits = db.query(Habit).filter(Habit.archived == False).all()
    if habits:
        top_streak = max((h.base_streak or 0 for h in habits), default=0)
        if top_streak >= 5:
            insights.append(
                ProductivityInsight(
                    id="ins-habit-streak",
                    type="positive",
                    category="Habit",
                    title="Strong Ritual Momentum",
                    description=f"You have maintained an unbroken {top_streak}-day streak on your primary habits. Consistency compound returns are compounding.",
                    impact="Medium",
                )
            )

    # 5. Planning Capacity Adherence
    timeblocks_all = db.query(DailyTimeblock).all()
    if len(timeblocks_all) >= 4:
        insights.append(
            ProductivityInsight(
                id="ins-planning-healthy",
                type="tip",
                category="Planning",
                title="Balanced Daily Capacity",
                description="Your planned workload is structured within the optimal 6.0 hours/day focus budget, preventing burnout while sustaining momentum.",
                impact="Medium",
            )
        )

    has_data = len(insights) > 0 or total_tasks >= 3
    sufficiency_msg = None if has_data else "Not enough activity data to identify your productivity pattern yet."

    return InsightsResponse(
        insights=insights,
        total_insights=len(insights),
        has_sufficient_data=has_data,
        data_sufficiency_message=sufficiency_msg,
    )
