from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .policy import QualityPolicy
from .quality import assess_batch, batch_metrics, confidence_metrics, field_metrics
from .pipeline import run_cascade
from .repair import repair_documents
from .synthetic import CORRUPTION_SCENARIOS, SyntheticConfig, make_batch


def run_scenarios(config: SyntheticConfig = SyntheticConfig(), corruption_rate: float = 0.18) -> pd.DataFrame:
    rows = []
    for scenario in CORRUPTION_SCENARIOS:
        truth, extracted = make_batch(config, corruption_rate, scenario)
        repaired = repair_documents(extracted)
        _, counts = assess_batch(repaired, QualityPolicy())
        metrics = batch_metrics(truth, repaired)
        rows.append(
            {
                "scenario": scenario,
                "date_accuracy": metrics["field_metrics"]["document_date"],
                "reference_accuracy": metrics["field_metrics"]["reference_id"],
                "amount_accuracy": metrics["field_metrics"]["total_amount"],
                "duplicate_rate": metrics["duplicate_rate"],
                "mean_confidence": metrics["mean_confidence"],
                "accept_rate": counts.get("accept", 0) / len(repaired),
                "review_rate": counts.get("review", 0) / len(repaired),
                "reject_rate": counts.get("reject", 0) / len(repaired),
            }
        )
    return pd.DataFrame(rows)


def run_cost_quality_sweep(
    config: SyntheticConfig = SyntheticConfig(), corruption_rate: float = 0.18
) -> pd.DataFrame:
    rows = []
    for threshold in (0.55, 0.70, 0.85, 0.95):
        result = run_cascade(config, corruption_rate, fallback_score_threshold=threshold)
        rows.append({
            "fallback_threshold": threshold,
            "fallback_rate": result.summary["fallback_rate"],
            "mean_latency_ms": result.summary["mean_latency_ms"],
            "total_cost_units": result.summary["total_cost_units"],
            "reconciliation_rate": result.summary["reconciliation_rate"],
            "accept_rate": result.summary["accept_count"] / len(result.records),
        })
    return pd.DataFrame(rows)


