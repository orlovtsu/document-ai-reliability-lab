# Document AI Reliability Lab

A domain-neutral, synthetic benchmark for reliable document extraction.

The project models a document-processing workflow rather than a specific industry:

```text
synthetic ground truth -> controlled OCR corruption -> extraction/normalization -> quality gate -> field metrics
```

It contains no real documents, organizations, accounts, products, or production data.

## What this demonstrates

- deterministic synthetic document generation;
- controlled corruption of dates, identifiers, amounts, and duplicate rows;
- field-level exact-match and tolerance-aware metrics;
- quality gates that distinguish accepted, review, and rejected records;
- conservative repair/normalization with explicit repair actions;
- versioned quality policy and confidence-band analysis;
- scenario-level Markdown/PNG benchmark report;
- extractor cascade with fallback, page coverage, reconciliation, latency, and cost metrics;
- explicit extractor protocol with cost/latency provider profiles;
- optional Azure Document Intelligence and OpenAI vision fallback adapter boundaries;
- confidence reliability and cost-quality frontier reports;
- explicit failure taxonomy;
- typed FastAPI endpoint;
- tests, Docker, and CI.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
uvicorn document_ai.api:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API.

## Benchmark

```powershell
python scripts/run_benchmark.py --seed 42 --rows 500
```

The benchmark prints field-level extraction metrics and quality-gate outcomes. All values are synthetic and intended to demonstrate evaluation methodology only.

Generate the detailed scenario report with charts:

```powershell
python scripts/run_benchmark.py --report
```

Open `reports/REPORT.md` for field accuracy, routing outcomes, confidence analysis, duplicate rate, and scenario comparisons.

Additional committed artifacts include `reports/operational_frontier.png`, `reports/cost_quality_sweep.json`, `reports/confidence_reliability.json`, and `reports/cascade_summary.json`.

The report also includes the synthetic extractor cascade: the primary stage is cheap and fast, while the fallback stage is slower and more expensive but improves coverage and quality when the primary quality gate fails.

See [provider adapter architecture](docs/provider-adapters.md) for the cloud integration boundary. Cloud calls are disabled by default and tested through dependency injection.

The committed report compares clean, missing-date, date-shift, identifier-typo, amount-noise, duplicate-row, and mixed-failure scenarios.

## Scope and limitations

This is not an OCR engine and does not claim production extraction performance. It is a compact reliability lab for reasoning about noisy inputs, validation, confidence, repair, and operational routing.
