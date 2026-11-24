import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

class MachineLearningPredictor:
    """
    Conditionally activates Scikit-Learn models when empirical dataset
    satisfies statistical rigor thresholds (N >= 15 with balanced classes).
    Otherwise, gracefully delegates to validated statistical heuristic models.
    """
    MIN_OBSERVATIONS = 15

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.model_version = "statistical_v1"

    def evaluate_training_eligibility(self, completed_tasks: List[Any]) -> Tuple[bool, str]:
        """
        Validates if dataset has sufficient observations and class distribution
        to support ML training without overfitting or biased hallucinations.
        """
        n = len(completed_tasks)
        if n < self.MIN_OBSERVATIONS:
            return False, f"Insufficient observations (N={n} < {self.MIN_OBSERVATIONS}). Statistical mode active."

        # Check outcome variation (e.g. on-time vs overdue)
        on_time = 0
        overdue = 0
        for t in completed_tasks:
            if t.due_date and t.completed_at:
                if t.completed_at.date() <= t.due_date:
                    on_time += 1
                else:
                    overdue += 1

        if min(on_time, overdue) < 3:
            return False, f"Class imbalance detected (on_time={on_time}, overdue={overdue}). At least 3 samples per class required for ML."

        return True, f"Eligible for ML training (N={n}, on_time={on_time}, overdue={overdue})."

    def train_deadline_model(self, completed_tasks: List[Any]) -> bool:
        """
        Trains Logistic Regression model if eligibility criteria are met.
        """
        eligible, reason = self.evaluate_training_eligibility(completed_tasks)
        if not eligible:
            logger.info(f"Skipping ML model training: {reason}")
            self.model_version = "statistical_v1"
            self.is_trained = False
            return False

        try:
            from sklearn.linear_model import LogisticRegression

            X = []
            y = []
            for t in completed_tasks:
                if t.due_date and t.completed_at:
                    est = float(getattr(t, "estimated_duration", 60) or 60)
                    postpones = float(getattr(t, "postpone_count", 0) or 0)
                    priority_val = 2.0 if getattr(t, "priority", "Medium") == "High" else 1.0
                    X.append([est, postpones, priority_val])
                    # 1 = Overdue, 0 = On-time
                    y.append(1 if t.completed_at.date() > t.due_date else 0)

            clf = LogisticRegression(solver="liblinear", random_state=42)
            clf.fit(np.array(X), np.array(y))
            self.model = clf
            self.is_trained = True
            self.model_version = "sklearn_logistic_v1"
            logger.info(f"Trained ML deadline model successfully on N={len(X)} samples.")
            return True
        except Exception as e:
            logger.warning(f"Failed to train ML model: {e}. Falling back to statistical model.")
            self.is_trained = False
            self.model_version = "statistical_v1"
            return False

    def predict_deadline_overdue_prob(
        self,
        estimated_duration: float,
        postpone_count: int,
        priority: str,
        buffer_ratio: float
    ) -> float:
        """
        Returns estimated overdue probability (0.0 to 1.0).
        Uses Scikit-Learn model if trained, else statistical probability function.
        """
        if self.is_trained and self.model is not None:
            try:
                priority_val = 3.0 if priority == "Urgent" else (2.0 if priority == "High" else 1.0)
                feat = np.array([[estimated_duration, float(postpone_count), priority_val]])
                prob = self.model.predict_proba(feat)[0][1]
                return float(prob)
            except Exception as e:
                logger.debug(f"Error in ML prediction: {e}")

        # Statistical distribution model
        # Base probability inversely proportional to buffer ratio
        if buffer_ratio <= 0.2:
            base_prob = 0.90
        elif buffer_ratio <= 0.5:
            base_prob = 0.75
        elif buffer_ratio <= 1.0:
            base_prob = 0.55
        elif buffer_ratio <= 1.5:
            base_prob = 0.30
        else:
            base_prob = 0.10

        # Adjust for postponements (+10% per postponement)
        postpone_adj = min(0.30, postpone_count * 0.10)

        # Adjust for priority urgency
        priority_adj = 0.10 if priority == "Urgent" else (0.05 if priority == "High" else 0.0)

        return min(0.98, max(0.05, base_prob + postpone_adj + priority_adj))
