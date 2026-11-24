from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class PredictiveInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prediction_type: str
    entity_type: str
    entity_id: Optional[str] = None
    risk_score: float
    risk_category: str
    confidence_score: float
    has_sufficient_data: bool
    title: str
    summary: str
    supporting_evidence: Optional[List[str]] = None
    contributing_factors: Optional[List[str]] = None
    suggested_action: Optional[str] = None
    time_horizon: Optional[str] = None
    horizon_date: Optional[date] = None
    predicted_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    evaluation_status: str
    evaluation_notes: Optional[str] = None
    model_version: str
    created_at: datetime
    updated_at: datetime
    evaluated_at: Optional[datetime] = None

class TaskCompletionPredictionResponse(BaseModel):
    task_id: str
    title: str
    priority: str
    due_date: Optional[date] = None
    days_remaining: Optional[int] = None
    estimated_duration_minutes: int
    adjusted_duration_minutes: int
    completion_likelihood: float
    risk_level: str
    confidence_score: float
    has_sufficient_data: bool
    supporting_evidence: List[str] = []
    contributing_factors: List[str] = []
    explanation: str
    suggested_action: str
    predicted_outcome: str

class PredictiveRiskSummary(BaseModel):
    total_insights: int
    critical_count: int
    high_count: int
    moderate_count: int
    low_count: int
    insufficient_data_count: int
    average_confidence: float
    has_sufficient_history: bool
    historical_observation_count: int
    top_critical_risks: List[PredictiveInsightResponse] = []

class PredictiveOverviewResponse(BaseModel):
    summary: PredictiveRiskSummary
    deadlines: List[PredictiveInsightResponse] = []
    goals: List[PredictiveInsightResponse] = []
    workload: List[PredictiveInsightResponse] = []
    habits: List[PredictiveInsightResponse] = []
    feasibility: List[PredictiveInsightResponse] = []
    productivity: List[PredictiveInsightResponse] = []

class PredictionEvaluationResponse(BaseModel):
    total_tracked: int
    pending_count: int
    evaluated_count: int
    insufficient_data_count: int
    accuracy_rate: Optional[float] = None
    evaluated_insights: List[PredictiveInsightResponse] = []
    evaluation_timestamp: datetime

class PredictionRefreshResponse(BaseModel):
    status: str
    insights_generated: int
    critical_risks_identified: int
    recommendations_spawned: int
    insufficient_data_signals: int
    timestamp: datetime
