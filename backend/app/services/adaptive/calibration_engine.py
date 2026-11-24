import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.schemas.adaptive import CalibrationBin, PredictionCalibrationResponse
from backend.app.services.adaptive.confidence_manager import (
    MIN_EVALUATIONS_CALIBRATION,
    MIN_EVALUATIONS_VALIDATED,
    calculate_sample_confidence,
)
from backend.app.services.predictive.prediction_evaluator import evaluate_matured_predictions

logger = logging.getLogger(__name__)

BIN_RANGES = [
    (0.0, 0.20, "0.0 - 0.20"),
    (0.20, 0.40, "0.20 - 0.40"),
    (0.40, 0.60, "0.40 - 0.60"),
    (0.60, 0.80, "0.60 - 0.80"),
    (0.80, 1.01, "0.80 - 1.00"),
]

def calibrate_predictions(
    db: Session,
    reference_date: Optional[date] = None,
    now_utc: Optional[datetime] = None,
) -> PredictionCalibrationResponse:
    """
    Evaluates Phase 6 predictions against empirical outcomes, computes Brier scores,
    reliability bins, detects systematic overconfidence or underconfidence,
    and calculates an advisory calibration adjustment factor.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = reference_date or now.date() if isinstance(now, datetime) else date.today()

    # 1. First trigger evaluation of any matured predictions
    evaluate_matured_predictions(db, reference_date=today)

    # 2. Query all evaluated predictive insights
    evaluated_insights = (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.evaluation_status == "EVALUATED")
        .all()
    )

    total_evaluated = len(evaluated_insights)
    findings: List[str] = []

    if total_evaluated < MIN_EVALUATIONS_CALIBRATION:
        findings.append(
            f"Insufficient matured predictions ({total_evaluated}/{MIN_EVALUATIONS_CALIBRATION}). Calibration metrics pending maturation."
        )
        return PredictionCalibrationResponse(
            total_evaluated=total_evaluated,
            brier_score=None,
            calibration_bias=None,
            calibration_status="INSUFFICIENT_DATA",
            advisory_calibration_factor=1.0,
            deadline_risk_accuracy=None,
            goal_trajectory_accuracy=None,
            habit_decay_accuracy=None,
            reliability_bins=[],
            findings_and_warnings=findings,
            has_sufficient_evaluations=False,
            evaluated_at=now,
        )

    # 3. Analyze Task Likelihood & Deadline Probabilities
    # Probabilities and binary actual outcomes
    pairs: List[Tuple[float, int]] = []
    deadline_correct = 0
    deadline_total = 0
    goal_correct = 0
    goal_total = 0
    habit_correct = 0
    habit_total = 0

    for ins in evaluated_insights:
        ptype = ins.prediction_type
        # Extract implied or explicit probability
        pred_prob = ins.confidence_score
        # Check risk score inversion (if risk is high, completion prob is low)
        if ins.risk_score is not None and ins.risk_score > 0:
            pred_prob = round(1.0 - (ins.risk_score / 100.0), 2)
            pred_prob = max(0.02, min(0.98, pred_prob))

        actual_binary = 1 if ins.actual_outcome in ("ON_TIME", "ON_TRACK", "STABLE") else 0
        pairs.append((pred_prob, actual_binary))

        if ptype == "DEADLINE_RISK":
            deadline_total += 1
            if ins.predicted_outcome == ins.actual_outcome:
                deadline_correct += 1
        elif ptype == "GOAL_TRAJECTORY":
            goal_total += 1
            if ins.predicted_outcome == ins.actual_outcome:
                goal_correct += 1
        elif ptype == "HABIT_DECAY":
            habit_total += 1
            if ins.predicted_outcome == ins.actual_outcome:
                habit_correct += 1

    # Compute Brier Score
    n = len(pairs)
    brier_score = round(sum((p - y) ** 2 for p, y in pairs) / n, 4)

    # Compute Calibration Bias = mean(p) - mean(y)
    mean_pred = sum(p for p, _ in pairs) / n
    mean_actual = sum(y for _, y in pairs) / n
    calibration_bias = round(mean_pred - mean_actual, 3)

    # Status classification
    if calibration_bias > 0.10:
        calibration_status = "OVERCONFIDENT"
        findings.append(
            f"Overconfidence detected: Model predicted {round(mean_pred*100, 1)}% success likelihood, but actual completion was {round(mean_actual*100, 1)}%."
        )
    elif calibration_bias < -0.10:
        calibration_status = "UNDERCONFIDENT"
        findings.append(
            f"Underconfidence detected: Model predicted {round(mean_pred*100, 1)}% success likelihood, but actual completion was {round(mean_actual*100, 1)}%."
        )
    else:
        calibration_status = "WELL_CALIBRATED"
        findings.append(
            f"Well calibrated: Model predictions ({round(mean_pred*100, 1)}%) closely track actual completion frequency ({round(mean_actual*100, 1)}%)."
        )

    # Advisory Calibration Factor
    has_validated_data = total_evaluated >= MIN_EVALUATIONS_VALIDATED
    if mean_pred > 0.05 and has_validated_data:
        raw_factor = mean_actual / mean_pred
        advisory_factor = round(max(0.60, min(1.40, raw_factor)), 2)
        findings.append(f"Validated advisory calibration factor: {advisory_factor}x (applied cautiously with validation checks).")
    else:
        advisory_factor = 1.0
        findings.append(f"Advisory calibration factor set to baseline 1.0x pending {MIN_EVALUATIONS_VALIDATED} evaluated observations.")

    # 4. Construct Reliability Bins
    reliability_bins: List[CalibrationBin] = []
    for low, high, label in BIN_RANGES:
        bin_items = [item for item in pairs if low <= item[0] < high]
        count = len(bin_items)
        if count > 0:
            m_pred = round(sum(p for p, _ in bin_items) / count, 3)
            obs_freq = round(sum(y for _, y in bin_items) / count, 3)
            gap = round(m_pred - obs_freq, 3)
        else:
            m_pred = round((low + min(1.0, high)) / 2.0, 3)
            obs_freq = 0.0
            gap = 0.0

        reliability_bins.append(
            CalibrationBin(
                bin_range=label,
                prediction_count=count,
                mean_predicted_probability=m_pred,
                observed_frequency=obs_freq,
                calibration_gap=gap,
            )
        )

    deadline_acc = round(deadline_correct / deadline_total, 3) if deadline_total > 0 else None
    goal_acc = round(goal_correct / goal_total, 3) if goal_total > 0 else None
    habit_acc = round(habit_correct / habit_total, 3) if habit_total > 0 else None

    if deadline_acc is not None:
        findings.append(f"Deadline risk accuracy: {round(deadline_acc * 100, 1)}% ({deadline_correct}/{deadline_total}).")
    if goal_acc is not None:
        findings.append(f"Goal trajectory accuracy: {round(goal_acc * 100, 1)}% ({goal_correct}/{goal_total}).")
    if habit_acc is not None:
        findings.append(f"Habit decay accuracy: {round(habit_acc * 100, 1)}% ({habit_correct}/{habit_total}).")

    return PredictionCalibrationResponse(
        total_evaluated=total_evaluated,
        brier_score=brier_score,
        calibration_bias=calibration_bias,
        calibration_status=calibration_status,
        advisory_calibration_factor=advisory_factor,
        deadline_risk_accuracy=deadline_acc,
        goal_trajectory_accuracy=goal_acc,
        habit_decay_accuracy=habit_acc,
        reliability_bins=reliability_bins,
        findings_and_warnings=findings,
        has_sufficient_evaluations=has_validated_data,
        evaluated_at=now,
    )
