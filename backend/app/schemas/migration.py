from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

class MigrationImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Array of task objects from localStorage")
    goals: List[Dict[str, Any]] = Field(default_factory=list, description="Array of goal objects from localStorage")
    habits: List[Dict[str, Any]] = Field(default_factory=list, description="Array of habit objects from localStorage")
    timeblocks: Any = Field(default_factory=dict, description="Array or date-mapped dict of timeblock objects from localStorage")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing records with same ID")

class MigrationImportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(..., description="'success', 'partial', or 'error'")
    tasks_imported: int = Field(default=0, serialization_alias="tasksImported")
    tasks_updated: int = Field(default=0, serialization_alias="tasksUpdated")
    tasks_skipped: int = Field(default=0, serialization_alias="tasksSkipped")
    goals_imported: int = Field(default=0, serialization_alias="goalsImported")
    goals_updated: int = Field(default=0, serialization_alias="goalsUpdated")
    goals_skipped: int = Field(default=0, serialization_alias="goalsSkipped")
    habits_imported: int = Field(default=0, serialization_alias="habitsImported")
    habits_updated: int = Field(default=0, serialization_alias="habitsUpdated")
    habits_skipped: int = Field(default=0, serialization_alias="habitsSkipped")
    habit_logs_imported: int = Field(default=0, serialization_alias="habitLogsImported")
    timeblocks_imported: int = Field(default=0, serialization_alias="timeblocksImported")
    timeblocks_updated: int = Field(default=0, serialization_alias="timeblocksUpdated")
    timeblocks_skipped: int = Field(default=0, serialization_alias="timeblocksSkipped")
    message: str = ""
    errors: List[str] = Field(default_factory=list)

class MigrationStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_tasks_in_db: int = Field(..., serialization_alias="totalTasksInDb")
    total_goals_in_db: int = Field(..., serialization_alias="totalGoalsInDb")
    total_habits_in_db: int = Field(default=0, serialization_alias="totalHabitsInDb")
    total_habit_logs_in_db: int = Field(default=0, serialization_alias="totalHabitLogsInDb")
    total_timeblocks_in_db: int = Field(default=0, serialization_alias="totalTimeblocksInDb")
    last_task_created: Any = Field(default=None, serialization_alias="lastTaskCreated")
    last_goal_created: Any = Field(default=None, serialization_alias="lastGoalCreated")
