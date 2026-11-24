from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user_optional
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.goal import GoalCreate, GoalUpdate, GoalProgressUpdate, GoalResponse
from backend.app.services import goal_service

router = APIRouter(prefix="/api/goals", tags=["Goals"])

@router.get("", response_model=List[GoalResponse], response_model_by_alias=True)
def list_goals(
    status: Optional[str] = Query(None, description="Filter by status (In Progress, On Track, Behind, Completed)"),
    priority: Optional[str] = Query(None, description="Filter by priority (High, Medium, Low)"),
    goal_type: Optional[str] = Query(None, alias="goalType", description="Filter by goal type (Short-Term, Long-Term)"),
    type: Optional[str] = Query(None, description="Alias for goalType"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in title, description, or key milestone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve all goals with linked task counts, computed progress and days remaining.
    """
    effective_type = goal_type or type
    return goal_service.get_goals(
        db=db,
        status=status,
        priority=priority,
        goal_type=effective_type,
        category=category,
        search=search,
        skip=skip,
        limit=limit,
        user_id=current_user.id,
    )

@router.get("/{goal_id}", response_model=GoalResponse, response_model_by_alias=True)
def get_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve single goal details by ID with ownership verification.
    """
    goal = goal_service.get_goal_by_id(db, goal_id, user_id=current_user.id)
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal with ID '{goal_id}' not found",
        )
    return goal

@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=True)
def create_goal(
    goal_in: GoalCreate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Create a new goal associated with the current user account.
    """
    return goal_service.create_goal(db, goal_in, user_id=current_user.id)

@router.put("/{goal_id}", response_model=GoalResponse, response_model_by_alias=True)
def update_goal(
    goal_id: str,
    goal_in: GoalUpdate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Update an existing goal by ID with ownership verification.
    """
    updated = goal_service.update_goal(db, goal_id, goal_in, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal with ID '{goal_id}' not found",
        )
    return updated

@router.delete("/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a goal by ID. Linked tasks will have goal_id set to null.
    """
    success = goal_service.delete_goal(db, goal_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal with ID '{goal_id}' not found",
        )
    return {"message": "Goal deleted successfully", "id": goal_id}

@router.patch("/{goal_id}/progress", response_model=GoalResponse, response_model_by_alias=True)
def update_goal_progress(
    goal_id: str,
    progress_in: GoalProgressUpdate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Convenience endpoint: Update a goal's progress percentage with ownership verification.
    """
    updated = goal_service.update_goal_progress(
        db, goal_id, progress=progress_in.progress, status=progress_in.status, user_id=current_user.id
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal with ID '{goal_id}' not found",
        )
    return updated
