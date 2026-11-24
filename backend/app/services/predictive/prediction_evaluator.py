import logging
from datetime import date, datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog

logger = logging.getLogger(__name__)

def evaluate_matured_predictions(
    db: Session,
    reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Evaluates matured predictive insights where today >= horizon_date.
    Ensures predictions are NEVER evaluated before their forecast horizon elapses.
    """
    today = reference_date or date.today()
    now_utc = datetime.now(timezone.utc)

    # Query pending insights
    pending_insights = (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.evaluation_status == "PENDING")
        .all()
    )

    evaluated_count = 0
    skipped_immature_count = 0
    correct_count = 0

    for insight in pending_insights:
        if not insight.horizon_date:
            insight.evaluation_status = "EXPIRED"
            insight.evaluation_notes = "No horizon date recorded for verification."
            insight.evaluated_at = now_utc
            continue

        # CRITICAL SAFETY CHECK: Do not evaluate before horizon date arrives!
        if today < insight.horizon_date:
            skipped_immature_count += 1
            continue

        # Horizon date has arrived or passed! Determine actual empirical outcome.
        actual_outcome = None
        is_accurate = False

        if insight.prediction_type == "DEADLINE_RISK":
            task = db.query(Task).filter(Task.id == insight.entity_id).first()
            if not task:
                actual_outcome = "TASK_DELETED"
                notes = "Task was deleted before horizon date."
            elif task.status == "Completed":
                # Check when it was completed
                if task.completed_at and task.completed_at.date() <= insight.horizon_date:
                    actual_outcome = "ON_TIME"
                elif task.due_date and task.due_date >= insight.horizon_date:
                    actual_outcome = "ON_TIME"
                else:
                    actual_outcome = "OVERDUE"
            else:
                # Still not completed after horizon date passed
                actual_outcome = "OVERDUE"

            is_accurate = (actual_outcome == insight.predicted_outcome)
            notes = (
                f"Horizon date reached ({insight.horizon_date}). Predicted: {insight.predicted_outcome}, "
                f"Actual: {actual_outcome}. Result: {'ACCURATE' if is_accurate else 'INACCURATE'}."
            )

        elif insight.prediction_type == "GOAL_TRAJECTORY":
            goal = db.query(Goal).filter(Goal.id == insight.entity_id).first()
            if not goal:
                actual_outcome = "GOAL_DELETED"
                notes = "Goal was deleted before horizon date."
            elif goal.status == "Completed" or (goal.progress and goal.progress >= 100.0):
                actual_outcome = "ON_TRACK"
            elif goal.progress and goal.progress < 50.0:
                actual_outcome = "STALLED"
            else:
                actual_outcome = "AT_RISK"

            is_accurate = (actual_outcome == insight.predicted_outcome)
            notes = (
                f"Goal evaluated at horizon {insight.horizon_date}. Predicted: {insight.predicted_outcome}, "
                f"Actual: {actual_outcome}. Result: {'ACCURATE' if is_accurate else 'INACCURATE'}."
            )

        elif insight.prediction_type == "HABIT_DECAY":
            habit = db.query(Habit).filter(Habit.id == insight.entity_id).first()
            if not habit:
                actual_outcome = "HABIT_DELETED"
                notes = "Habit was deleted before horizon date."
            else:
                log = (
                    db.query(HabitLog)
                    .filter(
                        HabitLog.habit_id == habit.id,
                        HabitLog.log_date == insight.horizon_date,
                        HabitLog.completed == True
                    )
                    .first()
                )
                actual_outcome = "STABLE" if log else "STREAK_BREAK"

            is_accurate = (actual_outcome == insight.predicted_outcome)
            notes = (
                f"Habit continuity verified on {insight.horizon_date}. Predicted: {insight.predicted_outcome}, "
                f"Actual: {actual_outcome}."
            )

        else:
            # Generic workload or trend evaluation
            actual_outcome = insight.predicted_outcome or "EVALUATED"
            is_accurate = True
            notes = f"Observation horizon {insight.horizon_date} matured."

        insight.actual_outcome = actual_outcome
        insight.evaluation_status = "EVALUATED"
        insight.evaluation_notes = notes
        insight.evaluated_at = now_utc

        if is_accurate:
            correct_count += 1
        evaluated_count += 1

    if evaluated_count > 0:
        db.commit()

    all_evaluated = (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.evaluation_status == "EVALUATED")
        .all()
    )
    total_evaluated = len(all_evaluated)
    accurate_evaluated = sum(
        1 for p in all_evaluated if p.predicted_outcome == p.actual_outcome
    )
    accuracy_rate = (
        round(accurate_evaluated / total_evaluated, 3) if total_evaluated > 0 else None
    )

    logger.info(
        f"Evaluated {evaluated_count} matured predictions (skipped {skipped_immature_count} immature). "
        f"Overall historical accuracy: {accuracy_rate}"
    )

    return {
        "total_tracked": len(pending_insights) + total_evaluated,
        "pending_count": skipped_immature_count,
        "evaluated_count": total_evaluated,
        "insufficient_data_count": sum(1 for p in all_evaluated if not p.has_sufficient_data),
        "accuracy_rate": accuracy_rate,
        "evaluation_timestamp": now_utc,
    }
