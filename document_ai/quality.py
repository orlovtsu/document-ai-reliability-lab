from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class QualityDecision:
    status: str
    quality_score: float
    reasons: list[str]


def assess_row(row: pd.Series) -> QualityDecision:
    reasons: list[str] = []
    score = 1.0
    if not row.get("document_date"):
        score -= 0.35
        reasons.append("missing_date")
    if not isinstance(row.get("reference_id"), str) or not row.get("reference_id", "").startswith("REF-"):
        score -= 0.3
        reasons.append("invalid_reference")
    amount = row.get("total_amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        score -= 0.25
        reasons.append("invalid_amount")
    if row.get("line_count", 0) < 1:
        score -= 0.1
        reasons.append("invalid_line_count")
    score = max(0.0, score)
    status = "accept" if score >= 0.85 else "review" if score >= 0.55 else "reject"
    return QualityDecision(status, score, reasons)


def assess_batch(extracted: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    decisions = [assess_row(row) for _, row in extracted.iterrows()]
    result = extracted.copy()
    result["quality_status"] = [decision.status for decision in decisions]
    result["quality_score"] = [decision.quality_score for decision in decisions]
    result["quality_reasons"] = [decision.reasons for decision in decisions]
    return result, result["quality_status"].value_counts().to_dict()


def field_metrics(truth: pd.DataFrame, extracted: pd.DataFrame) -> list[dict]:
    joined = extracted.drop_duplicates("document_id").merge(
        truth, on="document_id", suffixes=("_pred", "_true"), how="inner"
    )
    metrics = []
    for field in ["document_type", "document_date", "reference_id", "line_count"]:
        metrics.append(
            {
                "field": field,
                "exact_match_rate": float(
                    (joined[f"{field}_pred"] == joined[f"{field}_true"]).mean()
                ),
                "evaluated_rows": int(len(joined)),
            }
        )
    amount_match = (joined["total_amount_pred"] - joined["total_amount_true"]).abs() <= 0.01
    metrics.append(
        {
            "field": "total_amount",
            "exact_match_rate": float(amount_match.mean()),
            "evaluated_rows": int(len(joined)),
        }
    )
    return metrics
