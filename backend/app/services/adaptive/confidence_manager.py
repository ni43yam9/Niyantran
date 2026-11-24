import math
from datetime import datetime, timezone, date, time
from typing import List, Optional, Any

# Strict minimum-data thresholds
MIN_EVENTS_TIME_OF_DAY = 5
MIN_EVENTS_DAY_OF_WEEK = 7
MIN_BLOCKS_ESTIMATION_BIAS = 3
MIN_INTERACTIONS_REC_WEIGHTS = 3
MIN_EVALUATIONS_CALIBRATION = 5
MIN_EVALUATIONS_VALIDATED = 10
MIN_EVENTS_FULL_PROFILE = 10

def get_time_window_bucket(dt: Any) -> str:
    """
    Categorizes a datetime or time string into one of 4 major daily productivity windows:
    - Morning:   06:00 to 11:59
    - Afternoon: 12:00 to 17:59
    - Evening:   18:00 to 22:59
    - Night:     23:00 to 05:59
    """
    hour = 12
    if isinstance(dt, datetime):
        hour = dt.hour
    elif isinstance(dt, time):
        hour = dt.hour
    elif isinstance(dt, str):
        # Format "09:00 AM" or "14:30"
        s = dt.strip().upper()
        if "AM" in s or "PM" in s:
            try:
                parsed = datetime.strptime(s, "%I:%M %p")
                hour = parsed.hour
            except Exception:
                try:
                    parsed = datetime.strptime(s.split()[0], "%H:%M")
                    hour = parsed.hour
                except Exception:
                    hour = 12
        else:
            try:
                hour = int(s.split(":")[0])
            except Exception:
                hour = 12

    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 18:
        return "Afternoon"
    elif 18 <= hour < 23:
        return "Evening"
    else:
        return "Night"

def calculate_sample_confidence(
    sample_size: int,
    target_threshold: int,
    consistency_ratio: float = 1.0,
) -> float:
    """
    Computes statistical confidence in [0.0, 1.0] based on sample size and observation consistency.
    Enforces that small sample sizes cannot yield high confidence.
    """
    if sample_size <= 0 or target_threshold <= 0:
        return 0.0

    ratio = min(1.0, sample_size / target_threshold)
    # Logarithmic progression to reward larger datasets smoothly
    size_factor = math.sqrt(ratio)
    bounded_consistency = max(0.2, min(1.0, consistency_ratio))
    raw_confidence = size_factor * bounded_consistency

    # Scale to maximum 0.95 (reserving 1.0 for very large datasets)
    return round(min(0.95, max(0.05, raw_confidence)), 2)

def compute_recency_weights(
    timestamps: List[datetime],
    half_life_days: float = 14.0,
    reference_time: Optional[datetime] = None,
) -> List[float]:
    """
    Computes exponential recency decay weights:
    w = 2 ^ (-delta_days / half_life)
    Events occurring within the half-life window retain > 50% weight.
    Enables learned patterns to adapt gracefully as user behavior shifts.
    """
    ref = reference_time or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    weights: List[float] = []
    for ts in timestamps:
        t = ts
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        delta_days = max(0.0, (ref - t).total_seconds() / 86400.0)
        weight = math.pow(2.0, -delta_days / max(1.0, half_life_days))
        weights.append(weight)

    return weights
