from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user_optional
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.daily_intent import (
    DailyIntentCreate,
    DailyIntentUpdate,
    DailyIntentResponse,
)
from backend.app.services import daily_intent_service

router = APIRouter(prefix="/api/daily-intents", tags=["Daily Intents"])


@router.get("", response_model=List[DailyIntentResponse])
def list_daily_intents(
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    user_id: Optional[str] = Query(None, description="User ID"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Lists daily intent directives sorted by date descending."""
    eff_user_id = user_id or current_user.id
    return daily_intent_service.list_daily_intents(
        db=db,
        user_id=eff_user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@router.get("/{target_date}", response_model=DailyIntentResponse)
def get_daily_intent(
    target_date: date,
    user_id: Optional[str] = Query(None, description="User ID"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Retrieves the active daily intent for a specific date."""
    eff_user_id = user_id or current_user.id
    intent = daily_intent_service.get_daily_intent_by_date(db, intent_date=target_date, user_id=eff_user_id)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active daily intent found for date {target_date}",
        )
    return intent


@router.post("", response_model=DailyIntentResponse, status_code=status.HTTP_201_CREATED)
def set_daily_intent(
    intent_in: DailyIntentCreate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Creates or updates the daily intent for a specific date (idempotent upsert).
    Increments version on update for future offline-first synchronization.
    """
    if not intent_in.user_id or intent_in.user_id == "default_user":
        intent_in.user_id = current_user.id
    return daily_intent_service.upsert_daily_intent(db, intent_in)


@router.delete("/{target_date}")
def delete_daily_intent(
    target_date: date,
    user_id: Optional[str] = Query(None, description="User ID"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Soft-deletes the daily intent for a specific date.
    Preserves tombstone metadata for future distributed deletion sync.
    """
    eff_user_id = user_id or current_user.id
    success = daily_intent_service.soft_delete_daily_intent(db, intent_date=target_date, user_id=eff_user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Daily intent for date {target_date} not found",
        )
    return {"status": "success", "message": f"Daily intent for {target_date} soft-deleted successfully"}
