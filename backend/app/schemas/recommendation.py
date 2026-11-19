from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class RecommendationBase(BaseModel):
    type: str = Field(..., description="PRIORITIZATION, DEADLINE_RISK, WORKLOAD_BALANCE, GOAL_PROGRESS, HABIT_IMPROVEMENT")
    category: str = Field(..., description="Task, Goal, Habit, Schedule")
    title: str = Field(..., max_length=200)
    description: str
    reason: str = Field(..., description="Deterministic, plain-English justification for why this recommendation was triggered")
    priority: str = Field("MEDIUM", description="HIGH, MEDIUM, LOW")
    status: str = Field("PENDING", description="PENDING, ACCEPTED, DISMISSED, COMPLETED")
    action_type: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None
    entity_id: Optional[str] = None
    target_date: Optional[date] = None

class RecommendationCreate(RecommendationBase):
    pass

class RecommendationUpdate(BaseModel):
    status: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None

class RecommendationResponse(RecommendationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RecommendationSummary(BaseModel):
    total_active: int
    high_priority_count: int
    by_type: Dict[str, int]
    items: List[RecommendationResponse]
