from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.habit import HabitCreate, HabitUpdate, HabitResponse, HabitLogCreate
from backend.app.services import habit_service

router = APIRouter(prefix="/api/habits", tags=["Habits"])

@router.get("", response_model=List[HabitResponse], response_model_by_alias=True)
def list_habits(
    include_archived: bool = Query(False, alias="includeArchived"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all habits with historical logs and completed dates.
    """
    return habit_service.get_habits(db, include_archived=include_archived)

@router.post("", response_model=HabitResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def create_habit(habit_in: HabitCreate, db: Session = Depends(get_db)):
    """
    Create a new habit with optional pre-filled completed dates.
    """
    return habit_service.create_habit(db, habit_in)

@router.get("/{habit_id}", response_model=HabitResponse, response_model_by_alias=True)
def get_habit(habit_id: str, db: Session = Depends(get_db)):
    """
    Retrieve single habit details by ID.
    """
    habit = habit_service.get_habit_by_id(db, habit_id)
    if not habit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return habit

@router.put("/{habit_id}", response_model=HabitResponse, response_model_by_alias=True)
def update_habit(habit_id: str, habit_in: HabitUpdate, db: Session = Depends(get_db)):
    """
    Update habit metadata.
    """
    updated = habit_service.update_habit(db, habit_id, habit_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return updated

@router.delete("/{habit_id}", status_code=status.HTTP_200_OK)
def delete_habit(habit_id: str, db: Session = Depends(get_db)):
    """
    Delete a habit and all associated historical logs.
    """
    success = habit_service.delete_habit(db, habit_id)
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
    db: Session = Depends(get_db),
):
    """
    Toggle completion status for a habit on a specific date.
    Preserves historical streaks across weekly calendar resets.
    """
    target_date = log_date or date.today()
    updated = habit_service.toggle_habit_log(db, habit_id, target_date, completed)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habit with ID '{habit_id}' not found",
        )
    return updated
