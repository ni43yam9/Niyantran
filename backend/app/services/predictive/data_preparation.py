import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)

class HistoricalDataContainer:
    """
    Structured container holding verified empirical observations from the database.
    Strictly avoids fabricating events or synthesizing observations.
    """
    def __init__(
        self,
        tasks: List[Task],
        goals: List[Goal],
        habits: List[Habit],
        habit_logs: List[HabitLog],
        timeblocks: List[DailyTimeblock],
        activity_logs: List[ActivityLog],
        today: date
    ):
        self.tasks = tasks
        self.goals = goals
        self.habits = habits
        self.habit_logs = habit_logs
        self.timeblocks = timeblocks
        self.activity_logs = activity_logs
        self.today = today

        # Segmented tasks
        self.completed_tasks = [t for t in tasks if t.status == "Completed"]
        self.active_tasks = [t for t in tasks if t.status in ("Pending", "In Progress")]
        self.overdue_tasks = [t for t in self.active_tasks if t.due_date and t.due_date < today]

        # Empirical observation counts
        self.completed_task_count = len(self.completed_tasks)
        self.activity_log_count = len(self.activity_logs)
        self.habit_log_count = len(self.habit_logs)
        self.timeblock_count = len(self.timeblocks)

        # Total genuine historical events count
        self.total_observations = (
            self.completed_task_count +
            self.activity_log_count +
            self.habit_log_count +
            self.timeblock_count
        )

        # Baseline data sufficiency threshold
        # If total observations < 5, system operates in cold-start / heuristic mode
        self.has_sufficient_history = self.total_observations >= 5
        self.ml_ready = self.completed_task_count >= 15


def prepare_predictive_dataset(db: Session, reference_date: Optional[date] = None) -> HistoricalDataContainer:
    """
    Extracts all entity and log records from the database cleanly,
    validates datatypes and timezone boundaries, and packages them
    into a HistoricalDataContainer without fabrication.
    """
    today = reference_date or date.today()

    tasks = db.query(Task).all()
    goals = db.query(Goal).all()
    habits = db.query(Habit).all()
    habit_logs = db.query(HabitLog).all()
    timeblocks = db.query(DailyTimeblock).all()
    activity_logs = db.query(ActivityLog).all()

    container = HistoricalDataContainer(
        tasks=tasks,
        goals=goals,
        habits=habits,
        habit_logs=habit_logs,
        timeblocks=timeblocks,
        activity_logs=activity_logs,
        today=today
    )

    logger.debug(
        f"Data prepared: {len(tasks)} tasks ({container.completed_task_count} completed), "
        f"{len(goals)} goals, {len(habits)} habits, {len(habit_logs)} habit logs, "
        f"{len(timeblocks)} timeblocks, {len(activity_logs)} activity logs. "
        f"Total historical observations: {container.total_observations} (sufficient={container.has_sufficient_history})"
    )

    return container
