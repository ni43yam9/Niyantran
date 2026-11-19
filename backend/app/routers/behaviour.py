from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.behaviour import (
    ActivityLogCreate,
    ActivityLogResponse,
    TaskCompletionAnalysis,
    PostponementAnalysis,
    TimeEstimationAnalysis,
    ProductivityHoursAnalysis,
    HabitConsistencyAnalysis,
    DailyPlanningAnalysis,
    BehaviourSummaryResponse,
)
from backend.app.services import behaviour_service

router = APIRouter(prefix="/api/behaviour", tags=["behaviour"])

@router.get("/summary", response_model=BehaviourSummaryResponse)
def get_behaviour_summary(
    tz_offset: int = Query(0, description="Client timezone offset in minutes from UTC (e.g. +330 for IST)"),
    db: Session = Depends(get_db),
):
    """
    Returns aggregated productivity behaviour summary across all 6 monitoring modules.
    """
    return behaviour_service.get_behaviour_summary(db, tz_offset_mins=tz_offset)

@router.get("/task-completion", response_model=TaskCompletionAnalysis)
def get_task_completion_analysis(
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Module A: Task Completion Monitoring (velocity, daily/weekly completion, day of week distribution).
    """
    return behaviour_service.get_task_completion_analysis(db, tz_offset_mins=tz_offset)

@router.get("/postponements", response_model=PostponementAnalysis)
def get_postponement_analysis(
    db: Session = Depends(get_db),
):
    """
    Module B: Procrastination Monitoring (repeated postponements, overdue completions, delay patterns).
    """
    return behaviour_service.get_postponement_analysis(db)

@router.get("/time-estimation", response_model=TimeEstimationAnalysis)
def get_time_estimation_analysis(
    db: Session = Depends(get_db),
):
    """
    Module C: Time Estimation Monitoring (underestimation vs overestimation bias and category breakdown).
    """
    return behaviour_service.get_time_estimation_analysis(db)

@router.get("/productivity-hours", response_model=ProductivityHoursAnalysis)
def get_productivity_hours_analysis(
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Module D: Productivity Time Analysis (time of day quadrants, peak hour window, hourly histogram).
    """
    return behaviour_service.get_productivity_hours_analysis(db, tz_offset_mins=tz_offset)

@router.get("/habit-consistency", response_model=HabitConsistencyAnalysis)
def get_habit_consistency_analysis(
    db: Session = Depends(get_db),
):
    """
    Module E: Habit Consistency Monitoring (30-day streak retention, missed days, ritual execution rate).
    """
    return behaviour_service.get_habit_consistency_analysis(db)

@router.get("/daily-planning", response_model=DailyPlanningAnalysis)
def get_daily_planning_analysis(
    db: Session = Depends(get_db),
):
    """
    Module F: Daily Planning Behaviour (planning accuracy, daily focus capacity adherence, unfinished blocks).
    """
    return behaviour_service.get_daily_planning_analysis(db)

@router.post("/activity", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
def record_activity_log(
    activity_in: ActivityLogCreate,
    db: Session = Depends(get_db),
):
    """
    Records a raw behavioural activity event with automatic deduplication.
    """
    log = behaviour_service.record_activity(
        db=db,
        event_type=activity_in.event_type,
        entity_type=activity_in.entity_type,
        entity_id=activity_in.entity_id,
        timestamp=activity_in.timestamp,
        original_date=activity_in.original_date,
        new_date=activity_in.new_date,
        duration_minutes=activity_in.duration_minutes,
        actual_duration_minutes=activity_in.actual_duration_minutes,
        details=activity_in.details,
    )
    return ActivityLogResponse.model_validate(log)

@router.get("/activities", response_model=List[ActivityLogResponse])
def list_activities(
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Lists recorded raw activity log entries.
    """
    return behaviour_service.get_activities(
        db,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        skip=skip,
    )
