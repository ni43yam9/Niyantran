from backend.app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from backend.app.schemas.goal import GoalCreate, GoalUpdate, GoalProgressUpdate, GoalResponse
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.schemas.migration import MigrationImportRequest, MigrationImportResponse
from backend.app.schemas.recommendation import (
    RecommendationBase,
    RecommendationCreate,
    RecommendationUpdate,
    RecommendationResponse,
    RecommendationSummary,
)

__all__ = [
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "GoalCreate",
    "GoalUpdate",
    "GoalProgressUpdate",
    "GoalResponse",
    "DashboardSummaryResponse",
    "MigrationImportRequest",
    "MigrationImportResponse",
    "RecommendationBase",
    "RecommendationCreate",
    "RecommendationUpdate",
    "RecommendationResponse",
    "RecommendationSummary",
]
