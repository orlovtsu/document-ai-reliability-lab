from dataclasses import dataclass

import pandas as pd

from .policy import QualityPolicy
from .quality import assess_batch, batch_metrics
from .repair import repair_documents
from .extractors import FALLBACK_EXTRACTOR, PRIMARY_EXTRACTOR
from .synthetic import SyntheticConfig, generate_ground_truth


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    latency_ms: int
    cost_units: float


PRIMARY = ProviderProfile(PRIMARY_EXTRACTOR.name, PRIMARY_EXTRACTOR.latency_ms, PRIMARY_EXTRACTOR.cost_units)
FALLBACK = ProviderProfile(FALLBACK_EXTRACTOR.name, FALLBACK_EXTRACTOR.latency_ms, FALLBACK_EXTRACTOR.cost_units)


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
    fallback_score_threshold: float = 0.85,
) -> PipelineResult:
    truth = generate_ground_truth(config)
    primary = PRIMARY_EXTRACTOR.extract(truth, config)
    primary = _page_coverage(primary, config.seed)
    primary_assessed, _ = assess_batch(primary, policy)
    fallback_mask = (
        (primary_assessed["coverage_rate"] < 1.0)
        | (primary_assessed["quality_score"] < fallback_score_threshold)
        | primary_assessed["quality_reasons"].map(lambda reasons: "reconciliation_failure" in reasons)
    )
    # Fallback is better, but still imperfect: real fallback stages can fail too.
    fallback = FALLBACK_EXTRACTOR.extract(truth, config)
    fallback = _page_coverage(fallback, config.seed + 17)
    fallback_by_id = fallback.drop_duplicates("document_id").set_index("document_id")
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
