from dataclasses import dataclass


@dataclass(frozen=True)
class QualityPolicy:
    version: str = "quality-policy-1.0"
    accept_threshold: float = 0.85
    review_threshold: float = 0.55
    amount_tolerance: float = 0.01
    duplicate_action: str = "review"

    def __post_init__(self):
        if not 0 <= self.review_threshold <= self.accept_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 <= review <= accept <= 1")
        if self.duplicate_action not in {"review", "reject"}:
            raise ValueError("duplicate_action must be review or reject")
