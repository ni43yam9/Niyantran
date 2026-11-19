from backend.app.routers.tasks import router as tasks_router
from backend.app.routers.goals import router as goals_router
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.migration import router as migration_router
from backend.app.routers.habits import router as habits_router
from backend.app.routers.timeblocks import router as timeblocks_router
from backend.app.routers.behaviour import router as behaviour_router
from backend.app.routers.analytics import router as analytics_router
from backend.app.routers.recommendations import router as recommendations_router

__all__ = [
    "tasks_router",
    "goals_router",
    "dashboard_router",
    "migration_router",
    "habits_router",
    "timeblocks_router",
    "behaviour_router",
    "analytics_router",
    "recommendations_router",
]
