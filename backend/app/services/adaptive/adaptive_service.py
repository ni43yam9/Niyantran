import logging
import uuid
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.models.adaptive_profile import UserProductivityProfile
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.adaptive import (
    LearnedPatternsResponse,
    PredictionCalibrationResponse,
    AdaptiveSchedulingResponse,
    ProfileRefreshResponse,
)
from backend.app.services.adaptive.behaviour_learner import (
    learn_working_periods,
    learn_task_tendencies,
    learn_postponements,
    learn_estimation_bias,
    learn_habit_consistency,
    learn_goal_progress,
    learn_workload_tolerance,
)
from backend.app.services.adaptive.adaptive_recommender import (
    analyze_recommendation_interactions,
)
from backend.app.services.adaptive.calibration_engine import (
    calibrate_predictions,
)
from backend.app.services.adaptive.scheduling_advisor import (
    generate_adaptive_scheduling_suggestions,
)
from backend.app.services.adaptive.confidence_manager import (
    MIN_EVENTS_FULL_PROFILE,
    calculate_sample_confidence,
)

logger = logging.getLogger(__name__)

def build_or_refresh_profile(
    db: Session,
    user_id: str = "default_user",
    reference_date: Optional[date] = None,
    now_utc: Optional[datetime] = None,
) -> UserProductivityProfile:
    """
    Executes a complete adaptive learning cycle across all historical activity,
    extracts personalized behavioral patterns, prediction calibrations,
    and updates the persistent UserProductivityProfile record.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = reference_date or now.date() if isinstance(now, datetime) else date.today()

    # Query all raw domain records
    tasks = db.query(Task).all()
    goals = db.query(Goal).all()
    habits = db.query(Habit).all()
    habit_logs = db.query(HabitLog).all()
    timeblocks = db.query(DailyTimeblock).all()
    activity_logs = db.query(ActivityLog).all()

    # 1. Learn Behavioral Patterns
    working_periods = learn_working_periods(timeblocks, activity_logs, tasks, now_utc=now)
    task_tendencies = learn_task_tendencies(tasks, activity_logs)
    postponements = learn_postponements(tasks, activity_logs)
    estimation_bias = learn_estimation_bias(timeblocks)
    habit_consistency = learn_habit_consistency(habits, habit_logs, now_utc=now)
    goal_progress = learn_goal_progress(goals, tasks)
    workload_tolerance = learn_workload_tolerance(timeblocks, tasks, activity_logs)

    # 2. Analyze Recommendation Interactions
    recs_receptivity = analyze_recommendation_interactions(db, now_utc=now)

    # 3. Prediction Calibration
    calibration = calibrate_predictions(db, reference_date=today, now_utc=now)

    # 4. Compute Overall Confidence & History Sufficiency
    total_data_points = (
        working_periods.sample_size
        + task_tendencies.sample_size
        + postponements.sample_size
        + estimation_bias.sample_size
        + habit_consistency.sample_size
        + recs_receptivity.sample_size
    )

    confidences = [
        working_periods.confidence,
        task_tendencies.confidence,
        postponements.confidence,
        estimation_bias.confidence,
        habit_consistency.confidence,
        goal_progress.confidence,
        recs_receptivity.confidence,
    ]
    overall_confidence = round(sum(confidences) / len(confidences), 2)
    has_sufficient_history = (
        total_data_points >= MIN_EVENTS_FULL_PROFILE
        and working_periods.has_sufficient_data
        and task_tendencies.has_sufficient_data
    )

    # Serialize structured profile data
    profile_data_dict: Dict[str, Any] = {
        "working_periods": working_periods.model_dump(),
        "task_tendencies": task_tendencies.model_dump(),
        "postponements": postponements.model_dump(),
        "estimation_bias": estimation_bias.model_dump(),
        "habit_consistency": habit_consistency.model_dump(),
        "goal_progress": goal_progress.model_dump(),
        "workload_tolerance": workload_tolerance.model_dump(),
        "recommendations": recs_receptivity.model_dump(),
        "calibration": calibration.model_dump(exclude={"evaluated_at"}),
        "total_data_points": total_data_points,
    }

    # Query existing profile for today or create new
    existing_profile = (
        db.query(UserProductivityProfile)
        .filter(
            UserProductivityProfile.user_id == user_id,
            UserProductivityProfile.profile_date == today,
        )
        .first()
    )

    if not existing_profile:
        existing_profile = UserProductivityProfile(
            id=f"prof_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            profile_date=today,
        )
        db.add(existing_profile)

    # Update profile fields
    existing_profile.peak_time_window = working_periods.peak_time_window
    existing_profile.peak_days = working_periods.peak_days
    existing_profile.preferred_session_duration_minutes = working_periods.preferred_session_duration_minutes
    existing_profile.optimal_daily_load_minutes = workload_tolerance.optimal_daily_load_minutes
    existing_profile.max_observed_sustainable_minutes = workload_tolerance.max_observed_sustainable_minutes
    existing_profile.duration_bias_factor = estimation_bias.duration_bias_factor
    existing_profile.is_bias_empirical = estimation_bias.is_empirical
    existing_profile.task_completion_rate = task_tendencies.completion_rate
    existing_profile.postponement_rate = postponements.postponement_rate
    existing_profile.procrastination_level = postponements.procrastination_level
    existing_profile.habit_stability = habit_consistency.habit_stability
    existing_profile.recommendation_weights = recs_receptivity.adaptive_type_weights
    existing_profile.calibration_metrics = {
        "brier_score": calibration.brier_score,
        "calibration_bias": calibration.calibration_bias,
        "calibration_status": calibration.calibration_status,
        "advisory_calibration_factor": calibration.advisory_calibration_factor,
    }
    existing_profile.profile_data = profile_data_dict
    existing_profile.confidence_score = overall_confidence
    existing_profile.has_sufficient_history = has_sufficient_history
    existing_profile.updated_at = now

    db.commit()
    db.refresh(existing_profile)
    logger.info(
        f"Updated UserProductivityProfile for user '{user_id}': peak={existing_profile.peak_time_window}, "
        f"conf={overall_confidence:.2f}, sufficient_data={has_sufficient_history}"
    )

    return existing_profile

def get_or_build_profile(
    db: Session,
    user_id: str = "default_user",
    force_refresh: bool = False,
    now_utc: Optional[datetime] = None,
) -> UserProductivityProfile:
    """
    Returns the latest profile from the database, or computes it if none exists or if force_refresh is requested.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()

    if not force_refresh:
        latest = (
            db.query(UserProductivityProfile)
            .filter(UserProductivityProfile.user_id == user_id)
            .order_by(UserProductivityProfile.profile_date.desc(), UserProductivityProfile.updated_at.desc())
            .first()
        )
        if latest and latest.profile_date == today:
            return latest

    return build_or_refresh_profile(db, user_id=user_id, reference_date=today, now_utc=now)

