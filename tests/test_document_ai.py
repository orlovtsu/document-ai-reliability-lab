from fastapi.testclient import TestClient

from document_ai.api import app
from document_ai.quality import assess_batch, field_metrics
from document_ai.synthetic import SyntheticConfig, generate_ground_truth, make_batch


client = TestClient(app)


def test_synthetic_batch_is_reproducible():
    first_truth, first_extracted = make_batch(SyntheticConfig(seed=7, rows=100))
    second_truth, second_extracted = make_batch(SyntheticConfig(seed=7, rows=100))
    assert first_truth.equals(second_truth)
    assert first_extracted.equals(second_extracted)


def test_quality_gate_returns_all_statuses_for_noisy_batch():
    _, extracted = make_batch(SyntheticConfig(seed=42, rows=500), corruption_rate=0.35)
    assessed, counts = assess_batch(extracted)
    assert set(counts) <= {"accept", "review", "reject"}
    assert len(assessed) == len(extracted)
    assert sum(counts.values()) == len(extracted)


def test_field_metrics_are_bounded():
    truth, extracted = make_batch(SyntheticConfig(seed=42, rows=100))
    metrics = field_metrics(truth, extracted)
    assert {metric["field"] for metric in metrics} == {
        "document_type", "document_date", "reference_id", "line_count", "total_amount"
    }
    assert all(0 <= metric["exact_match_rate"] <= 1 for metric in metrics)


def test_benchmark_api():
    response = client.post("/benchmark")
    assert response.status_code == 200
    assert response.json()["document_count"] == 500
    assert response.json()["field_metrics"]


def test_truth_schema_has_no_external_data():
    truth = generate_ground_truth(SyntheticConfig(seed=1, rows=5))
    assert truth["document_id"].str.startswith("doc-").all()
    assert truth["reference_id"].str.startswith("REF-").all()
