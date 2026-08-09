from fastapi import FastAPI

from .quality import assess_batch, field_metrics
from .schemas import BatchResponse, DocumentInput, FieldMetric
from .synthetic import SyntheticConfig, make_batch

app = FastAPI(title="Document AI Reliability Lab", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/benchmark", response_model=BatchResponse)
def benchmark() -> BatchResponse:
    truth, extracted = make_batch(SyntheticConfig())
    _, quality_counts = assess_batch(extracted)
    metrics = field_metrics(truth, extracted)
    return BatchResponse(
        document_count=len(truth),
        field_metrics=[FieldMetric(**metric) for metric in metrics],
        quality_counts=quality_counts,
    )
