from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .policy import QualityPolicy
from .quality import assess_batch, batch_metrics, field_metrics
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


def build_report(
    config: SyntheticConfig = SyntheticConfig(),
    corruption_rate: float = 0.18,
    output_dir: Path = Path("reports"),
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_scenarios(config, corruption_rate)
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

## Limitations

This is a synthetic reliability laboratory, not an OCR engine or real-world fairness/performance claim. Production extension points include layout-aware extraction, confidence calibration, human-review cost measurement, source drift monitoring, and representative document governance.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    results.to_json(output_dir / "scenario_matrix.json", orient="records", indent=2)
    return results
