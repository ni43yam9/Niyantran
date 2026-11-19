from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ActivityLogBase(BaseModel):
    event_type: str = Field(..., description="Type of event: TASK_CREATED, TASK_COMPLETED, TASK_POSTPONED, etc.")
    entity_type: str = Field(..., description="Target entity type: task, habit, timeblock, plan")
    entity_id: Optional[str] = Field(None, description="Optional ID of associated entity")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of event, defaults to now UTC")
    original_date: Optional[date] = Field(None, description="Original scheduled date if rescheduled")
    new_date: Optional[date] = Field(None, description="New scheduled date if rescheduled")
    duration_minutes: Optional[int] = Field(None, description="Estimated duration in minutes")
    actual_duration_minutes: Optional[int] = Field(None, description="Actual duration in minutes")
    details: Optional[Dict[str, Any]] = Field(None, description="Arbitrary event metadata")

    model_config = ConfigDict(populate_by_name=True)

class ActivityLogCreate(ActivityLogBase):
    pass

class ActivityLogResponse(ActivityLogBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# ----------------- Analysis Models ----------------- #

class TaskCompletionAnalysis(BaseModel):
    total_created: int = 0
    total_completed: int = 0
    total_pending: int = 0
    completion_rate: float = 0.0
    daily_completion_percentage: float = 0.0
    weekly_completion_percentage: float = 0.0
    average_completion_time_hours: Optional[float] = None
    completions_by_day_of_week: Dict[str, int] = Field(default_factory=dict)
    most_productive_day: Optional[str] = None
    has_sufficient_data: bool = False
    message: Optional[str] = None

class RepeatedlyPostponedTask(BaseModel):
    task_id: str
    title: str
    category: str
    postpone_count: int
    original_date: Optional[date] = None
    current_date: Optional[date] = None
    status: str

class PostponementAnalysis(BaseModel):
    total_postponements: int = 0
    postponed_task_count: int = 0
    repeatedly_postponed_tasks: List[RepeatedlyPostponedTask] = Field(default_factory=list)
    completed_after_deadline_count: int = 0
    overdue_completion_rate: float = 0.0
    procrastination_level: str = "Insufficient Data"  # 'Low', 'Moderate', 'High', 'Insufficient Data'
    has_sufficient_data: bool = False
    message: Optional[str] = None

class CategoryEstimationAccuracy(BaseModel):
    category: str
    planned_minutes: int
    actual_minutes: int
    variance_minutes: int
    count: int
    is_underestimated: bool

class TimeEstimationAnalysis(BaseModel):
    total_tracked_tasks: int = 0
    total_planned_minutes: int = 0
    total_actual_minutes: int = 0
    average_error_minutes: float = 0.0
    underestimated_count: int = 0
    overestimated_count: int = 0
    accurate_count: int = 0
    underestimation_percentage: float = 0.0
    estimation_bias: str = "Insufficient Data"  # 'Underestimation', 'Overestimation', 'Balanced', 'Insufficient Data'
    category_breakdown: List[CategoryEstimationAccuracy] = Field(default_factory=list)
    has_sufficient_data: bool = False
    message: Optional[str] = None

class ProductivityHoursAnalysis(BaseModel):
    total_recorded_completions: int = 0
    morning_completions: int = 0      # 05:00 - 12:00
    afternoon_completions: int = 0    # 12:00 - 17:00
    evening_completions: int = 0      # 17:00 - 22:00
    night_completions: int = 0        # 22:00 - 05:00
    peak_period: str = "Insufficient Data"  # 'Morning', 'Afternoon', 'Evening', 'Night', 'Insufficient Data'
    peak_window: Optional[str] = None       # e.g. "09:00 AM - 12:00 PM"
    hourly_distribution: Dict[int, int] = Field(default_factory=dict)
    has_sufficient_data: bool = False
    message: Optional[str] = None

class HabitSummary(BaseModel):
    habit_id: str
    name: str
    category: str
    current_streak: int
    longest_streak: int
    completion_rate_30d: float

class HabitConsistencyAnalysis(BaseModel):
    total_active_habits: int = 0
    overall_consistency_percentage: float = 0.0
    average_current_streak: float = 0.0
    longest_streak_recorded: int = 0
    missed_days_last_30_days: int = 0
    most_consistent_habit: Optional[str] = None
    habit_summaries: List[HabitSummary] = Field(default_factory=list)
    has_sufficient_data: bool = False
    message: Optional[str] = None

class DailyPlanningAnalysis(BaseModel):
    total_planned_blocks: int = 0
    completed_planned_blocks: int = 0
    planning_accuracy_rate: float = 0.0
    average_daily_planned_hours: float = 0.0
    frequently_shifted_count: int = 0
    unfinished_planned_tasks: int = 0
    capacity_discipline: str = "Insufficient Data"  # 'Healthy (< 6.0 hrs)', 'Overbooked (> 6.0 hrs)', 'Insufficient Data'
    has_sufficient_data: bool = False
    message: Optional[str] = None

class BehaviourSummaryResponse(BaseModel):
    task_completion: TaskCompletionAnalysis
    procrastination: PostponementAnalysis
    time_estimation: TimeEstimationAnalysis
    productivity_hours: ProductivityHoursAnalysis
    habit_consistency: HabitConsistencyAnalysis
    daily_planning: DailyPlanningAnalysis
    overall_assessment: str
    evaluated_at: datetime
