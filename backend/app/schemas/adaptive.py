from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class WorkingPeriodsPattern(BaseModel):
    peak_time_window: str = Field(..., description="Morning, Afternoon, Evening, Night, or INSUFFICIENT_DATA")
    peak_days: List[str] = Field(default_factory=list)
    time_window_distribution: Dict[str, int] = Field(default_factory=dict)
    day_of_week_distribution: Dict[str, int] = Field(default_factory=dict)
    preferred_session_duration_minutes: int = 60
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class TaskTendenciesPattern(BaseModel):
    total_created: int = 0
    total_completed: int = 0
    completion_rate: float = 0.0
    avg_daily_completed_tasks: float = 0.0
    most_completed_category: Optional[str] = None
    category_completion_rates: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class PostponementPattern(BaseModel):
    total_postponements: int = 0
    postponed_task_count: int = 0
    postponement_rate: float = 0.0
    most_postponed_category: Optional[str] = None
    repeatedly_postponed_count: int = 0
    procrastination_level: str = "Insufficient Data"
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class EstimationBiasPattern(BaseModel):
    duration_bias_factor: float = 1.25
    is_empirical: bool = False
    variance: float = 0.0
    category_biases: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class HabitConsistencyPattern(BaseModel):
    average_adherence_rate: float = 0.0
    active_streaks_count: int = 0
    strongest_habit: Optional[str] = None
    habit_stability: str = "Insufficient Data"
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class GoalProgressPattern(BaseModel):
    active_goals_count: int = 0
    avg_velocity_percent_per_day: float = 0.0
    stalled_goals_count: int = 0
    on_track_goals_count: int = 0
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class RecommendationReceptivityPattern(BaseModel):
    total_interactions: int = 0
    acceptance_rate: float = 0.0
    dismissal_rate: float = 0.0
    execution_rate: float = 0.0
    ignored_count: int = 0
    receptivity_by_type: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    adaptive_type_weights: Dict[str, float] = Field(default_factory=dict)
    most_favored_type: Optional[str] = None
    most_dismissed_type: Optional[str] = None
    confidence: float = 0.0
    sample_size: int = 0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class WorkloadTolerancePattern(BaseModel):
    optimal_daily_load_minutes: int = 300
    max_observed_sustainable_minutes: int = 360
    heavy_day_completion_rate: float = 0.0
    confidence: float = 0.0
    has_sufficient_data: bool = False
    evidence: List[str] = Field(default_factory=list)

class LearnedPatternsResponse(BaseModel):
    user_id: str
    evaluation_date: date
    working_periods: WorkingPeriodsPattern
    task_tendencies: TaskTendenciesPattern
    postponements: PostponementPattern
    estimation_bias: EstimationBiasPattern
    habits: HabitConsistencyPattern
    goals: GoalProgressPattern
    recommendations: RecommendationReceptivityPattern
    workload_tolerance: WorkloadTolerancePattern
    overall_confidence: float
    has_sufficient_history: bool

class CalibrationBin(BaseModel):
    bin_range: str
    prediction_count: int
    mean_predicted_probability: float
    observed_frequency: float
    calibration_gap: float

class PredictionCalibrationResponse(BaseModel):
    total_evaluated: int
    brier_score: Optional[float] = None
    calibration_bias: Optional[float] = None
    calibration_status: str  # OVERCONFIDENT, UNDERCONFIDENT, WELL_CALIBRATED, INSUFFICIENT_DATA
    advisory_calibration_factor: float
    deadline_risk_accuracy: Optional[float] = None
    goal_trajectory_accuracy: Optional[float] = None
    habit_decay_accuracy: Optional[float] = None
    reliability_bins: List[CalibrationBin] = Field(default_factory=list)
    findings_and_warnings: List[str] = Field(default_factory=list)
    has_sufficient_evaluations: bool
    evaluated_at: datetime

class SchedulingSuggestion(BaseModel):
    id: str
    suggestion_type: str  # ENERGY_WINDOW_ALIGNMENT, LOW_ENERGY_MICRO_TASK, WORKLOAD_REDISTRIBUTION, DAY_OVERLOAD_PREVENTION
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    current_date: Optional[date] = None
    suggested_date: Optional[date] = None
    suggested_window: str
    confidence_score: float
    reason: str
    evidence: List[str] = Field(default_factory=list)
    requires_user_approval: bool = True

class AdaptiveSchedulingResponse(BaseModel):
    peak_time_window: str
    optimal_daily_load_minutes: int
    suggestions: List[SchedulingSuggestion] = Field(default_factory=list)
    total_suggestions: int = 0
    summary: str

class ProductivityProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    profile_date: date
    peak_time_window: Optional[str] = None
    peak_days: Optional[List[str]] = None
    preferred_session_duration_minutes: int
    optimal_daily_load_minutes: int
    max_observed_sustainable_minutes: int
    duration_bias_factor: float
    is_bias_empirical: bool
    task_completion_rate: float
    postponement_rate: float
    procrastination_level: str
    habit_stability: str
    recommendation_weights: Optional[Dict[str, float]] = None
    calibration_metrics: Optional[Dict[str, Any]] = None
    profile_data: Optional[Dict[str, Any]] = None
    confidence_score: float
    has_sufficient_history: bool
    created_at: datetime
    updated_at: datetime

class ProfileRefreshResponse(BaseModel):
    status: str
    profile_id: str
    user_id: str
    patterns_identified: int
    overall_confidence: float
    has_sufficient_history: bool
    refreshed_at: datetime
