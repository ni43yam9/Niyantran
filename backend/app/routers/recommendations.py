from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user_optional
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.recommendation import (
    RecommendationResponse,
    RecommendationSummary,
)
from backend.app.services import recommendation_service

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])

@router.get("", response_model=RecommendationSummary)
def list_recommendations(
    status: Optional[str] = Query("PENDING", description="PENDING, ACCEPTED, DISMISSED, COMPLETED, or ALL"),
    category: Optional[str] = Query(None, description="Task, Goal, Habit, Schedule"),
    rec_type: Optional[str] = Query(None, description="PRIORITIZATION, DEADLINE_RISK, WORKLOAD_BALANCE, GOAL_PROGRESS, HABIT_IMPROVEMENT"),
    limit: int = Query(50, ge=1, le=200),
    cooldown_hours: int = Query(48, ge=1, le=720, description="Dismissal cooldown in hours"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieves intelligent productivity recommendations with summary metrics.
    Automatically respects deduplication and dismissal cooldowns.
    """
    return recommendation_service.get_recommendations(
        db=db,
        status=status,
        category=category,
        rec_type=rec_type,
        limit=limit,
        cooldown_hours=cooldown_hours,
        user_id=current_user.id,
    )

@router.post("/generate", response_model=RecommendationSummary)
def generate_recommendations(
    cooldown_hours: int = Query(48, ge=1, le=720, description="Dismissal cooldown in hours"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Forces immediate evaluation and generation of recommendations with deduplication and cooldown.
    """
    recommendation_service.generate_recommendations(db, cooldown_hours=cooldown_hours)
    return recommendation_service.get_recommendations(
        db=db, status="PENDING", cooldown_hours=cooldown_hours, user_id=current_user.id
    )

@router.post("/{rec_id}/accept", response_model=RecommendationResponse)
def accept_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Accepts a recommendation and safely triggers associated actions (e.g. rescheduling tasks).
    Validates lifecycle transition from PENDING -> ACCEPTED.
    """
    try:
        rec = recommendation_service.accept_recommendation(db=db, rec_id=rec_id, user_id=current_user.id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return rec
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

@router.post("/{rec_id}/dismiss", response_model=RecommendationResponse)
def dismiss_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Dismisses a recommendation with 48h cooldown enforcement.
    Validates lifecycle transition from PENDING -> DISMISSED.
    """
    try:
        rec = recommendation_service.dismiss_recommendation(db=db, rec_id=rec_id, user_id=current_user.id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return rec
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

@router.post("/{rec_id}/complete", response_model=RecommendationResponse)
def complete_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Marks a recommendation as completed.
    Validates lifecycle transition from PENDING/ACCEPTED -> COMPLETED.
    """
    try:
        rec = recommendation_service.complete_recommendation(db=db, rec_id=rec_id, user_id=current_user.id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return rec
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
