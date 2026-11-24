import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, Date, DateTime, JSON, Index
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class UserProductivityProfile(Base):
    """
    Stores personalized productivity profile and learned behavioral patterns
    developed in Phase 7: Adaptive Intelligence & Personalized Learning.
    Based strictly on observed user activity, tracking confidence and sample sizes.
    """
    __tablename__ = "user_productivity_profiles"

    id = Column(String(50), primary_key=True, default=lambda: f"prof_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    profile_date = Column(Date, nullable=False, index=True)

    # 1. Preferred Working Periods
    peak_time_window = Column(String(50), nullable=True)          # "Morning", "Afternoon", "Evening", "Night", "INSUFFICIENT_DATA"
    peak_days = Column(JSON, nullable=True)                        # ["Tuesday", "Wednesday"]
    preferred_session_duration_minutes = Column(Integer, nullable=False, default=60)

    # 2. Workload Tolerance & Capacity
    optimal_daily_load_minutes = Column(Integer, nullable=False, default=300)      # Comfortable sustainable focus minutes
    max_observed_sustainable_minutes = Column(Integer, nullable=False, default=360) # Observed maximum before completion collapses

    # 3. Time Estimation Bias
    duration_bias_factor = Column(Float, nullable=False, default=1.25)             # Empirical actual/planned duration ratio
    is_bias_empirical = Column(Boolean, nullable=False, default=False)

    # 4. Behavioral Tendencies
    task_completion_rate = Column(Float, nullable=False, default=0.0)              # Percentage 0.0 to 100.0
    postponement_rate = Column(Float, nullable=False, default=0.0)                 # Percentage 0.0 to 100.0
    procrastination_level = Column(String(30), nullable=False, default="Insufficient Data") # Low, Moderate, High, Insufficient Data
    habit_stability = Column(String(30), nullable=False, default="Insufficient Data")       # High, Moderate, Fragile, Insufficient Data

    # 5. Adaptive Recommendation Weights
    recommendation_weights = Column(JSON, nullable=True)           # Dict[str, float] type multipliers (0.4 to 1.5)

    # 6. Prediction Calibration Summary
    calibration_metrics = Column(JSON, nullable=True)              # Brier score, calibration bias, over/underconfident status

    # 7. Complete Profile Evidence & Structured Breakdown
    profile_data = Column(JSON, nullable=True)                     # Full dictionary of detailed pattern analytics & evidence
    confidence_score = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0 overall statistical confidence
    has_sufficient_history = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_profile_user_date", "user_id", "profile_date"),
    )

    def __repr__(self) -> str:
        return f"<UserProductivityProfile {self.id}: user={self.user_id} peak={self.peak_time_window} conf={self.confidence_score:.2f}>"
