from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.timeblock import TimeblockCreate, TimeblockUpdate, TimeblockResponse
from backend.app.services import timeblock_service

router = APIRouter(prefix="/api/timeblocks", tags=["Timeblocks & Planning"])

@router.get("", response_model=List[TimeblockResponse], response_model_by_alias=True)
def list_timeblocks(
    block_date: Optional[date] = Query(None, alias="date", description="Filter by date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="Filter by status (Pending, In Progress, Completed)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    """
    Retrieve scheduled timeblocks for a specific date or across dates.
    """
    return timeblock_service.get_timeblocks(db, block_date=block_date, status=status, category=category)

@router.get("/analytics/planned-vs-actual", response_model=List[Dict[str, Any]])
def get_planned_vs_actual(
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    db: Session = Depends(get_db),
):
    """
    Retrieve Planned vs Actual focus hours grouped by category.
    Directly powers Recommendation 5: Planned vs Actual Productivity Insights.
    """
    return timeblock_service.get_planned_vs_actual_analytics(db, start_date=start_date, end_date=end_date)

@router.post("", response_model=TimeblockResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def create_timeblock(block_in: TimeblockCreate, db: Session = Depends(get_db)):
    """
    Create a new timeblock with planned duration and optional actual duration.
    """
    return timeblock_service.create_timeblock(db, block_in)

@router.get("/{block_id}", response_model=TimeblockResponse, response_model_by_alias=True)
def get_timeblock(block_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a single timeblock by ID.
    """
    block = timeblock_service.get_timeblock_by_id(db, block_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timeblock with ID '{block_id}' not found",
        )
    return block

@router.put("/{block_id}", response_model=TimeblockResponse, response_model_by_alias=True)
def update_timeblock(block_id: str, block_in: TimeblockUpdate, db: Session = Depends(get_db)):
    """
    Update a timeblock, including durationMinutes and actualDurationMinutes.
    """
    updated = timeblock_service.update_timeblock(db, block_id, block_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timeblock with ID '{block_id}' not found",
        )
    return updated

@router.delete("/{block_id}", status_code=status.HTTP_200_OK)
def delete_timeblock(block_id: str, db: Session = Depends(get_db)):
    """
    Delete a timeblock.
    """
    success = timeblock_service.delete_timeblock(db, block_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timeblock with ID '{block_id}' not found",
        )
    return {"message": f"Timeblock '{block_id}' deleted successfully"}
