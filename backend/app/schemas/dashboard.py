from typing import Any, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from backend.app.schemas.task import TaskResponse

class DashboardMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_tasks: int = Field(..., serialization_alias="totalTasks")
    completed_tasks: int = Field(..., serialization_alias="completedTasks")
    pending_tasks: int = Field(..., serialization_alias="pendingTasks")
    active_goals: int = Field(..., serialization_alias="activeGoals")
    completion_rate: int = Field(..., serialization_alias="completionRate")
    overdue_count: int = Field(..., serialization_alias="overdueCount")
    due_today_count: int = Field(..., serialization_alias="dueTodayCount")

class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    metrics: DashboardMetrics
    tasks_due_today: List[TaskResponse] = Field(default_factory=list, serialization_alias="tasksDueToday")
    top_priorities: List[Dict[str, Any]] = Field(default_factory=list, serialization_alias="topPriorities")
    category_distribution: List[Dict[str, Any]] = Field(default_factory=list, serialization_alias="categoryDistribution")
