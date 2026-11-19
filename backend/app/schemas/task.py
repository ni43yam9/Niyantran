from datetime import date, datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, AliasChoices, ConfigDict, model_validator

TASK_TYPES = ("Daily", "Short-Term", "Long-Term", "One-Time", "Occasional")
TASK_CATEGORIES = ("Academic", "Coding", "Career", "Reading", "Health", "Personal")
TASK_PRIORITIES = ("High", "Medium", "Low")
TASK_STATUSES = ("Pending", "In Progress", "Completed")

TaskType = Literal["Daily", "Short-Term", "Long-Term", "One-Time", "Occasional"]
TaskCategory = Literal["Academic", "Coding", "Career", "Reading", "Health", "Personal"]
TaskPriority = Literal["High", "Medium", "Low"]
TaskStatus = Literal["Pending", "In Progress", "Completed"]

class TaskBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: str = Field(..., min_length=1, max_length=200, description="Title of the task")
    description: Optional[str] = Field(default="", max_length=2000, description="Detailed description")
    task_type: TaskType = Field(
        default="Daily",
        validation_alias=AliasChoices("task_type", "taskType"),
        description="Category of repetition or planning horizon",
    )
    category: TaskCategory = Field(default="Coding", description="Functional area")
    priority: TaskPriority = Field(default="Medium", description="Priority level")
    status: TaskStatus = Field(default="Pending", description="Completion status")
    start_date: date = Field(
        default_factory=date.today,
        validation_alias=AliasChoices("start_date", "startDate"),
        description="Task start date (YYYY-MM-DD)",
    )
    due_date: date = Field(
        default_factory=date.today,
        validation_alias=AliasChoices("due_date", "dueDate"),
        description="Task due date (YYYY-MM-DD)",
    )
    goal_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("goal_id", "goalId", "associated_goal_id", "associatedGoalId"),
        description="Foreign key to associated Goal id",
    )

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date cannot be earlier than start date")
        return self

class TaskCreate(TaskBase):
    id: Optional[str] = Field(
        default=None,
        description="Optional custom ID (e.g. from client or migration, 't-123')",
    )

class TaskUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    task_type: Optional[TaskType] = Field(
        default=None,
        validation_alias=AliasChoices("task_type", "taskType"),
    )
    category: Optional[TaskCategory] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    start_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("start_date", "startDate"),
    )
    due_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("due_date", "dueDate"),
    )
    goal_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("goal_id", "goalId", "associated_goal_id", "associatedGoalId"),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("completed_at", "completedAt"),
    )

class TaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    title: str
    description: Optional[str] = ""
    task_type: str = Field(..., serialization_alias="taskType")
    category: str
    priority: str
    status: str
    start_date: date = Field(..., serialization_alias="startDate")
    due_date: date = Field(..., serialization_alias="dueDate")
    goal_id: Optional[str] = Field(default=None, serialization_alias="goalId")
    associated_goal_id: Optional[str] = Field(default=None, serialization_alias="associatedGoalId")
    associated_goal_title: Optional[str] = Field(default=None, serialization_alias="associatedGoalTitle")
    completed_at: Optional[datetime] = Field(default=None, serialization_alias="completedAt")
    
    # Transient computed fields for rich UI support
    is_today: bool = Field(default=False, serialization_alias="isToday")
    is_overdue: bool = Field(default=False, serialization_alias="isOverdue")
    
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt")

    @classmethod
    def from_orm_model(cls, task, goal_title: Optional[str] = None):
        today = date.today()
        is_today = (task.due_date == today or task.start_date == today)
        is_overdue = (task.status != "Completed" and task.due_date < today)
        
        # Determine goal title from relationship if loaded
        title = goal_title
        if not title and hasattr(task, "goal") and task.goal:
            title = task.goal.title

        return cls(
            id=task.id,
            title=task.title,
            description=task.description or "",
            task_type=task.task_type,
            category=task.category,
            priority=task.priority,
            status=task.status,
            start_date=task.start_date,
            due_date=task.due_date,
            goal_id=task.goal_id,
            associated_goal_id=task.goal_id,
            associated_goal_title=title,
            completed_at=task.completed_at,
            is_today=is_today,
            is_overdue=is_overdue,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
