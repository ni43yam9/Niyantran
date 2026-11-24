from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user_optional
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from backend.app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

@router.get("", response_model=List[TaskResponse], response_model_by_alias=True)
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status (Pending, In Progress, Completed)"),
    priority: Optional[str] = Query(None, description="Filter by priority (High, Medium, Low)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    task_type: Optional[str] = Query(None, alias="taskType", description="Filter by task type"),
    search: Optional[str] = Query(None, description="Search in title or description"),
    is_today: Optional[bool] = Query(None, alias="isToday", description="Filter tasks due today or starting today"),
    is_overdue: Optional[bool] = Query(None, alias="isOverdue", description="Filter overdue pending tasks"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve all tasks with optional multi-criteria filtering, search, and pagination.
    """
    return task_service.get_tasks(
        db=db,
        status=status,
        priority=priority,
        category=category,
        task_type=task_type,
        search=search,
        is_today=is_today,
        is_overdue=is_overdue,
        skip=skip,
        limit=limit,
        user_id=current_user.id,
    )

@router.get("/{task_id}", response_model=TaskResponse, response_model_by_alias=True)
def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Retrieve single task details by ID with ownership verification.
    """
    task = task_service.get_task_by_id(db, task_id, user_id=current_user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return task

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=True)
def create_task(
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Create a new task associated with the current user account.
    """
    return task_service.create_task(db, task_in, user_id=current_user.id)

@router.put("/{task_id}", response_model=TaskResponse, response_model_by_alias=True)
def update_task(
    task_id: str,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Update an existing task by ID with ownership verification.
    """
    updated = task_service.update_task(db, task_id, task_in, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return updated

@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Permanently delete or tombstone a task by ID with ownership verification.
    """
    success = task_service.delete_task(db, task_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return {"message": "Task deleted successfully", "id": task_id}

@router.patch("/{task_id}/complete", response_model=TaskResponse, response_model_by_alias=True)
def mark_task_complete(
    task_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Convenience endpoint: Mark a task as Completed with ownership verification.
    """
    task = task_service.set_task_status(db, task_id, "Completed", user_id=current_user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return task

@router.patch("/{task_id}/pending", response_model=TaskResponse, response_model_by_alias=True)
def mark_task_pending(
    task_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Convenience endpoint: Revert a task to Pending with ownership verification.
    """
    task = task_service.set_task_status(db, task_id, "Pending", user_id=current_user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found",
        )
    return task
