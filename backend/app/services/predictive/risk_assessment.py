from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class RiskAssessmentResult:
    risk_score: float                  # 0.0 to 100.0
    risk_category: str                 # CRITICAL, HIGH, MODERATE, LOW, INSUFFICIENT_DATA
    confidence_score: float            # 0.0 to 1.0
    has_sufficient_data: bool
    title: str
    summary: str
    contributing_factors: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    suggested_action: Optional[str] = None
    predicted_outcome: Optional[str] = None

def calculate_confidence_score(
    sample_size: int,
    benchmark_size: int = 15,
    base_confidence: float = 0.85
) -> float:
    """
    Computes a mathematically sound confidence score based on the volume
    of empirical observations.
    - If sample_size == 0: returns 0.15 (pure baseline heuristic)
    - If sample_size < 3: capped at 0.35 (insufficient observations)
    - Scales linearly up to base_confidence as sample_size approaches benchmark_size
    - Maximum confidence: 0.95
    """
    if sample_size <= 0:
        return 0.15

    if sample_size < 3:
        return round(min(0.35, 0.15 + (sample_size / 3.0) * 0.15), 2)

    ratio = min(1.0, float(sample_size) / float(benchmark_size))
    score = base_confidence * ratio
    return round(min(0.95, max(0.20, score)), 2)

def classify_risk(risk_score: float, has_sufficient_data: bool = True) -> str:
    """
    Classifies a numerical risk score into standard operational categories.
    """
    if not has_sufficient_data and risk_score < 40.0:
        return "INSUFFICIENT_DATA"

    if risk_score >= 80.0:
        return "CRITICAL"
    elif risk_score >= 60.0:
        return "HIGH"
    elif risk_score >= 40.0:
        return "MODERATE"
    else:
        return "LOW"
