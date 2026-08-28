from dataclasses import dataclass

import pandas as pd

from .policy import QualityPolicy


@dataclass(frozen=True)
class QualityDecision:
    status: str
    quality_score: float
    reasons: list[str]


def assess_row(row: pd.Series, policy: QualityPolicy = QualityPolicy()) -> QualityDecision:
    reasons: list[str] = []
    score = 1.0
    date_value = row.get("document_date")
    parsed_date = pd.to_datetime(date_value, format="%Y-%m-%d", errors="coerce") if date_value else pd.NaT
    if pd.isna(parsed_date):
        score -= 0.35
        reasons.append("invalid_or_missing_date")
    if not isinstance(row.get("reference_id"), str) or not row.get("reference_id", "").startswith("REF-"):
        score -= 0.3
        reasons.append("invalid_reference")
    amount = row.get("total_amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        score -= 0.25
        reasons.append("invalid_amount")
    subtotal = row.get("subtotal")
    tax = row.get("tax_amount")
    if isinstance(subtotal, (int, float)) and isinstance(tax, (int, float)) and isinstance(amount, (int, float)):
        if abs(subtotal + tax - amount) > 0.01:
            score -= 0.3
            reasons.append("reconciliation_failure")
    if row.get("line_count", 0) < 1:
        score -= 0.1
        reasons.append("invalid_line_count")
    if bool(row.get("is_duplicate", False)):
        reasons.append("duplicate_row")
        if policy.duplicate_action == "reject":
            return QualityDecision("reject", 0.0, reasons)
        score -= 0.2
    score = max(0.0, score)
    status = "accept" if score >= policy.accept_threshold else "review" if score >= policy.review_threshold else "reject"
    return QualityDecision(status, score, reasons)


def assess_batch(extracted: pd.DataFrame, policy: QualityPolicy = QualityPolicy()) -> tuple[pd.DataFrame, dict[str, int]]:
    decisions = [assess_row(row, policy) for _, row in extracted.iterrows()]
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
    for field in ["document_type", "document_date", "reference_id", "line_count", "subtotal", "tax_amount"]:
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


def batch_metrics(truth: pd.DataFrame, extracted: pd.DataFrame) -> dict:
    metrics = {metric["field"]: metric["exact_match_rate"] for metric in field_metrics(truth, extracted)}
    duplicate_count = int(extracted.get("is_duplicate", pd.Series(dtype=bool)).sum())
    return {
        "field_metrics": metrics,
        "duplicate_rate": duplicate_count / len(extracted) if len(extracted) else 0.0,
        "mean_confidence": float(
            extracted[[column for column in extracted.columns if column.startswith("confidence_")]].mean().mean()
        ) if len(extracted) else 0.0,
        "rows": int(len(extracted)),
        "reconciliation_rate": float(
            ((extracted["subtotal"] + extracted["tax_amount"] - extracted["total_amount"]).abs() <= 0.01).mean()
        ) if len(extracted) else 0.0,
    }


def confidence_metrics(truth: pd.DataFrame, extracted: pd.DataFrame) -> list[dict]:
    joined = extracted.drop_duplicates("document_id").merge(
        truth, on="document_id", suffixes=("_pred", "_true"), how="inner"
    )
    records = []
    for field in ["document_type", "document_date", "reference_id", "line_count", "total_amount"]:
        confidence = joined[f"confidence_{field}"]
        predicted = joined[f"{field}_pred"]
        expected = joined[f"{field}_true"]
        correct = (predicted - expected).abs() <= 0.01 if field == "total_amount" else predicted == expected
        bands = pd.cut(confidence, [-0.01, 0.7, 0.9, 1.01], labels=["low", "medium", "high"])
        for band, group in pd.DataFrame({"band": bands, "correct": correct}).groupby("band", observed=False):
            records.append({
                "field": field,
                "confidence_band": str(band),
                "rows": int(len(group)),
                "accuracy": float(group["correct"].mean()) if len(group) else 0.0,
            })
    return records
