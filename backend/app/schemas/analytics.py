from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AnalyticsOverview(BaseModel):
    productivity_score: int = Field(..., description="Overall productivity score 0-100")
    daily_completion_rate: float
    weekly_completion_rate: float
    monthly_completion_rate: float
    total_completed_tasks: int
    total_postponed_tasks: int
    total_pending_tasks: int
    habit_consistency_rate: float
    active_goals_count: int
    evaluated_at: datetime

class DailyAnalytics(BaseModel):
    target_date: date
    tasks_planned: int
    tasks_completed: int
    tasks_postponed: int
    completion_percentage: float
    focus_minutes_planned: int
    focus_minutes_actual: int
    hourly_completions: Dict[int, int]
    has_sufficient_data: bool
    summary: str

class DayWeeklyData(BaseModel):
    date: date
    day_name: str
    planned: int
    completed: int
    postponed: int
    completion_rate: float

class WeeklyAnalytics(BaseModel):
    week_start: date
    week_end: date
    daily_breakdown: List[DayWeeklyData]
    total_planned: int
    total_completed: int
    total_postponed: int
    weekly_completion_rate: float
    productivity_trend: str  # 'Improving', 'Steady', 'Declining', 'Insufficient Data'
    most_productive_day: Optional[str]

class MonthlyAnalytics(BaseModel):
    year: int
    month: int
    month_name: str
    tasks_completed: int
    tasks_completed_prev_month: int
    percentage_change: float
    goals_completed: int
    goals_in_progress: int
    average_goal_progress: float
    monthly_habit_consistency: float
    trend: str  # 'Improving', 'Steady', 'Declining', 'Insufficient Data'

class TimeAnalytics(BaseModel):
    most_productive_window: str
    least_productive_window: str
    average_task_completion_hours: Optional[float]
    total_estimated_minutes: int
    total_actual_minutes: int
    estimation_variance_minutes: int
    underestimation_rate: float
    quadrant_distribution: Dict[str, int]  # 'Morning', 'Afternoon', 'Evening', 'Night'
    quadrant_percentages: Dict[str, float]
    has_sufficient_data: bool

class GoalAnalyticsItem(BaseModel):
    goal_id: str
    title: str
    category: str
    timeframe: str
    priority: str
    status: str
    progress: int
    total_tasks: int
    completed_tasks: int
    task_completion_rate: float

class GoalAnalytics(BaseModel):
    total_goals: int
    completed_goals: int
    active_goals: int
    average_progress: float
    short_term_count: int
    long_term_count: int
    goals: List[GoalAnalyticsItem]
    completion_trend: str

class ProductivityInsight(BaseModel):
    id: str
    type: str  # 'positive', 'warning', 'neutral', 'tip'
    category: str  # 'Timing', 'Estimation', 'Habit', 'Planning', 'Postponement'
    title: str
    description: str
    impact: str  # 'High', 'Medium', 'Low'

class InsightsResponse(BaseModel):
    insights: List[ProductivityInsight]
    total_insights: int
    has_sufficient_data: bool
    data_sufficiency_message: Optional[str] = None
