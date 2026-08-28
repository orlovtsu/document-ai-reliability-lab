from dataclasses import dataclass

import pandas as pd

from .policy import QualityPolicy
from .quality import assess_batch, batch_metrics
from .repair import repair_documents
from .synthetic import SyntheticConfig, make_batch


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    latency_ms: int
    cost_units: float


PRIMARY = ProviderProfile("primary", latency_ms=180, cost_units=1.0)
FALLBACK = ProviderProfile("fallback", latency_ms=950, cost_units=4.5)


@dataclass(frozen=True)
class PipelineResult:
    records: pd.DataFrame
    summary: dict[str, float | int]


def _page_coverage(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    result = frame.copy()
    result["page_count"] = 3
    result["primary_pages"] = result.apply(
        lambda row: 2 if (row.name + seed) % 11 == 0 else 3, axis=1
    )
    result["coverage_rate"] = result["primary_pages"] / result["page_count"]
    return result


def run_cascade(
    config: SyntheticConfig = SyntheticConfig(),
    corruption_rate: float = 0.18,
    policy: QualityPolicy = QualityPolicy(),
) -> PipelineResult:
    truth, primary = make_batch(config, corruption_rate, scenario="mixed")
    primary = _page_coverage(primary, config.seed)
    primary_assessed, _ = assess_batch(primary, policy)
    fallback_mask = (
        (primary_assessed["coverage_rate"] < 1.0)
        | (primary_assessed["quality_status"] != "accept")
        | primary_assessed["quality_reasons"].map(lambda reasons: "reconciliation_failure" in reasons)
    )
    # Fallback is a synthetic clean extraction with a small residual amount error.
    _, fallback = make_batch(config, corruption_rate=0.03, scenario="clean")
    fallback = _page_coverage(fallback, config.seed + 17)
    fallback_by_id = fallback.set_index("document_id")
    chosen = primary.copy()
    chosen["stage_used"] = PRIMARY.name
    chosen["fallback_reason"] = ""
    chosen["latency_ms"] = PRIMARY.latency_ms
    chosen["cost_units"] = PRIMARY.cost_units
    for index in chosen.index[fallback_mask]:
        document_id = chosen.loc[index, "document_id"]
        fallback_row = fallback_by_id.loc[document_id]
        for column in fallback.columns:
            if column in chosen.columns and column != "document_id":
                chosen.loc[index, column] = fallback_row[column]
        chosen.loc[index, "stage_used"] = FALLBACK.name
        chosen.loc[index, "fallback_reason"] = "coverage_or_quality_gate"
        chosen.loc[index, "latency_ms"] = FALLBACK.latency_ms
        chosen.loc[index, "cost_units"] = FALLBACK.cost_units
    repaired = repair_documents(chosen)
    assessed, counts = assess_batch(repaired, policy)
    summary = batch_metrics(truth, assessed)
    summary.update(
        {
            "fallback_rate": float((assessed["stage_used"] == FALLBACK.name).mean()),
            "page_coverage_rate": float(assessed["coverage_rate"].mean()),
            "mean_latency_ms": float(assessed["latency_ms"].mean()),
            "total_cost_units": float(assessed["cost_units"].sum()),
            "accept_count": int(counts.get("accept", 0)),
            "review_count": int(counts.get("review", 0)),
            "reject_count": int(counts.get("reject", 0)),
        }
    )
    return PipelineResult(assessed, summary)
