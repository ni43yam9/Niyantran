from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict

class HabitLogBase(BaseModel):
    log_date: date = Field(..., alias="date", description="Log date YYYY-MM-DD")
    completed: bool = Field(True, description="Whether habit was completed on this date")
    notes: Optional[str] = Field(None, description="Optional reflection note")

    model_config = ConfigDict(populate_by_name=True)

class HabitLogCreate(HabitLogBase):
    pass

class HabitLogResponse(BaseModel):
    id: str
    habit_id: str = Field(..., alias="habitId")
    log_date: date = Field(..., alias="date")
    completed: bool
    notes: Optional[str] = None
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class HabitBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    target: Optional[str] = Field(None, max_length=100)
    category: str = Field("General", max_length=50)
    frequency: str = Field("Daily", max_length=50)
    base_streak: int = Field(0, ge=0, alias="baseStreak")

    model_config = ConfigDict(populate_by_name=True)

class HabitCreate(HabitBase):
    id: Optional[str] = Field(None, description="Optional custom ID (e.g. h-1)")
    completed_dates: Optional[Dict[str, bool]] = Field(default_factory=dict, alias="completedDates")

class HabitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    target: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    frequency: Optional[str] = Field(None, max_length=50)
    base_streak: Optional[int] = Field(None, ge=0, alias="baseStreak")
    archived: Optional[bool] = None

    model_config = ConfigDict(populate_by_name=True)

class HabitResponse(BaseModel):
    id: str
    name: str
    target: Optional[str] = None
    category: str
    frequency: str
    base_streak: int = Field(..., alias="baseStreak")
    archived: bool
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    completed_dates: Dict[str, bool] = Field(default_factory=dict, alias="completedDates")
    logs: List[HabitLogResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
