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

# ===========================================================================
# Phase 8: Advanced Productivity Analytics & Insights Schemas
# ===========================================================================

class ScoreBreakdown(BaseModel):
    task_completion_points: float = Field(..., description="Max 25.0 points based on completed/created ratio")
    priority_weight_points: float = Field(..., description="Max 20.0 points based on priority weighted completions")
    deadline_adherence_points: float = Field(..., description="Max 20.0 points based on on-time delivery vs overdue debt")
    goal_progress_points: float = Field(..., description="Max 15.0 points based on active goal progress velocity")
    habit_consistency_points: float = Field(..., description="Max 15.0 points based on 14-day habit consistency")
    trend_modifier_points: float = Field(..., description="[-5.0 to +5.0] points based on recent velocity vs backlog growth")
    total_score: int = Field(..., description="Composite 0-100 explainable score")

class ProductivityScoreDetail(BaseModel):
    score: int
    level: str  # 'Exceptional', 'High', 'Balanced', 'Developing', 'Needs Focus', 'Baseline'
    breakdown: ScoreBreakdown
    methodology_explanation: str
    backlog_expansion_flag: bool
    has_sufficient_data: bool
    disclaimer: str
    evaluated_at: datetime

class TaskAnalyticsDetail(BaseModel):
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    postponed_tasks: int
    completion_rate: float
    priority_completion_rates: Dict[str, float]
    category_completion_rates: Dict[str, float]
    completions_by_day_of_week: Dict[str, int]
    average_lead_time_hours: Optional[float] = None
    has_sufficient_data: bool
    summary: str

class GoalAnalyticsDetail(BaseModel):
    total_goals: int
    completed_goals: int
    active_goals: int
    average_progress: float
    delayed_goals_count: int
    on_track_goals_count: int
    average_velocity_percent_per_day: float
    predictive_trajectories: List[Dict[str, Any]] = Field(default_factory=list)
    has_sufficient_data: bool
    summary: str

class HabitAnalyticsDetail(BaseModel):
    total_habits: int
    active_habits: int
    adherence_7d: float
    adherence_14d: float
    adherence_30d: float
    longest_streak: int
    active_streaks_count: int
    missed_days_last_4d: int
    habit_trend: str  # 'Improving', 'Steady', 'Declining', 'Insufficient Data'
    has_sufficient_data: bool
    summary: str

class PeriodComparison(BaseModel):
    period_label: str
    current_period_days_elapsed: int
    comparison_mode: str  # 'DAY_ALIGNED_SLICE', 'PRO_RATED_VELOCITY', 'FULL_PERIOD'
    current_completions: int
    previous_aligned_completions: int
    velocity_delta_percent: float
    trend: str  # 'Improving', 'Steady', 'Declining', 'Insufficient Data'
    explanation: str

class ProductivityTrendsDetail(BaseModel):
    daily_trend: PeriodComparison
    weekly_trend: PeriodComparison
    monthly_trend: PeriodComparison
    overall_momentum: str
    has_sufficient_data: bool

class TimeDistributionDetail(BaseModel):
    total_tracked_duration_minutes: int
    total_estimated_duration_minutes: int
    has_tracked_duration_data: bool
    estimation_bias_ratio: float
    is_bias_empirical: bool
    deep_work_focus_minutes: int
    category_durations: Dict[str, Dict[str, int]]
    working_hour_distribution: Dict[str, int]
    data_notes: str

class WeeklyProductivityReport(BaseModel):
    report_id: str
    week_start: date
    week_end: date
    productivity_score: int
    task_summary: Dict[str, Any]
    goal_summary: Dict[str, Any]
    habit_summary: Dict[str, Any]
    time_summary: Dict[str, Any]
    key_achievements: List[str]
    actionable_recommendations: List[str]
    generated_at: datetime

class MonthlyProductivityReport(BaseModel):
    report_id: str
    year: int
    month: int
    month_name: str
    productivity_score: int
    monthly_velocity_delta: float
    task_summary: Dict[str, Any]
    goal_summary: Dict[str, Any]
    habit_summary: Dict[str, Any]
    key_milestones: List[str]
    actionable_recommendations: List[str]
    generated_at: datetime
