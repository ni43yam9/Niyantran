import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.adaptive import (
    ProductivityProfileResponse,
    ProfileRefreshResponse,
    LearnedPatternsResponse,
    PredictionCalibrationResponse,
    AdaptiveSchedulingResponse,
)
from backend.app.services.adaptive import (
    get_or_build_profile,
    build_or_refresh_profile,
    get_learned_patterns_response,
    calibrate_predictions,
    generate_adaptive_scheduling_suggestions,
    analyze_recommendation_interactions,
    learn_working_periods,
    learn_workload_tolerance,
)
from backend.app.models.task import Task
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/adaptive",
    tags=["adaptive-intelligence"],
    responses={404: {"description": "Resource not found"}},
)

@router.get("/profile", response_model=ProductivityProfileResponse)
def get_user_productivity_profile(
    force_refresh: bool = Query(False, description="Whether to recompute profile on demand"),
    db: Session = Depends(get_db),
):
    """
    Returns the latest personal productivity profile and learned behavioral tendencies.
    """
    profile = get_or_build_profile(db, user_id="default_user", force_refresh=force_refresh)
    return profile

@router.post("/profile/refresh", response_model=ProfileRefreshResponse)
def refresh_user_productivity_profile(
    db: Session = Depends(get_db),
):
    """
    Triggers an immediate full learning cycle across all historical user activity,
    updates the database profile, and returns learning summary metrics.
    """
    profile = build_or_refresh_profile(db, user_id="default_user")
    patterns_count = 8

    return ProfileRefreshResponse(
        status="SUCCESS",
        profile_id=profile.id,
        user_id=profile.user_id,
        patterns_identified=patterns_count,
        overall_confidence=profile.confidence_score,
        has_sufficient_history=profile.has_sufficient_history,
        refreshed_at=datetime.now(timezone.utc),
    )

@router.get("/patterns", response_model=LearnedPatternsResponse)
def get_learned_patterns(
    db: Session = Depends(get_db),
):
    """
    Returns granular learned behavioral patterns across all 8 productivity domains,
    including sample sizes, statistical confidences, and empirical supporting evidence.
    """
    return get_learned_patterns_response(db, user_id="default_user")

@router.get("/calibration", response_model=PredictionCalibrationResponse)
def get_prediction_calibration(
    db: Session = Depends(get_db),
):
    """
    Evaluates Phase 6 predictions against empirical outcomes, returning Brier score,
    calibration bias (overconfidence vs underconfidence), reliability bins,
    and validated advisory calibration factors.
    """
    return calibrate_predictions(db)

@router.get("/scheduling-suggestions", response_model=AdaptiveSchedulingResponse)
def get_adaptive_scheduling_suggestions(
    db: Session = Depends(get_db),
):
    """
    Generates personalized scheduling suggestions matching complex tasks to learned peak energy windows,
    lightweight tasks to secondary windows, and redistributing overloaded days.
    Guarantees zero automatic modification of task schedules.
    """
    tasks = db.query(Task).all()
    timeblocks = db.query(DailyTimeblock).all()
    activity_logs = db.query(ActivityLog).all()

    working_periods = learn_working_periods(timeblocks, activity_logs, tasks)
    workload_tolerance = learn_workload_tolerance(timeblocks, tasks, activity_logs)

    return generate_adaptive_scheduling_suggestions(
        db=db,
        working_periods=working_periods,
        workload_tolerance=workload_tolerance,
    )

@router.get("/recommendation-weights")
def get_adaptive_recommendation_weights(
    db: Session = Depends(get_db),
):
    """
    Returns adaptive recommendation weights and interaction metrics per recommendation type,
    including acceptance, dismissal, execution rates, and time-decay status on dismissal penalties.
    """
    receptivity = analyze_recommendation_interactions(db)
    return {
        "total_interactions": receptivity.total_interactions,
        "overall_acceptance_rate": receptivity.acceptance_rate,
        "overall_dismissal_rate": receptivity.dismissal_rate,
        "overall_execution_rate": receptivity.execution_rate,
        "ignored_count": receptivity.ignored_count,
        "adaptive_type_weights": receptivity.adaptive_type_weights,
        "receptivity_by_type": receptivity.receptivity_by_type,
        "most_favored_type": receptivity.most_favored_type,
        "most_dismissed_type": receptivity.most_dismissed_type,
        "confidence": receptivity.confidence,
        "has_sufficient_data": receptivity.has_sufficient_data,
        "evidence": receptivity.evidence,
    }
