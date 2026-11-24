from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class StructuredExplanation:
    """
    Ensures every recommendation provides fully transparent, explainable reasoning
    across four distinct operational facets.
    """
    what_happened: str        # The empirical event or observed metric
    why_generated: str        # The underlying rule, threshold, or causal driver
    suggested_action: str     # The concrete, executable remedy
    why_prioritize: str       # The strategic consequence or impact on weekly goals

    def to_reason_text(self) -> str:
        """
        Synthesizes the 4 facets into an articulate justification string
        for the reason field.
        """
        return (
            f"{self.what_happened} "
            f"{self.why_generated} "
            f"Action: {self.suggested_action} "
            f"Impact: {self.why_prioritize}"
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "what_happened": self.what_happened,
            "why_generated": self.why_generated,
            "suggested_action": self.suggested_action,
            "why_prioritize": self.why_prioritize,
        }