def get_learned_patterns_response(
    db: Session,
    user_id: str = "default_user",
    now_utc: Optional[datetime] = None,
) -> LearnedPatternsResponse:
    """
    Generates and returns the detailed 8-domain LearnedPatternsResponse.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()

    tasks = db.query(Task).all()
    goals = db.query(Goal).all()
    habits = db.query(Habit).all()
    habit_logs = db.query(HabitLog).all()
    timeblocks = db.query(DailyTimeblock).all()
    activity_logs = db.query(ActivityLog).all()

    working_periods = learn_working_periods(timeblocks, activity_logs, tasks, now_utc=now)
    task_tendencies = learn_task_tendencies(tasks, activity_logs)
    postponements = learn_postponements(tasks, activity_logs)
    estimation_bias = learn_estimation_bias(timeblocks)
    habit_consistency = learn_habit_consistency(habits, habit_logs, now_utc=now)
    goal_progress = learn_goal_progress(goals, tasks)
    workload_tolerance = learn_workload_tolerance(timeblocks, tasks, activity_logs)
    recs = analyze_recommendation_interactions(db, now_utc=now)

    total_data_points = (
        working_periods.sample_size
        + task_tendencies.sample_size
        + postponements.sample_size
        + estimation_bias.sample_size
        + habit_consistency.sample_size
        + recs.sample_size
    )

    confidences = [
        working_periods.confidence,
        task_tendencies.confidence,
        postponements.confidence,
        estimation_bias.confidence,
        habit_consistency.confidence,
        goal_progress.confidence,
        recs.confidence,
    ]
    overall_confidence = round(sum(confidences) / len(confidences), 2)
    has_sufficient_history = (
        total_data_points >= MIN_EVENTS_FULL_PROFILE
        and working_periods.has_sufficient_data
        and task_tendencies.has_sufficient_data
    )

    return LearnedPatternsResponse(
        user_id=user_id,
        evaluation_date=today,
        working_periods=working_periods,
        task_tendencies=task_tendencies,
        postponements=postponements,
        estimation_bias=estimation_bias,
        habits=habit_consistency,
        goals=goal_progress,
        recommendations=recs,
        workload_tolerance=workload_tolerance,
        overall_confidence=overall_confidence,
        has_sufficient_history=has_sufficient_history,
    )
