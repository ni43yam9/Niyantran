from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class TimeblockBase(BaseModel):
    block_date: date = Field(..., alias="date", description="Date of the timeblock YYYY-MM-DD")
    title: str = Field(..., min_length=1, max_length=200)
    time: str = Field(..., description="Start time e.g. 09:00 AM")
    duration_minutes: int = Field(60, ge=5, le=720, alias="durationMinutes", description="Planned duration in minutes")
    actual_duration_minutes: Optional[int] = Field(None, ge=0, le=720, alias="actualDurationMinutes", description="Actual time spent (Planned vs Actual)")
    category: str = Field("General", max_length=50)
    status: str = Field("Pending", description="Status: Pending, In Progress, Completed")
    is_break: bool = Field(False, alias="isBreak")
    task_id: Optional[str] = Field(None, alias="taskId", description="Optional linked Task ID")

    model_config = ConfigDict(populate_by_name=True)

class TimeblockCreate(TimeblockBase):
    id: Optional[str] = Field(None, description="Optional custom ID e.g. blk_1")

class TimeblockUpdate(BaseModel):
    block_date: Optional[date] = Field(None, alias="date")
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    time: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=5, le=720, alias="durationMinutes")
    actual_duration_minutes: Optional[int] = Field(None, ge=0, le=720, alias="actualDurationMinutes")
    category: Optional[str] = None
    status: Optional[str] = None
    is_break: Optional[bool] = Field(None, alias="isBreak")
    task_id: Optional[str] = Field(None, alias="taskId")

    model_config = ConfigDict(populate_by_name=True)

class TimeblockResponse(BaseModel):
    id: str
    block_date: date = Field(..., alias="date")
    title: str
    time: str
    duration_minutes: int = Field(..., alias="durationMinutes")
    actual_duration_minutes: Optional[int] = Field(None, alias="actualDurationMinutes")
    category: str
    status: str
    is_break: bool = Field(..., alias="isBreak")
    task_id: Optional[str] = Field(None, alias="taskId")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
