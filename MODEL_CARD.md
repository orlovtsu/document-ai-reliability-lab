# Benchmark Card

## Intended use

This project is a synthetic reliability benchmark for document extraction workflows. It is not an OCR engine and must not be interpreted as production extraction performance.

## Data

All documents and fields are generated locally from seeded random distributions. Corruption is controlled by named scenarios such as missing dates, identifier typos, amount noise, duplicate rows, and mixed failures.

## Metrics

The benchmark reports field-level exact-match rates, tolerance-aware amount accuracy, duplicate rate, confidence-band accuracy, quality-gate outcomes, and scenario comparisons. Confidence is treated as a claim to validate, not as ground truth.

The pipeline report additionally measures fallback rate, page coverage, reconciliation rate, mean latency, and synthetic cost units. These metrics demonstrate an operational trade-off between a fast primary extractor and a slower recovery stage.

## Limitations

The synthetic data does not represent any real document population. Repair heuristics are deliberately conservative and do not recover information that is genuinely absent. A production system would require representative documents, layout-aware extraction, confidence calibration, source drift monitoring, and human review measurement.