def build_report(
    config: SyntheticConfig = SyntheticConfig(),
    corruption_rate: float = 0.18,
    output_dir: Path = Path("reports"),
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_scenarios(config, corruption_rate)
    cascade = run_cascade(config, corruption_rate)
    cost_quality = run_cost_quality_sweep(config, corruption_rate)
    truth, raw_extracted = make_batch(config, corruption_rate, scenario="mixed")
    repaired_extracted = repair_documents(raw_extracted)
    confidence_table = pd.DataFrame(confidence_metrics(truth, repaired_extracted))
    figure, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    results.plot.bar(x="scenario", y=["date_accuracy", "reference_accuracy", "amount_accuracy"], ax=axes[0, 0])
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_title("Field accuracy by corruption scenario")
    axes[0, 0].tick_params(axis="x", rotation=30)
    results.plot.bar(x="scenario", y=["accept_rate", "review_rate", "reject_rate"], ax=axes[0, 1])
    axes[0, 1].set_ylim(0, 1)
    axes[0, 1].set_title("Quality routing by scenario")
    axes[0, 1].tick_params(axis="x", rotation=30)
    results.plot.line(x="mean_confidence", y="amount_accuracy", marker="o", ax=axes[1, 0])
    axes[1, 0].set_xlim(0, 1)
    axes[1, 0].set_ylim(0, 1)
    axes[1, 0].set_title("Confidence versus amount accuracy")
    results.plot.bar(x="scenario", y="duplicate_rate", ax=axes[1, 1], color="#c44e52")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].set_title("Duplicate rate")
    axes[1, 1].tick_params(axis="x", rotation=30)
    figure.savefig(output_dir / "scenario_matrix.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    axes[0].plot(cost_quality["total_cost_units"], cost_quality["reconciliation_rate"], "o-")
    axes[0].set(xlabel="Total cost units", ylabel="Reconciliation rate", title="Cost-quality frontier")
    axes[0].grid(alpha=0.2)
    for _, row in confidence_table.iterrows():
        if row["rows"]:
            axes[1].scatter(row["confidence_band"], row["accuracy"], s=max(20, row["rows"]), label=row["field"])
    axes[1].set_ylim(0, 1)
    axes[1].set(title="Confidence reliability", xlabel="Confidence band", ylabel="Observed accuracy")
    axes[1].grid(alpha=0.2)
    figure.savefig(output_dir / "operational_frontier.png", dpi=160)
    plt.close(figure)

    metric_table = "\n".join(
        f"| {row.scenario} | {row.date_accuracy:.3f} | {row.reference_accuracy:.3f} | {row.amount_accuracy:.3f} | {row.accept_rate:.3f} | {row.review_rate:.3f} | {row.reject_rate:.3f} |"
        for row in results.itertuples()
    )
    report = f"""# Document AI Reliability Report

All rows are synthetic. The benchmark compares named corruption scenarios after deterministic normalization and a versioned quality policy.

![Scenario matrix](scenario_matrix.png)

| Scenario | Date accuracy | Reference accuracy | Amount accuracy | Accept | Review | Reject |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{metric_table}

## Methodology

1. Generate deterministic document ground truth.
2. Apply one named corruption scenario.
3. Normalize conservative formatting issues.
4. Score fields and duplicates.
5. Route rows through `quality-policy-1.0`.
6. Compare accuracy, confidence, duplicate rate, and routing outcomes.

## Interpretation

- Missing information is not invented by the repair layer.
- Low-confidence or structurally invalid rows are routed to review or reject.
- Scenario-level metrics make failure modes visible instead of hiding them in one aggregate score.
- Confidence is diagnostic and should be calibrated against field correctness before production use.

## Extraction cascade

The synthetic cascade routes low-quality or incomplete primary extraction through a fallback stage and reports the operational trade-offs.

| Metric | Value |
| --- | ---: |
| Fallback rate | {cascade.summary['fallback_rate']:.3f} |
| Page coverage rate | {cascade.summary['page_coverage_rate']:.3f} |
| Mean latency (ms) | {cascade.summary['mean_latency_ms']:.1f} |
| Total cost units | {cascade.summary['total_cost_units']:.1f} |
| Reconciled rate | {cascade.summary['reconciliation_rate']:.3f} |

The fallback is intentionally more expensive and slower. It is used only when coverage or quality signals justify the operational cost.

## Operational frontier

![Operational frontier](operational_frontier.png)

The left panel shows cost versus reconciliation quality as the fallback threshold changes. The right panel compares reported confidence bands with observed field accuracy. Confidence is a claim to calibrate, not a guarantee.

### Cost-quality sweep

| Fallback threshold | Fallback rate | Mean latency (ms) | Cost units | Reconciled rate | Accept rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
"""
    report += "\n".join(
        f"| {row.fallback_threshold:.2f} | {row.fallback_rate:.3f} | {row.mean_latency_ms:.1f} | {row.total_cost_units:.1f} | {row.reconciliation_rate:.3f} | {row.accept_rate:.3f} |"
        for row in cost_quality.itertuples()
    )
    report += """

### Confidence reliability

Confidence is evaluated against actual field correctness by confidence band:

| Field | Band | Rows | Accuracy |
| --- | --- | ---: | ---: |
"""
    report += "\n".join(
        f"| {row.field} | {row.confidence_band} | {row.rows} | {row.accuracy:.3f} |"
        for row in confidence_table.itertuples()
    )
    report += """

## Limitations

This is a synthetic reliability laboratory, not an OCR engine or real-world fairness/performance claim. Production extension points include layout-aware extraction, confidence calibration, human-review cost measurement, source drift monitoring, and representative document governance.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    results.to_json(output_dir / "scenario_matrix.json", orient="records", indent=2)
    pd.DataFrame([cascade.summary]).to_json(output_dir / "cascade_summary.json", orient="records", indent=2)
    cost_quality.to_json(output_dir / "cost_quality_sweep.json", orient="records", indent=2)
    confidence_table.to_json(output_dir / "confidence_reliability.json", orient="records", indent=2)
    return results
