from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user_optional
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.habit import HabitCreate, HabitUpdate, HabitResponse
from backend.app.services import habit_service

router = APIRouter(prefix="/api/habits", tags=["Habits"])

@router.get("", response_model=List[HabitResponse], response_model_by_alias=True)
def list_habits(
    include_archived: bool = Query(False, alias="includeArchived"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve all habits with historical logs and completed dates for the current user.
    """
    return habit_service.get_habits(db, include_archived=include_archived, user_id=current_user.id)

@router.post("", response_model=HabitResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def create_habit(
    habit_in: HabitCreate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Create a new habit associated with current user.
    """
    return habit_service.create_habit(db, habit_in, user_id=current_user.id)

@router.get("/{habit_id}", response_model=HabitResponse, response_model_by_alias=True)
def get_habit(
    habit_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve single habit details by ID with ownership verification.
    """
    habit = habit_service.get_habit_by_id(db, habit_id, user_id=current_user.id)
    if not habit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return habit

@router.put("/{habit_id}", response_model=HabitResponse, response_model_by_alias=True)
def update_habit(
    habit_id: str,
    habit_in: HabitUpdate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Update habit metadata with ownership verification.
    """
    updated = habit_service.update_habit(db, habit_id, habit_in, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return updated

@router.delete("/{habit_id}", status_code=status.HTTP_200_OK)
def delete_habit(
    habit_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Delete a habit and all associated historical logs with ownership verification.
    """
    success = habit_service.delete_habit(db, habit_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return {"message": f"Habit '{habit_id}' deleted successfully"}

@router.post("/{habit_id}/toggle", response_model=HabitResponse, response_model_by_alias=True)
def toggle_habit_status(
    habit_id: str,
    log_date: Optional[date] = Query(None, alias="date", description="Date to toggle YYYY-MM-DD (defaults to today)"),
    completed: Optional[bool] = Query(None, description="Explicit completed state, or toggle if omitted"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Toggle completion status for a habit on a specific date with ownership verification.
    Preserves historical streaks across weekly calendar resets.
    """
    target_date = log_date or date.today()
    updated = habit_service.toggle_habit_log(db, habit_id, target_date, completed, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return updated
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return updated
