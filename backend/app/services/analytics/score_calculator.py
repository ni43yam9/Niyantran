import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.analytics import ScoreBreakdown, ProductivityScoreDetail

logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = (
    "This productivity score measures system deliverable execution velocity, deadline adherence, "
    "and habit consistency within Niyantra. It does not measure personal human worth, intellectual ability, "
    "or unrecorded real-world effort."
)

def calculate_explainable_productivity_score(
    db: Session,
    reference_date: Optional[date] = None,
    now_utc: Optional[datetime] = None,
) -> ProductivityScoreDetail:
    """
    Computes a transparent, explainable 6-variable productivity score (0 - 100).
    Guards against rewarding excessive task creation without execution (Backlog Expansion Guard)
    and handles insufficient data with a calibrated baseline.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = reference_date or now.date() if isinstance(now, datetime) else date.today()

    tasks = db.query(Task).all()
    goals = db.query(Goal).all()
    habits = db.query(Habit).filter(Habit.archived == False).all()

    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if t.status == "Completed"]
    pending_tasks = [t for t in tasks if t.status != "Completed"]
    total_completed = len(completed_tasks)
    total_pending = len(pending_tasks)

    # 1. Check Minimum Data Sufficiency
    if total_tasks < 3:
        breakdown = ScoreBreakdown(
            task_completion_points=12.5,
            priority_weight_points=10.0,
            deadline_adherence_points=10.0,
            goal_progress_points=7.5,
            habit_consistency_points=7.5,
            trend_modifier_points=2.5,
            total_score=50,
        )
        explanation = (
            "Baseline productivity score (50/100) assigned due to limited activity records (< 3 deliverables). "
            "Complete 3 or more deliverables and log habit check-ins to activate personalized calibration."
        )
        return ProductivityScoreDetail(
            score=50,
            level="Baseline",
            breakdown=breakdown,
            methodology_explanation=explanation,
            backlog_expansion_flag=False,
            has_sufficient_data=False,
            disclaimer=DISCLAIMER_TEXT,
            evaluated_at=now,
        )

    # 2. Component 1: Task Completion Rate (Max 25.0 points)
    # Ratio of completed deliverables to total created pool
    raw_comp_rate = total_completed / max(1, total_tasks)
    task_comp_pts = round(25.0 * raw_comp_rate, 1)

    # 3. Component 2: Priority-Weighted Execution (Max 20.0 points)
    # High priority = 3.0, Medium = 2.0, Low = 1.0
    weight_map = {"High": 3.0, "Medium": 2.0, "Low": 1.0}
    total_weight_pool = sum(weight_map.get(t.priority, 2.0) for t in tasks)
    completed_weight_pool = sum(weight_map.get(t.priority, 2.0) for t in completed_tasks)
    priority_ratio = completed_weight_pool / max(1.0, total_weight_pool)
    priority_pts = round(20.0 * priority_ratio, 1)

    # 4. Component 3: Deadline Adherence (Max 20.0 points)
    # Overdue tasks in pending backlog degrade score
    overdue_tasks = [t for t in pending_tasks if t.due_date and t.due_date < today]
    overdue_count = len(overdue_tasks)
    overdue_ratio = overdue_count / max(1, total_pending) if total_pending > 0 else 0.0
    # Adherence factor drops as overdue proportion rises
    adherence_factor = max(0.0, 1.0 - (1.5 * overdue_ratio))
    deadline_pts = round(20.0 * adherence_factor, 1)

    # 5. Component 4: Goal Progress Velocity (Max 15.0 points)
    active_goals = [g for g in goals if g.status != "Completed"]
    if active_goals:
        avg_progress = sum(float(g.progress or 0) for g in active_goals) / len(active_goals)
        goal_pts = round(15.0 * (avg_progress / 100.0), 1)
    elif goals:
        # All goals completed
        goal_pts = 15.0
    else:
        # Neutral baseline when user tracks tasks without goals
        goal_pts = 10.0

    # 6. Component 5: Habit Consistency (Max 15.0 points)
    fourteen_days_ago = today - timedelta(days=14)
    if habits:
        habit_logs_14d = (
            db.query(func.count(HabitLog.id))
            .filter(HabitLog.completed == True, HabitLog.log_date >= fourteen_days_ago)
            .scalar()
            or 0
        )
        possible_logs = len(habits) * 14
        habit_adherence = habit_logs_14d / max(1, possible_logs)
        habit_pts = round(15.0 * min(1.0, habit_adherence), 1)
    else:
        # Neutral baseline when user tracks tasks without habits
        habit_pts = 10.0

    # 7. Component 6: Trend & Backlog Expansion Guard Modifier ([-5.0 to +5.0] points)
    seven_days_ago = today - timedelta(days=7)
    created_7d = sum(1 for t in tasks if t.created_at and t.created_at.date() >= seven_days_ago)
    completed_7d = sum(1 for t in completed_tasks if t.completed_at and t.completed_at.date() >= seven_days_ago)

    backlog_expansion_detected = False
    trend_modifier = 0.0

    # Guard: Creating lots of tasks without completing them does NOT increase score
    if created_7d >= 2 * max(1, completed_7d) and completed_7d <= 1:
        backlog_expansion_detected = True
        trend_modifier -= 3.5  # Friction penalty for expanding backlog without execution
    elif completed_7d >= 3 and overdue_count == 0:
        trend_modifier += 4.0  # Execution momentum bonus
    elif completed_7d >= 1:
        trend_modifier += 1.5
    else:
        trend_modifier -= 1.0

    trend_pts = round(max(-5.0, min(5.0, trend_modifier)), 1)

    # 8. Composite Sum & Bounding
    raw_total = task_comp_pts + priority_pts + deadline_pts + goal_pts + habit_pts + trend_pts
    final_score = int(round(max(10.0, min(100.0, raw_total))))

    # Score Classification Level
    if final_score >= 85:
        level = "Exceptional"
    elif final_score >= 70:
        level = "High"
    elif final_score >= 50:
        level = "Balanced"
    elif final_score >= 35:
        level = "Developing"
    else:
        level = "Needs Focus"

    breakdown = ScoreBreakdown(
        task_completion_points=task_comp_pts,
        priority_weight_points=priority_pts,
        deadline_adherence_points=deadline_pts,
        goal_progress_points=goal_pts,
        habit_consistency_points=habit_pts,
        trend_modifier_points=trend_pts,
        total_score=final_score,
    )

    explanation_parts = [
        f"Productivity Score {final_score}/100 ({level}).",
        f"Deliverable Completion: {task_comp_pts}/25.0 pts ({total_completed}/{total_tasks} completed, {round(raw_comp_rate*100, 1)}%).",
        f"Priority Execution: {priority_pts}/20.0 pts (weighted by High/Medium deliverable focus).",
        f"Deadline Adherence: {deadline_pts}/20.0 pts ({overdue_count} overdue debt deliverables).",
        f"Goal Alignment: {goal_pts}/15.0 pts across active milestones.",
        f"Habit Rituals: {habit_pts}/15.0 pts across trailing 14-day check-ins.",
    ]
    if backlog_expansion_detected:
        explanation_parts.append(
            f"Backlog Expansion Guard active ({trend_pts} pts): Task creation ({created_7d}) outpaced completions ({completed_7d}). "
            "Focus on execution over deliverable generation."
        )
    else:
        explanation_parts.append(f"Trend Modifier: {trend_pts:+} pts based on weekly execution velocity.")

    methodology_text = " ".join(explanation_parts)

    return ProductivityScoreDetail(
        score=final_score,
        level=level,
        breakdown=breakdown,
        methodology_explanation=methodology_text,
        backlog_expansion_flag=backlog_expansion_detected,
        has_sufficient_data=True,
        disclaimer=DISCLAIMER_TEXT,
        evaluated_at=now,
    )
