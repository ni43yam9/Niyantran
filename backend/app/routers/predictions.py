import logging
from datetime import datetime, timezone, date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.schemas.predictive import (
    PredictiveInsightResponse,
    PredictiveOverviewResponse,
    PredictionEvaluationResponse,
    PredictionRefreshResponse,
    TaskCompletionPredictionResponse,
)
from backend.app.services.predictive.predictive_engine import predictive_engine
from backend.app.services.predictive.prediction_evaluator import evaluate_matured_predictions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["Predictions"])

@router.get("/overview", response_model=PredictiveOverviewResponse)
def get_prediction_overview(
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Returns an aggregated overview of all predictive risk intelligence,
    categorized by domain with summary counts and confidence metrics.
    """
    return predictive_engine.get_overview(db, reference_date=reference_date)

@router.get("/deadlines", response_model=List[PredictiveInsightResponse])
def get_deadline_predictions(db: Session = Depends(get_db)):
    """
    Returns pending task deadline breach risk predictions.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "DEADLINE_RISK",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .order_by(PredictiveInsight.risk_score.desc())
        .all()
    )

@router.get("/tasks", response_model=List[TaskCompletionPredictionResponse])
def get_task_completion_predictions(
    task_id: Optional[str] = None,
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Returns on-time completion likelihood predictions for active tasks.
    """
    return predictive_engine.predict_task_completions(db, task_id=task_id, reference_date=reference_date)

@router.get("/tasks/{task_id}", response_model=TaskCompletionPredictionResponse)
def get_single_task_completion_prediction(
    task_id: str,
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Returns on-time completion likelihood prediction for a single task.
    """
    preds = predictive_engine.predict_task_completions(db, task_id=task_id, reference_date=reference_date)
    if not preds:
        raise HTTPException(status_code=404, detail="Task not found or not active")
    return preds[0]

@router.get("/goals", response_model=List[PredictiveInsightResponse])
def get_goal_predictions(db: Session = Depends(get_db)):
    """
    Returns active goal trajectory and velocity deficit predictions.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "GOAL_TRAJECTORY",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .order_by(PredictiveInsight.risk_score.desc())
        .all()
    )

@router.get("/workload", response_model=List[PredictiveInsightResponse])
def get_workload_predictions(db: Session = Depends(get_db)):
    """
    Returns forward 7-day workload bottleneck predictions.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "WORKLOAD_OVERLOAD",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .order_by(PredictiveInsight.horizon_date.asc())
        .all()
    )

@router.get("/habits", response_model=List[PredictiveInsightResponse])
def get_habit_predictions(db: Session = Depends(get_db)):
    """
    Returns habit decay and streak vulnerability predictions.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "HABIT_DECAY",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .order_by(PredictiveInsight.risk_score.desc())
        .all()
    )

@router.get("/feasibility", response_model=List[PredictiveInsightResponse])
def get_backlog_feasibility_predictions(db: Session = Depends(get_db)):
    """
    Returns deliverable backlog volume and capacity feasibility predictions.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "WORKLOAD_FEASIBILITY",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .all()
    )

@router.get("/productivity", response_model=List[PredictiveInsightResponse])
def get_productivity_trend_predictions(db: Session = Depends(get_db)):
    """
    Returns forward weekly productivity trajectory forecasts.
    """
    return (
        db.query(PredictiveInsight)
        .filter(
            PredictiveInsight.prediction_type == "PRODUCTIVITY_TREND",
            PredictiveInsight.evaluation_status == "PENDING"
        )
        .all()
    )

@router.post("/refresh", response_model=PredictionRefreshResponse)
def refresh_predictions(
    bridge_recommendations: bool = Query(True, description="Spawn proactive recommendations for critical risks"),
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Executes full predictive engine cycle, refreshing all 6 predictors
    and updating persistent records with empirical data.
    """
    insights = predictive_engine.generate_all_predictions(db, reference_date=reference_date, persist=True)
    critical_count = sum(1 for i in insights if i.risk_category in ("CRITICAL", "HIGH"))
    insufficient_count = sum(1 for i in insights if not i.has_sufficient_data)

    spawned = 0
    if bridge_recommendations:
        spawned = predictive_engine.bridge_predictive_recommendations(db, reference_date=reference_date)

    return PredictionRefreshResponse(
        status="SUCCESS",
        insights_generated=len(insights),
        critical_risks_identified=critical_count,
        recommendations_spawned=spawned,
        insufficient_data_signals=insufficient_count,
        timestamp=datetime.now(timezone.utc)
    )

@router.post("/evaluate", response_model=PredictionEvaluationResponse)
def evaluate_predictions(
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Evaluates matured predictions whose horizon dates have passed against
    actual database outcomes.
    Immature predictions remain in PENDING status.
    """
    eval_result = evaluate_matured_predictions(db, reference_date=reference_date)

    evaluated_insights = (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.evaluation_status == "EVALUATED")
        .order_by(PredictiveInsight.evaluated_at.desc())
        .limit(50)
        .all()
    )

    return PredictionEvaluationResponse(
        total_tracked=eval_result["total_tracked"],
        pending_count=eval_result["pending_count"],
        evaluated_count=eval_result["evaluated_count"],
        insufficient_data_count=eval_result["insufficient_data_count"],
        accuracy_rate=eval_result["accuracy_rate"],
        evaluated_insights=evaluated_insights,
        evaluation_timestamp=eval_result["evaluation_timestamp"]
    )

@router.get("/evaluations", response_model=List[PredictiveInsightResponse])
def get_prediction_evaluations(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Returns list of evaluated historical predictions and their actual outcomes.
    """
    return (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.evaluation_status == "EVALUATED")
        .order_by(PredictiveInsight.evaluated_at.desc())
        .limit(limit)
        .all()
    )
