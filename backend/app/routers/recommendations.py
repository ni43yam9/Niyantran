from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
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
    db: Session = Depends(get_db),
):
    """
    Retrieves intelligent productivity recommendations with summary metrics.
    """
    return recommendation_service.get_recommendations(
        db=db,
        status=status,
        category=category,
        rec_type=rec_type,
        limit=limit,
    )

@router.post("/generate", response_model=RecommendationSummary)
def generate_recommendations(db: Session = Depends(get_db)):
    """
    Forces immediate evaluation and generation of recommendations.
    """
    recommendation_service.generate_recommendations(db)
    return recommendation_service.get_recommendations(db=db, status="PENDING")

@router.post("/{rec_id}/accept", response_model=RecommendationResponse)
def accept_recommendation(rec_id: str, db: Session = Depends(get_db)):
    """
    Accepts a recommendation and safely triggers associated actions (e.g. rescheduling tasks).
    """
    rec = recommendation_service.accept_recommendation(db=db, rec_id=rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec

@router.post("/{rec_id}/dismiss", response_model=RecommendationResponse)
def dismiss_recommendation(rec_id: str, db: Session = Depends(get_db)):
    """
    Dismisses a recommendation.
    """
    rec = recommendation_service.dismiss_recommendation(db=db, rec_id=rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec

@router.post("/{rec_id}/complete", response_model=RecommendationResponse)
def complete_recommendation(rec_id: str, db: Session = Depends(get_db)):
    """
    Marks a recommendation as completed.
    """
    rec = recommendation_service.complete_recommendation(db=db, rec_id=rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec
