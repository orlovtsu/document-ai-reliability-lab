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

## Scope and limitations

This is not an OCR engine and does not claim production extraction performance. It is a compact reliability lab for reasoning about noisy inputs, validation, confidence, repair, and operational routing.
