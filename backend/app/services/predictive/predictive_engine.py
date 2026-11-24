import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.models.recommendation import Recommendation
from backend.app.services.predictive.data_preparation import prepare_predictive_dataset
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.ml_models import MachineLearningPredictor
from backend.app.services.predictive.predictors.deadline_predictor import predict_deadline_risks
from backend.app.services.predictive.predictors.goal_risk_predictor import predict_goal_risks
from backend.app.services.predictive.predictors.workload_forecaster import forecast_workload_distribution
from backend.app.services.predictive.predictors.habit_predictor import predict_habit_decay
from backend.app.services.predictive.predictors.completion_estimator import estimate_queue_completion_feasibility
from backend.app.services.predictive.predictors.productivity_predictor import predict_productivity_trend
from backend.app.services.predictive.prediction_evaluator import evaluate_matured_predictions

logger = logging.getLogger(__name__)

class PredictiveEngine:
    """
    Central orchestrator for Phase 4.5 Predictive Productivity Intelligence.
    Coordinates data preparation, feature extraction, 6 predictive modules,
    persistence, evaluation, and recommendation bridging.
    """
    def __init__(self):
        self.ml_predictor = MachineLearningPredictor()

    def generate_all_predictions(
        self,
        db: Session,
        reference_date: Optional[date] = None,
        persist: bool = True
    ) -> List[PredictiveInsight]:
        """
        Runs all 6 predictive analyzers and optionally persists results to SQLite.
        """
        today = reference_date or date.today()

        # Step 1: Prepare empirical dataset
        data = prepare_predictive_dataset(db, reference_date=today)

        # Step 2: Attempt conditional ML training if dataset meets N >= 15 criteria
        self.ml_predictor.train_deadline_model(data.completed_tasks)

        # Step 3: Feature extraction
        extractor = FeatureExtractor(data)

        # Step 4: Run all 6 predictors
        raw_insights: List[Dict[str, Any]] = []
        raw_insights.extend(predict_deadline_risks(data, extractor, self.ml_predictor))
        raw_insights.extend(predict_goal_risks(data, extractor))
        raw_insights.extend(forecast_workload_distribution(data, extractor))
        raw_insights.extend(predict_habit_decay(data, extractor))
        raw_insights.extend(estimate_queue_completion_feasibility(data, extractor))
        raw_insights.extend(predict_productivity_trend(data, extractor))

        if not persist:
            # Return transient model objects without saving
            return [PredictiveInsight(**item) for item in raw_insights]

        # Step 5: Upsert persistence with deduplication
        persisted_records: List[PredictiveInsight] = []
        now_utc = datetime.now(timezone.utc)

        for item in raw_insights:
            p_type = item["prediction_type"]
            e_id = item["entity_id"]

            # Query existing active prediction
            existing = (
                db.query(PredictiveInsight)
                .filter(
                    PredictiveInsight.prediction_type == p_type,
                    PredictiveInsight.entity_id == e_id,
                    PredictiveInsight.evaluation_status == "PENDING"
                )
                .first()
            )

            if existing:
                # Update existing pending prediction
                existing.risk_score = item["risk_score"]
                existing.risk_category = item["risk_category"]
                existing.confidence_score = item["confidence_score"]
                existing.has_sufficient_data = item["has_sufficient_data"]
                existing.title = item["title"]
                existing.summary = item["summary"]
                existing.supporting_evidence = item["supporting_evidence"]
                existing.contributing_factors = item["contributing_factors"]
                existing.suggested_action = item["suggested_action"]
                existing.time_horizon = item.get("time_horizon")
                existing.horizon_date = item.get("horizon_date")
                existing.predicted_outcome = item.get("predicted_outcome")
                existing.model_version = item.get("model_version", "statistical_v1")
                existing.updated_at = now_utc
                persisted_records.append(existing)
            else:
                new_insight = PredictiveInsight(**item)
                db.add(new_insight)
                persisted_records.append(new_insight)

        db.commit()

        for rec in persisted_records:
            db.refresh(rec)

        logger.info(f"Generated and persisted {len(persisted_records)} predictive insights.")
        return persisted_records

    def get_overview(
        self,
        db: Session,
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Retrieves active predictive insights structured by category with high-level summary metrics.
        """
        today = reference_date or date.today()

        # Fetch all pending insights
        insights = (
            db.query(PredictiveInsight)
            .filter(PredictiveInsight.evaluation_status == "PENDING")
            .all()
        )

        # If empty, automatically generate fresh predictions
        if not insights:
            insights = self.generate_all_predictions(db, reference_date=today, persist=True)

        data = prepare_predictive_dataset(db, reference_date=today)

        # Categorize
        deadlines = [i for i in insights if i.prediction_type == "DEADLINE_RISK"]
        goals = [i for i in insights if i.prediction_type == "GOAL_TRAJECTORY"]
        workload = [i for i in insights if i.prediction_type == "WORKLOAD_OVERLOAD"]
        habits = [i for i in insights if i.prediction_type == "HABIT_DECAY"]
        feasibility = [i for i in insights if i.prediction_type == "WORKLOAD_FEASIBILITY"]
        productivity = [i for i in insights if i.prediction_type == "PRODUCTIVITY_TREND"]

        critical_count = sum(1 for i in insights if i.risk_category == "CRITICAL")
        high_count = sum(1 for i in insights if i.risk_category == "HIGH")
        moderate_count = sum(1 for i in insights if i.risk_category == "MODERATE")
        low_count = sum(1 for i in insights if i.risk_category == "LOW")
        insufficient_data_count = sum(1 for i in insights if i.risk_category == "INSUFFICIENT_DATA")

        avg_conf = (
            sum(i.confidence_score for i in insights) / len(insights)
            if insights else 0.0
        )

        top_critical = sorted(
            [i for i in insights if i.risk_category in ("CRITICAL", "HIGH")],
            key=lambda x: (x.risk_score, x.confidence_score),
            reverse=True
        )[:5]

        summary = {
            "total_insights": len(insights),
            "critical_count": critical_count,
            "high_count": high_count,
            "moderate_count": moderate_count,
            "low_count": low_count,
            "insufficient_data_count": insufficient_data_count,
            "average_confidence": round(avg_conf, 2),
            "has_sufficient_history": data.has_sufficient_history,
            "historical_observation_count": data.total_observations,
            "top_critical_risks": top_critical,
        }

        return {
            "summary": summary,
            "deadlines": deadlines,
            "goals": goals,
            "workload": workload,
            "habits": habits,
            "feasibility": feasibility,
            "productivity": productivity,
        }

    def bridge_predictive_recommendations(
        self,
        db: Session,
        reference_date: Optional[date] = None,
        cooldown_hours: int = 48
    ) -> int:
        """
        Translates critical and high predictive risks into proactive recommendations
        in the existing recommendation system, honoring deduplication and cooldown rules.
        """
        import uuid
        today = reference_date or date.today()
        now_utc = datetime.now(timezone.utc)
        cutoff_time = now_utc - timedelta(hours=cooldown_hours)

        insights = (
            db.query(PredictiveInsight)
            .filter(
                PredictiveInsight.evaluation_status == "PENDING",
                PredictiveInsight.risk_category.in_(["CRITICAL", "HIGH"])
            )
            .all()
        )

        spawned_count = 0

        for insight in insights:
            # Map prediction_type to recommendation type and category
            if insight.prediction_type == "DEADLINE_RISK":
                rec_type = "DEADLINE_RISK"
                category = "Task"
                sub_key = "PREDICTIVE_DEADLINE"
                action_type = "EXPEDITE_TASK"
            elif insight.prediction_type == "GOAL_TRAJECTORY":
                rec_type = "GOAL_PROGRESS"
                category = "Goal"
                sub_key = "PREDICTIVE_GOAL"
                action_type = "FOCUS_GOAL"
            elif insight.prediction_type == "WORKLOAD_OVERLOAD":
                rec_type = "WORKLOAD_BALANCE"
                category = "Schedule"
                sub_key = "PREDICTIVE_WORKLOAD"
                action_type = "RESCHEDULE_TASK"
            elif insight.prediction_type == "HABIT_DECAY":
                rec_type = "HABIT_IMPROVEMENT"
                category = "Habit"
                sub_key = "PREDICTIVE_HABIT"
                action_type = "TRACK_HABIT"
            else:
                continue

            # Check if active recommendation or recent dismissal exists for this entity and sub_key
            existing = (
                db.query(Recommendation)
                .filter(
                    Recommendation.type == rec_type,
                    Recommendation.entity_id == insight.entity_id,
                )
                .all()
            )

            is_suppressed = False
            for r in existing:
                r_sub = (r.action_payload or {}).get("sub_key", "default")
                if r_sub == sub_key:
                    if r.status in ("PENDING", "ACCEPTED"):
                        is_suppressed = True
                        break
                    elif r.status == "DISMISSED":
                        r_up = r.updated_at
                        if r_up.tzinfo is None:
                            r_up = r_up.replace(tzinfo=timezone.utc)
                        if (now_utc - r_up) < timedelta(hours=cooldown_hours):
                            is_suppressed = True
                            break

            if is_suppressed:
                continue

            # Create proactive recommendation with Phase 5 explainability
            from backend.app.services.intelligence.priority_scorer import calculate_recommendation_priority
            from backend.app.services.intelligence.explainability import StructuredExplanation

            score_res = calculate_recommendation_priority(
                urgency_days=0 if insight.risk_category == "CRITICAL" else 2,
                importance_level="High" if insight.risk_category == "CRITICAL" else "Medium",
                goal_relevance_pts=15.0 if rec_type == "GOAL_PROGRESS" else 0.0,
                habit_impact_pts=15.0 if rec_type == "HABIT_IMPROVEMENT" else 0.0,
                postpone_count=1 if "postpone" in str(insight.supporting_evidence).lower() else 0,
            )

            expl = StructuredExplanation(
                what_happened=insight.title,
                why_generated=insight.summary,
                suggested_action=insight.suggested_action or "Review and adjust schedule.",
                why_prioritize=f"Predictive {insight.risk_category} risk score ({insight.risk_score}/100) with {int(insight.confidence_score * 100)}% confidence.",
            )

            rec = Recommendation(
                id=f"rec_{uuid.uuid4().hex[:12]}",
                type=rec_type,
                category=category,
                title=f"[Predictive] {insight.title}",
                description=insight.summary,
                reason=expl.to_reason_text(),
                priority=score_res.level,
                status="PENDING",
                action_type=action_type,
                action_payload={
                    "sub_key": sub_key,
                    "predictive_insight_id": insight.id,
                    "risk_score": insight.risk_score,
                    "confidence_score": insight.confidence_score,
                    "horizon_date": insight.horizon_date.isoformat() if insight.horizon_date else None,
                    "suggested_action": insight.suggested_action,
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                },
                entity_id=insight.entity_id,
                target_date=insight.horizon_date or today,
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(rec)
            spawned_count += 1

        if spawned_count > 0:
            db.commit()
            logger.info(f"Bridge created {spawned_count} proactive recommendations from predictive risks.")

        return spawned_count

    def predict_task_completions(
        self,
        db: Session,
        task_id: Optional[str] = None,
        reference_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculates on-time completion likelihood for active tasks using
        statistical estimation and conditional ML.
        """
        today = reference_date or date.today()
        data = prepare_predictive_dataset(db, reference_date=today)
        self.ml_predictor.train_deadline_model(data.completed_tasks)
        extractor = FeatureExtractor(data)

        from backend.app.services.predictive.predictors.completion_estimator import (
            predict_all_task_completions,
            predict_task_completion_likelihood,
        )

        if task_id:
            target_task = next((t for t in data.active_tasks if t.id == task_id), None)
            if not target_task:
                target_task = next((t for t in data.tasks if t.id == task_id), None)
            if target_task:
                return [predict_task_completion_likelihood(target_task, data, extractor, self.ml_predictor)]
            return []

        return predict_all_task_completions(data, extractor, self.ml_predictor)

# Global singleton
predictive_engine = PredictiveEngine()
