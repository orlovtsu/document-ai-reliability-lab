from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .pipeline import run_cascade
from .policy import QualityPolicy
from .quality import assess_batch, batch_metrics, confidence_metrics
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
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 13, "axes.labelsize": 10})
    colors = {"date_accuracy": "#2f6f9f", "reference_accuracy": "#e07a3f", "amount_accuracy": "#4c956c"}
    scenarios = results["scenario"].str.replace("_", " ").str.title()
    figure, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)

    y = range(len(results))
    for offset, field in zip((-0.22, 0, 0.22), colors):
        bars = axes[0, 0].barh([value + offset for value in y], results[field], height=0.2, color=colors[field], label=field.replace("_", " ").title())
        axes[0, 0].bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    axes[0, 0].set_yticks(list(y), scenarios)
    axes[0, 0].set_xlim(0, 1.12)
    axes[0, 0].set_title("Field accuracy by failure scenario", loc="left", fontweight="bold")
    axes[0, 0].set_xlabel("Exact / tolerance-aware accuracy")
    axes[0, 0].legend(frameon=False, ncol=3, fontsize=8)
    axes[0, 0].grid(axis="x", alpha=0.2)

    left = pd.Series(0.0, index=results.index)
    routing_colors = [("accept_rate", "#4c956c"), ("review_rate", "#e6a23c"), ("reject_rate", "#c94c4c")]
    for field, color in routing_colors:
        bars = axes[0, 1].barh(scenarios, results[field], left=left, color=color, label=field.replace("_rate", "").title())
        left += results[field]
    axes[0, 1].set_xlim(0, 1)
    axes[0, 1].set_title("Quality routing outcome", loc="left", fontweight="bold")
    axes[0, 1].set_xlabel("Share of extracted rows")
    axes[0, 1].legend(frameon=False, ncol=3, fontsize=8)
    axes[0, 1].grid(axis="x", alpha=0.2)

    comparison_y = range(len(results))
    confidence_bars = axes[1, 0].barh([value - 0.14 for value in comparison_y], results["mean_confidence"], height=0.25, color="#345995", label="reported confidence")
    accuracy_bars = axes[1, 0].barh([value + 0.14 for value in comparison_y], results["amount_accuracy"], height=0.25, color="#e07a3f", label="observed amount accuracy")
    axes[1, 0].bar_label(confidence_bars, fmt="%.2f", padding=3, fontsize=8)
    axes[1, 0].bar_label(accuracy_bars, fmt="%.2f", padding=3, fontsize=8)
    axes[1, 0].set_yticks(list(comparison_y), scenarios)
    axes[1, 0].set_xlim(0.7, 1.08)
    axes[1, 0].set_title("Confidence versus observed accuracy", loc="left", fontweight="bold")
    axes[1, 0].set_xlabel("Rate")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 0].grid(axis="x", alpha=0.2)

    bars = axes[1, 1].barh(scenarios, results["duplicate_rate"], color="#c94c4c")
    axes[1, 1].bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    axes[1, 1].set_xlim(0, max(0.05, results["duplicate_rate"].max() * 1.35))
    axes[1, 1].set_title("Duplicate exposure", loc="left", fontweight="bold")
    axes[1, 1].set_xlabel("Duplicate row share")
    axes[1, 1].grid(axis="x", alpha=0.2)

    for axis in axes.flat:
        axis.spines[["top", "right"]].set_visible(False)
    figure.savefig(output_dir / "scenario_matrix.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    axes[0].plot(cost_quality["total_cost_units"], cost_quality["reconciliation_rate"], "o-", color="#2f6f9f", linewidth=2)
    for _, row in cost_quality.iterrows():
        axes[0].annotate(f"t={row['fallback_threshold']:.2f}", (row["total_cost_units"], row["reconciliation_rate"]), xytext=(5, 5), textcoords="offset points", fontsize=8)
    axes[0].set(xlabel="Total cost units", ylabel="Reconciliation rate", title="Cost-quality frontier")
    axes[0].grid(alpha=0.2)
    heatmap = confidence_table.pivot(index="field", columns="confidence_band", values="accuracy").reindex(columns=["low", "medium", "high"])
    image = axes[1].imshow(heatmap.fillna(0).to_numpy(), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    axes[1].set_xticks(range(len(heatmap.columns)), heatmap.columns)
    axes[1].set_yticks(range(len(heatmap.index)), heatmap.index)
    for row_index in range(len(heatmap.index)):
        for col_index in range(len(heatmap.columns)):
            value = heatmap.iloc[row_index, col_index]
            if pd.notna(value):
                axes[1].text(col_index, row_index, f"{value:.2f}", ha="center", va="center", fontsize=9)
    axes[1].set_title("Confidence reliability", loc="left", fontweight="bold")
    axes[1].set_xlabel("Reported confidence band")
    figure.colorbar(image, ax=axes[1], fraction=0.046, pad=0.04, label="Observed accuracy")
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
