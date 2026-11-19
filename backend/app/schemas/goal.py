from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, AliasChoices, ConfigDict, model_validator

GOAL_TYPES = ("Short-Term", "Long-Term")
GOAL_CATEGORIES = ("Academic", "Coding", "Career", "Reading", "Health", "Personal", "Technical")
GOAL_PRIORITIES = ("High", "Medium", "Low")
GOAL_STATUSES = ("In Progress", "On Track", "Behind", "Completed")

GoalType = Literal["Short-Term", "Long-Term"]
GoalCategory = Literal["Academic", "Coding", "Career", "Reading", "Health", "Personal", "Technical"]
GoalPriority = Literal["High", "Medium", "Low"]
GoalStatus = Literal["In Progress", "On Track", "Behind", "Completed"]

class GoalBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: str = Field(..., min_length=1, max_length=200, description="Title of the goal")
    description: Optional[str] = Field(default="", max_length=2000, description="Detailed description")
    goal_type: GoalType = Field(
        default="Short-Term",
        validation_alias=AliasChoices("goal_type", "goalType", "type"),
        description="Short-Term or Long-Term horizon",
    )
    category: str = Field(default="Coding", description="Functional category")
    priority: GoalPriority = Field(default="Medium", description="Priority level")
    status: GoalStatus = Field(default="In Progress", description="Goal progress status")
    start_date: date = Field(
        default_factory=date.today,
        validation_alias=AliasChoices("start_date", "startDate"),
        description="Start date (YYYY-MM-DD)",
    )
    target_date: date = Field(
        ...,
        validation_alias=AliasChoices("target_date", "targetDate"),
        description="Target completion date (YYYY-MM-DD)",
    )
    progress: int = Field(default=0, ge=0, le=100, description="Percentage completed (0-100)")
    key_milestone: Optional[str] = Field(
        default="",
        max_length=255,
        validation_alias=AliasChoices("key_milestone", "keyMilestone"),
        description="Notable current milestone target",
    )

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("Target date cannot be earlier than start date")
        return self

class GoalCreate(GoalBase):
    id: Optional[str] = Field(
        default=None,
        description="Optional custom ID (e.g. 'g-1' during migration)",
    )

class GoalUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    goal_type: Optional[GoalType] = Field(
        default=None,
        validation_alias=AliasChoices("goal_type", "goalType", "type"),
    )
    category: Optional[str] = None
    priority: Optional[GoalPriority] = None
    status: Optional[GoalStatus] = None
    start_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("start_date", "startDate"),
    )
    target_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("target_date", "targetDate"),
    )
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    key_milestone: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("key_milestone", "keyMilestone"),
    )

class GoalProgressUpdate(BaseModel):
    progress: int = Field(..., ge=0, le=100, description="New progress percentage (0-100)")
    status: Optional[GoalStatus] = Field(default=None, description="Optional updated status")

class GoalResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    title: str
    description: Optional[str] = ""
    goal_type: str = Field(..., serialization_alias="goalType")
    type: str = Field(..., serialization_alias="type")  # For legacy frontend compatibility
    category: str
    priority: str
    status: str
    start_date: date = Field(..., serialization_alias="startDate")
    target_date: date = Field(..., serialization_alias="targetDate")
    progress: int
    key_milestone: Optional[str] = Field(default="", serialization_alias="keyMilestone")

    # Transient computed fields
    total_tasks: int = Field(default=0, serialization_alias="totalTasks")
    completed_tasks: int = Field(default=0, serialization_alias="completedTasks")
    days_remaining: int = Field(default=0, serialization_alias="daysRemaining")

    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt")

    @classmethod
    def from_orm_model(cls, goal, total_tasks: int = 0, completed_tasks: int = 0):
        today = date.today()
        days_remaining = (goal.target_date - today).days

        # If goal has loaded tasks relationship and counts weren't explicitly passed
        if total_tasks == 0 and hasattr(goal, "tasks") and goal.tasks:
            total_tasks = len(goal.tasks)
            completed_tasks = sum(1 for t in goal.tasks if t.status == "Completed")

        return cls(
            id=goal.id,
            title=goal.title,
            description=goal.description or "",
            goal_type=goal.goal_type,
            type=goal.goal_type,
            category=goal.category,
            priority=goal.priority,
            status=goal.status,
            start_date=goal.start_date,
            target_date=goal.target_date,
            progress=goal.progress,
            key_milestone=goal.key_milestone or "",
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            days_remaining=days_remaining,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )
