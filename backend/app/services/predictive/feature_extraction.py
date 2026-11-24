import logging
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from backend.app.services.predictive.data_preparation import HistoricalDataContainer

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """
    Computes mathematical and statistical indicators from HistoricalDataContainer.
    Maintains transparency: explicitly tags whether features are based on empirical
    observations or heuristic defaults due to sparse data.
    """
    def __init__(self, data: HistoricalDataContainer):
        self.data = data
        self.today = data.today

        # Build task-to-timeblocks index
        self.task_timeblocks: Dict[str, List[Any]] = {}
        for tb in self.data.timeblocks:
            if tb.task_id:
                self.task_timeblocks.setdefault(tb.task_id, []).append(tb)

        # Build task postponement index from ActivityLog
        self.task_postpones: Dict[str, int] = {}
        for act in self.data.activity_logs:
            if act.event_type == "TASK_POSTPONED" and act.entity_id:
                self.task_postpones[act.entity_id] = self.task_postpones.get(act.entity_id, 0) + 1

    def get_task_estimated_duration(self, task) -> int:
        """
        Determines estimated duration in minutes from linked timeblock or defaults to 60m.
        """
        tbs = self.task_timeblocks.get(task.id, [])
        if tbs and tbs[0].duration_minutes:
            return tbs[0].duration_minutes
        return 60

    def get_task_postpone_count(self, task) -> int:
        """
        Gets count of postponements for this task from ActivityLog.
        """
        return self.task_postpones.get(task.id, 0)

    def extract_task_features(self) -> Dict[str, Any]:
        """
        Extracts completion velocity, estimation bias, and postponement factors.
        """
        completed = self.data.completed_tasks
        n_completed = len(completed)

        # 1. Estimation Bias Ratio from timeblocks and activity logs
        bias_ratios = []
        for tb in self.data.timeblocks:
            if tb.duration_minutes and tb.duration_minutes > 0 and tb.actual_duration_minutes and tb.actual_duration_minutes > 0:
                bias_ratios.append(float(tb.actual_duration_minutes) / float(tb.duration_minutes))

        for act in self.data.activity_logs:
            if act.duration_minutes and act.duration_minutes > 0 and act.actual_duration_minutes and act.actual_duration_minutes > 0:
                bias_ratios.append(float(act.actual_duration_minutes) / float(act.duration_minutes))

        if len(bias_ratios) >= 3:
            avg_estimation_bias = sum(bias_ratios) / len(bias_ratios)
            is_bias_heuristic = False
            bias_sample_size = len(bias_ratios)
        else:
            # Baseline heuristic: humans typically underestimate task duration by 25%
            avg_estimation_bias = 1.25
            is_bias_heuristic = True
            bias_sample_size = len(bias_ratios)

        # 2. Completion Velocity & Creation Trends
        seven_days_ago = self.today - timedelta(days=7)
        fourteen_days_ago = self.today - timedelta(days=14)

        recent_completions_7d = [
            t for t in completed
            if t.completed_at and t.completed_at.date() >= seven_days_ago
        ]
        prev_completions_7d = [
            t for t in completed
            if t.completed_at and fourteen_days_ago <= t.completed_at.date() < seven_days_ago
        ]
        recent_creations_7d = [
            t for t in self.data.tasks
            if t.created_at and t.created_at.date() >= seven_days_ago
        ]
        prev_creations_7d = [
            t for t in self.data.tasks
            if t.created_at and fourteen_days_ago <= t.created_at.date() < seven_days_ago
        ]

        recent_completions = [
            t for t in completed
            if t.completed_at and t.completed_at.date() >= fourteen_days_ago
        ]
        daily_velocity_14d = len(recent_completions) / 14.0

        # If zero recent completions with timestamps, check if any completed tasks exist
        if daily_velocity_14d == 0.0 and n_completed > 0:
            daily_velocity_14d = min(1.0, n_completed / 30.0)

        # Backlog Expansion vs Real Productivity Detection
        is_backlog_expanding = (
            len(recent_creations_7d) >= 2 * max(1, len(recent_completions_7d))
            and len(recent_completions_7d) <= max(1, len(prev_completions_7d))
        )

        # 3. Postponement Tendency
        total_postponements = sum(self.task_postpones.values())
        avg_postponements_per_task = (
            total_postponements / len(self.data.tasks) if self.data.tasks else 0.0
        )

        return {
            "n_completed_tasks": n_completed,
            "estimation_bias_ratio": round(avg_estimation_bias, 3),
            "is_bias_heuristic": is_bias_heuristic,
            "bias_sample_size": bias_sample_size,
            "daily_task_velocity": round(daily_velocity_14d, 3),
            "weekly_task_velocity": round(daily_velocity_14d * 7.0, 2),
            "completions_recent_7d": len(recent_completions_7d),
            "completions_prev_7d": len(prev_completions_7d),
            "creations_recent_7d": len(recent_creations_7d),
            "creations_prev_7d": len(prev_creations_7d),
            "is_backlog_expanding": is_backlog_expanding,
            "total_postponements": total_postponements,
            "avg_postponements_per_task": round(avg_postponements_per_task, 2),
        }

    def extract_workload_features(self) -> Dict[str, Any]:
        """
        Calculates daily capacity and forward 7-day projected load.
        """
        # Daily capacity (in minutes). Standard baseline: 240 mins (4.0 hrs)
        actual_minutes_per_day: Dict[date, int] = {}
        for tb in self.data.timeblocks:
            if tb.actual_duration_minutes and tb.actual_duration_minutes > 0:
                actual_minutes_per_day[tb.block_date] = (
                    actual_minutes_per_day.get(tb.block_date, 0) + tb.actual_duration_minutes
                )

        if len(actual_minutes_per_day) >= 3:
            daily_capacity = sum(actual_minutes_per_day.values()) / len(actual_minutes_per_day)
            is_capacity_heuristic = False
        else:
            daily_capacity = 240.0
            is_capacity_heuristic = True

        # Forward 7-day projection: sums estimated duration of tasks due and scheduled timeblocks on each date
        forecast_days = {}
        for i in range(1, 8):
            f_date = self.today + timedelta(days=i)
            tasks_due = [
                t for t in self.data.active_tasks
                if t.due_date == f_date
            ]
            high_prio_count = sum(1 for t in tasks_due if (getattr(t, "priority", "") or "").upper() == "HIGH")

            tbs_on_date = [
                tb for tb in self.data.timeblocks
                if tb.block_date == f_date
            ]
            tb_minutes = sum(tb.duration_minutes for tb in tbs_on_date if tb.duration_minutes)
            linked_tb_task_ids = {tb.task_id for tb in tbs_on_date if tb.task_id}
            task_minutes = sum(
                self.get_task_estimated_duration(t) for t in tasks_due
                if t.id not in linked_tb_task_ids
            )
            total_minutes = tb_minutes + task_minutes
            overload_ratio = round(total_minutes / daily_capacity, 2) if daily_capacity > 0 else 1.0

            forecast_days[f_date.isoformat()] = {
                "date": f_date,
                "task_count": len(tasks_due),
                "high_priority_task_count": high_prio_count,
                "total_estimated_minutes": total_minutes,
                "daily_capacity_minutes": round(daily_capacity, 1),
                "overload_ratio": overload_ratio,
                "is_overloaded": overload_ratio > 1.25 or total_minutes > 360,
                "is_conflict": high_prio_count >= 2,
                "is_light": total_minutes < 180 and overload_ratio < 0.60,
            }

        # Consecutive high-pressure streak detection (2+ days with >= 80% capacity)
        consecutive_heavy: List[List[date]] = []
        current_streak: List[date] = []
        for i in range(1, 8):
            f_date = self.today + timedelta(days=i)
            day_info = forecast_days[f_date.isoformat()]
            if day_info["overload_ratio"] >= 0.80 or day_info["total_estimated_minutes"] >= 240:
                current_streak.append(f_date)
            else:
                if len(current_streak) >= 2:
                    consecutive_heavy.append(current_streak)
                current_streak = []
        if len(current_streak) >= 2:
            consecutive_heavy.append(current_streak)

        return {
            "daily_capacity_minutes": round(daily_capacity, 1),
            "is_capacity_heuristic": is_capacity_heuristic,
            "forecast_7d": forecast_days,
            "high_pressure_periods": consecutive_heavy,
        }

    def extract_goal_features(self, goal) -> Dict[str, Any]:
        """
        Computes velocity deficit, trajectory metrics, and sufficiency check for a single goal.
        """
        progress = float(goal.progress or 0.0)
        remaining_progress = max(0.0, 100.0 - progress)

        start_date = goal.start_date or (self.today - timedelta(days=7))
        target_date = goal.target_date or (self.today + timedelta(days=30))

        days_elapsed = max(1, (self.today - start_date).days)
        days_remaining = (target_date - self.today).days

        historical_velocity = progress / days_elapsed
        required_velocity = (
            remaining_progress / max(1, days_remaining) if days_remaining > 0 else remaining_progress
        )
        velocity_deficit = max(0.0, required_velocity - historical_velocity)

        linked_tasks = [t for t in self.data.tasks if t.goal_id == goal.id]
        linked_total = len(linked_tasks)
        linked_completed = len([t for t in linked_tasks if t.status == "Completed"])
        linked_pending = linked_total - linked_completed

        seven_days_ago = self.today - timedelta(days=7)
        recent_completed_7d = len([
            t for t in linked_tasks
            if t.status == "Completed" and t.completed_at and t.completed_at.date() >= seven_days_ago
        ])

        # Sufficiency guard: newly created goals (< 3 days elapsed) with zero progress or completions
        has_sufficient_history = True
        if days_elapsed < 3 and linked_completed == 0 and progress == 0.0:
            has_sufficient_history = False

        return {
            "progress": progress,
            "remaining_progress": remaining_progress,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "historical_velocity": round(historical_velocity, 2),
            "required_velocity": round(required_velocity, 2),
            "velocity_deficit": round(velocity_deficit, 2),
            "linked_tasks_total": linked_total,
            "linked_tasks_completed": linked_completed,
            "linked_tasks_pending": linked_pending,
            "recent_completed_7d": recent_completed_7d,
            "has_sufficient_history": has_sufficient_history,
        }

    def extract_habit_features(self, habit) -> Dict[str, Any]:
        """
        Extracts streak continuity, recent adherence rates, and break vulnerability.
        """
        logs = [hl for hl in self.data.habit_logs if hl.habit_id == habit.id and hl.completed]
        logged_dates = {hl.log_date for hl in logs}

        last_7_days = [self.today - timedelta(days=i) for i in range(1, 8)]
        completed_last_7 = sum(1 for d in last_7_days if d in logged_dates)
        adherence_7d = round(completed_last_7 / 7.0, 2)

        last_14_days = [self.today - timedelta(days=i) for i in range(1, 15)]
        completed_last_14 = sum(1 for d in last_14_days if d in logged_dates)
        adherence_14d = round(completed_last_14 / 14.0, 2)

        last_4_days = [self.today - timedelta(days=i) for i in range(1, 5)]
        completed_last_4 = sum(1 for d in last_4_days if d in logged_dates)
        missed_last_4 = 4 - completed_last_4

        done_today = self.today in logged_dates

        if logged_dates:
            most_recent_date = max(logged_dates)
            days_since_last_log = (self.today - most_recent_date).days
        else:
            days_since_last_log = None

        streak = habit.base_streak or 0
        is_daily = (habit.frequency or "Daily").lower() == "daily"

        is_streak_vulnerable = False
        if is_daily and streak >= 2 and not done_today:
            is_streak_vulnerable = True
        elif is_daily and streak > 0 and days_since_last_log is not None and days_since_last_log >= 2:
            is_streak_vulnerable = True

        declining_consistency = (adherence_7d < adherence_14d - 0.20) and len(logs) >= 3
        missed_pattern = (missed_last_4 >= 2) and (streak < 2)

        return {
            "habit_id": habit.id,
            "streak_count": streak,
            "frequency": habit.frequency,
            "total_logs": len(logs),
            "completed_last_7": completed_last_7,
            "adherence_rate_7d": adherence_7d,
            "adherence_rate_14d": adherence_14d,
            "missed_last_4": missed_last_4,
            "done_today": done_today,
            "days_since_last_log": days_since_last_log,
            "is_streak_vulnerable": is_streak_vulnerable,
            "declining_consistency": declining_consistency,
            "missed_pattern": missed_pattern,
        }
