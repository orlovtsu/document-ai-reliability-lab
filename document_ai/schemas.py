from typing import Literal

from pydantic import BaseModel, Field

QualityStatus = Literal["accept", "review", "reject"]


class DocumentInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=10000)


class FieldMetric(BaseModel):
    field: str
    exact_match_rate: float
    evaluated_rows: int


class QualityDecision(BaseModel):
    status: QualityStatus
    quality_score: float
    reasons: list[str]


class BatchResponse(BaseModel):
    document_count: int
    field_metrics: list[FieldMetric]
    quality_counts: dict[str, int]
    policy_version: str
    duplicate_rate: float
    mean_confidence: float
