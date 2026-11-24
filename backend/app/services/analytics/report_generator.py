import uuid
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.analytics import (
    WeeklyProductivityReport,
    MonthlyProductivityReport,
)
from backend.app.services.analytics.score_calculator import calculate_explainable_productivity_score
from backend.app.services.analytics.task_analytics import analyze_tasks_in_depth
from backend.app.services.analytics.goal_analytics import analyze_goals_in_depth
from backend.app.services.analytics.habit_analytics import analyze_habits_in_depth
from backend.app.services.analytics.time_distribution import analyze_time_distribution

logger = logging.getLogger(__name__)

def generate_weekly_productivity_report(
    db: Session,
    start_date: Optional[date] = None,
    tz_offset_mins: int = 0,
    now_utc: Optional[datetime] = None,
) -> WeeklyProductivityReport:
    """
    Generates a concise, lightweight weekly productivity performance summary.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()

    if start_date:
        week_start = start_date
    else:
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # 1. Productivity Score & Components
    score_detail = calculate_explainable_productivity_score(db, reference_date=today, now_utc=now)

    # 2. Tasks completed in target week
    completed_in_week = []
    all_completed = db.query(Task).filter(Task.status == "Completed").all()
    for t in all_completed:
        if t.completed_at:
            c_date = (t.completed_at + timedelta(minutes=tz_offset_mins)).date()
            if week_start <= c_date <= week_end:
                completed_in_week.append(t)
        elif t.due_date and week_start <= t.due_date <= week_end:
            completed_in_week.append(t)

    task_summary = {
        "completed_count": len(completed_in_week),
        "high_priority_completed": sum(1 for t in completed_in_week if t.priority == "High"),
        "top_category": (
            max({t.category: sum(1 for x in completed_in_week if x.category == t.category) for t in completed_in_week}.items(), key=lambda x: x[1])[0]
            if completed_in_week else "None"
        ),
    }

    # 3. Goals Progress
    goals = db.query(Goal).all()
    goal_summary = {
        "total_active_goals": sum(1 for g in goals if g.status != "Completed"),
        "average_progress": round(sum(g.progress or 0 for g in goals) / max(1, len(goals)), 1),
    }

    # 4. Habits Consistency
    habits = db.query(Habit).filter(Habit.archived == False).all()
    habit_logs_week = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= week_start, HabitLog.log_date <= week_end)
        .scalar()
        or 0
    )
    possible_logs = len(habits) * 7
    habit_summary = {
        "total_habits": len(habits),
        "week_consistency_rate": round((habit_logs_week / max(1, possible_logs)) * 100.0, 1),
    }

    # 5. Time Summary
    time_dist = analyze_time_distribution(db, tz_offset_mins=tz_offset_mins)
    time_summary = {
        "total_tracked_minutes": time_dist.total_tracked_duration_minutes,
        "total_estimated_minutes": time_dist.total_estimated_duration_minutes,
        "deep_work_focus_minutes": time_dist.deep_work_focus_minutes,
    }

    # Key achievements & recommendations
    achievements = []
    if len(completed_in_week) > 0:
        achievements.append(f"Delivered {len(completed_in_week)} deliverables during the target weekly cycle.")
    if task_summary["high_priority_completed"] > 0:
        achievements.append(f"Successfully finalized {task_summary['high_priority_completed']} High-priority objective(s).")
    if habit_summary["week_consistency_rate"] >= 70.0:
        achievements.append(f"Maintained strong {habit_summary['week_consistency_rate']}% habit consistency.")
    if not achievements:
        achievements.append("Weekly cycle initiated. Focus on completing initial scheduled deliverables.")

    recommendations = [
        "Align demanding coding and academic tasks with your primary morning peak focus window.",
        "Maintain balanced 300-minute daily scheduling budgets to prevent end-of-week burnout.",
    ]

    report_id = f"rep_w_{week_start.isoformat()}_{uuid.uuid4().hex[:6]}"

    return WeeklyProductivityReport(
        report_id=report_id,
        week_start=week_start,
        week_end=week_end,
        productivity_score=score_detail.score,
        task_summary=task_summary,
        goal_summary=goal_summary,
        habit_summary=habit_summary,
        time_summary=time_summary,
        key_achievements=achievements,
        actionable_recommendations=recommendations,
        generated_at=now,
    )

def generate_monthly_productivity_report(
    db: Session,
    year: Optional[int] = None,
    month: Optional[int] = None,
    now_utc: Optional[datetime] = None,
) -> MonthlyProductivityReport:
    """
    Generates a concise, lightweight monthly productivity performance summary.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()

    target_year = year or today.year
    target_month = month or today.month

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

    month_name = curr_start.strftime("%B")

    # 1. Productivity Score
    score_detail = calculate_explainable_productivity_score(db, reference_date=today, now_utc=now)

    # 2. Tasks completed in month vs previous month
    curr_comp = 0
    prev_comp = 0
    all_comp = db.query(Task.completed_at).filter(Task.status == "Completed", Task.completed_at.isnot(None)).all()
    for row in all_comp:
        c_date = row[0].date()
        if curr_start <= c_date < next_month_start:
            curr_comp += 1
        elif prev_month_start <= c_date < curr_start:
            prev_comp += 1

    if prev_comp > 0:
        velocity_delta = round(((curr_comp - prev_comp) / prev_comp) * 100.0, 1)
    else:
        velocity_delta = 100.0 if curr_comp > 0 else 0.0

    task_summary = {
        "monthly_completed_tasks": curr_comp,
        "previous_month_completed": prev_comp,
        "velocity_delta_percent": velocity_delta,
    }

    # 3. Goals Summary
    goals = db.query(Goal).all()
    goal_summary = {
        "total_goals": len(goals),
        "completed_goals": sum(1 for g in goals if g.status == "Completed"),
        "average_progress": round(sum(g.progress or 0 for g in goals) / max(1, len(goals)), 1),
    }

    # 4. Habits Summary
    habits = db.query(Habit).filter(Habit.archived == False).all()
    days_in_month = (next_month_start - curr_start).days
    habit_logs_month = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.completed == True, HabitLog.log_date >= curr_start, HabitLog.log_date < next_month_start)
        .scalar()
        or 0
    )
    possible_habit_logs = len(habits) * days_in_month
    habit_summary = {
        "total_habits": len(habits),
        "monthly_consistency_rate": round((habit_logs_month / max(1, possible_habit_logs)) * 100.0, 1),
    }

    milestones = [
        f"Concluded {curr_comp} deliverable(s) across {month_name} {target_year}.",
        f"Goal milestone progress averaging {goal_summary['average_progress']}%.",
    ]

    recommendations = [
        "Regularly review goal velocity deficits to detect lagging milestones early.",
        "Maintain habit streak protections to stabilize monthly routine baseline.",
    ]

    report_id = f"rep_m_{target_year}_{target_month:02d}_{uuid.uuid4().hex[:6]}"

    return MonthlyProductivityReport(
        report_id=report_id,
        year=target_year,
        month=target_month,
        month_name=month_name,
        productivity_score=score_detail.score,
        monthly_velocity_delta=velocity_delta,
        task_summary=task_summary,
        goal_summary=goal_summary,
        habit_summary=habit_summary,
        key_milestones=milestones,
        actionable_recommendations=recommendations,
        generated_at=now,
    )
