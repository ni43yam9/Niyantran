import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)

class ProductivityContext:
    """
    Unified context snapshot integrating tasks, goals, habits, workloads,
    and historical behavioral patterns.
    """
    def __init__(
        self,
        today: date,
        tasks: List[Task],
        goals: List[Goal],
        habits: List[Habit],
        habit_logs: List[HabitLog],
        timeblocks: List[DailyTimeblock],
        activity_logs: List[ActivityLog],
        past_recommendations: List[Recommendation],
    ):
        self.today = today
        self.tasks = tasks
        self.goals = goals
        self.habits = habits
        self.habit_logs = habit_logs
        self.timeblocks = timeblocks
        self.activity_logs = activity_logs
        self.past_recommendations = past_recommendations

        # 1. Segmented tasks
        self.pending_tasks = [t for t in tasks if t.status != "Completed"]
        self.completed_tasks = [t for t in tasks if t.status == "Completed"]
        self.overdue_tasks = [
            t for t in self.pending_tasks
            if t.due_date and t.due_date < today
        ]
        self.due_today_tasks = [
            t for t in self.pending_tasks
            if t.due_date == today
        ]
        self.due_soon_tasks = [
            t for t in self.pending_tasks
            if t.due_date and 1 <= (t.due_date - today).days <= 2
        ]

        # Postponements index: task_id -> count
        self.task_postpones: Dict[str, int] = {}
        for a in self.activity_logs:
            if a.event_type == "TASK_POSTPONED" and a.entity_id:
                self.task_postpones[a.entity_id] = self.task_postpones.get(a.entity_id, 0) + 1

        # Goal map and active goals
        self.active_goals = [g for g in self.goals if g.status != "Completed"]
        self.goal_map: Dict[str, Goal] = {g.id: g for g in goals}
        self.tasks_by_goal: Dict[str, List[Task]] = {}
        for t in tasks:
            if t.goal_id:
                self.tasks_by_goal.setdefault(t.goal_id, []).append(t)

        # 2. Time estimation bias factor
        actual_vs_planned = []
        for tb in self.timeblocks:
            if (
                tb.status == "Completed"
                and tb.duration_minutes
                and tb.duration_minutes > 0
                and tb.actual_duration_minutes
                and tb.actual_duration_minutes > 0
            ):
                actual_vs_planned.append(float(tb.actual_duration_minutes) / float(tb.duration_minutes))

        if len(actual_vs_planned) >= 3:
            self.bias_factor = round(sum(actual_vs_planned) / len(actual_vs_planned), 2)
            self.is_bias_empirical = True
        else:
            self.bias_factor = 1.25  # Heuristic default: 25% underestimation
            self.is_bias_empirical = False

        # 3. Workload distribution across forward 7 days
        self.days_to_check = [today + timedelta(days=i) for i in range(7)]
        self.daily_load_minutes: Dict[date, int] = {d: 0 for d in self.days_to_check}
        self.daily_tasks: Dict[date, List[Task]] = {d: [] for d in self.days_to_check}

        for tb in self.timeblocks:
            if tb.block_date in self.daily_load_minutes and tb.duration_minutes:
                self.daily_load_minutes[tb.block_date] += tb.duration_minutes

        for t in self.pending_tasks:
            t_date = t.start_date or t.due_date or today
            if t_date in self.daily_tasks:
                self.daily_tasks[t_date].append(t)
                has_tb = any(tb.task_id == t.id for tb in self.timeblocks if tb.block_date == t_date)
                if not has_tb:
                    self.daily_load_minutes[t_date] += 60  # Default 1 hr if no timeblock

        # 4. User Interaction Profile with Recommendations
        total_interactions = len(self.past_recommendations)
        accepted_count = sum(1 for r in self.past_recommendations if r.status in ("ACCEPTED", "COMPLETED"))
        dismissed_count = sum(1 for r in self.past_recommendations if r.status == "DISMISSED")

        self.acceptance_rate = (
            round(accepted_count / total_interactions, 2) if total_interactions > 0 else 0.5
        )
        self.acceptance_by_type: Dict[str, float] = {}
        self.adaptive_type_weights: Dict[str, float] = {}
        for r_type in ("PRIORITIZATION", "DEADLINE_RISK", "WORKLOAD_BALANCE", "GOAL_PROGRESS", "HABIT_IMPROVEMENT"):
            type_recs = [r for r in self.past_recommendations if r.type == r_type]
            if type_recs:
                acc = sum(1 for r in type_recs if r.status in ("ACCEPTED", "COMPLETED"))
                rate = round(acc / len(type_recs), 2)
                self.acceptance_by_type[r_type] = rate
                dis = sum(1 for r in type_recs if r.status == "DISMISSED")
                if len(type_recs) >= 3:
                    dis_rate = dis / len(type_recs)
                    if dis_rate >= 0.60:
                        self.adaptive_type_weights[r_type] = max(0.40, round(1.0 - (dis_rate - 0.50) * 0.8, 2))
                    elif rate >= 0.60:
                        self.adaptive_type_weights[r_type] = min(1.40, round(1.0 + (rate - 0.50) * 0.5, 2))
                    else:
                        self.adaptive_type_weights[r_type] = 1.0
                else:
                    self.adaptive_type_weights[r_type] = 1.0
            else:
                self.acceptance_by_type[r_type] = 0.5
                self.adaptive_type_weights[r_type] = 1.0

        # 5. Learned peak productivity window (from completed focus blocks)
        window_counts: Dict[str, int] = {"Morning": 0, "Afternoon": 0, "Evening": 0, "Night": 0}
        for tb in self.timeblocks:
            if tb.status == "Completed" and tb.time:
                s = tb.time.strip().upper()
                hour = 12
                if "AM" in s or "PM" in s:
                    try:
                        hour = datetime.strptime(s, "%I:%M %p").hour
                    except Exception:
                        pass
                if 6 <= hour < 12:
                    window_counts["Morning"] += 1
                elif 12 <= hour < 18:
                    window_counts["Afternoon"] += 1
                elif 18 <= hour < 23:
                    window_counts["Evening"] += 1
                else:
                    window_counts["Night"] += 1

        total_windows = sum(window_counts.values())
        if total_windows >= 5:
            self.peak_time_window = max(window_counts.items(), key=lambda x: x[1])[0]
        else:
            self.peak_time_window = "Morning"  # Baseline default


def build_productivity_context(db: Session, reference_date: Optional[date] = None) -> ProductivityContext:
    """
    Gathers all operational tables and synthesizes a ProductivityContext.
    """
    today = reference_date or date.today()

    tasks = db.query(Task).all()
    goals = db.query(Goal).all()
    habits = db.query(Habit).filter(Habit.archived == False).all()
    habit_logs = db.query(HabitLog).all()
    timeblocks = db.query(DailyTimeblock).all()
    activity_logs = db.query(ActivityLog).all()
    past_recommendations = db.query(Recommendation).all()

    return ProductivityContext(
        today=today,
        tasks=tasks,
        goals=goals,
        habits=habits,
        habit_logs=habit_logs,
        timeblocks=timeblocks,
        activity_logs=activity_logs,
        past_recommendations=past_recommendations,
    )
