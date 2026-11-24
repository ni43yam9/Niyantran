from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class DailyIntentBase(BaseModel):
    intent_date: date = Field(..., description="Date for this daily intent directive")
    intent_text: str = Field(..., min_length=1, max_length=2000, description="The primary focus intent directive for the day")

class DailyIntentCreate(DailyIntentBase):
    user_id: Optional[str] = Field("default_user", description="Owner user ID")

class DailyIntentUpdate(BaseModel):
    intent_text: str = Field(..., min_length=1, max_length=2000, description="Updated intent directive")

class DailyIntentResponse(BaseModel):
    id: str
    user_id: str
    intent_date: date
    intent_text: str
    version: int
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
