from fastapi.testclient import TestClient

from document_ai.api import app
from document_ai.quality import assess_batch, confidence_metrics, field_metrics
from document_ai.extractors import FALLBACK_EXTRACTOR, PRIMARY_EXTRACTOR
from document_ai.cloud_adapters import AzureDocumentIntelligenceAdapter, OpenAIVisionFallbackAdapter
from document_ai.reporting import run_cost_quality_sweep, run_scenarios
from document_ai.pipeline import run_cascade
from document_ai.repair import repair_documents
from document_ai.synthetic import CORRUPTION_SCENARIOS, SyntheticConfig, generate_ground_truth, make_batch


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
        "document_type", "document_date", "reference_id", "line_count",
        "subtotal", "tax_amount", "total_amount"
    }
    assert all(0 <= metric["exact_match_rate"] <= 1 for metric in metrics)


def test_benchmark_api():
    response = client.post("/benchmark")
    assert response.status_code == 200
    assert response.json()["document_count"] == 500
    assert response.json()["field_metrics"]
    assert response.json()["policy_version"] == "quality-policy-1.0"


def test_truth_schema_has_no_external_data():
    truth = generate_ground_truth(SyntheticConfig(seed=1, rows=5))
    assert truth["document_id"].str.startswith("doc-").all()
    assert truth["reference_id"].str.startswith("REF-").all()


def test_confidence_metrics_are_bounded():
    truth, extracted = make_batch(SyntheticConfig(seed=5, rows=100))
    metrics = confidence_metrics(truth, extracted)
    assert metrics
    assert all(0 <= metric["accuracy"] <= 1 for metric in metrics)


def test_cascade_reports_coverage_fallback_latency_and_cost():
    result = run_cascade(SyntheticConfig(seed=9, rows=100))
    assert result.summary["fallback_rate"] > 0
    assert 0 < result.summary["page_coverage_rate"] <= 1
    assert result.summary["mean_latency_ms"] >= 180
    assert result.summary["total_cost_units"] > 0


def test_extractor_protocol_profiles_have_explicit_operational_tradeoff():
    assert PRIMARY_EXTRACTOR.latency_ms < FALLBACK_EXTRACTOR.latency_ms
    assert PRIMARY_EXTRACTOR.cost_units < FALLBACK_EXTRACTOR.cost_units


def test_cost_quality_sweep_is_reproducible():
    sweep = run_cost_quality_sweep(SyntheticConfig(seed=9, rows=100))
    assert len(sweep) == 4
    assert sweep["fallback_rate"].between(0, 1).all()
    assert sweep["total_cost_units"].gt(0).all()


def test_cloud_adapters_are_disabled_by_default_and_mockable():
    payload = lambda _: {
        "fields": {"document_date": "2025-01-01"},
        "confidence": {"document_date": 0.93},
        "pages_seen": 2,
    }
    for adapter in (AzureDocumentIntelligenceAdapter(), OpenAIVisionFallbackAdapter()):
        try:
            adapter.extract(b"synthetic")
        except RuntimeError as error:
            assert "disabled" in str(error)
        else:
            raise AssertionError("cloud adapter should be disabled without a backend")
    result = AzureDocumentIntelligenceAdapter(backend=payload).extract(b"synthetic")
    fallback = OpenAIVisionFallbackAdapter(backend=payload).extract(b"synthetic")
    assert result.provider == "azure-document-intelligence"
    assert fallback.provider == "openai-vision-fallback"
    assert result.fields["document_date"] == "2025-01-01"


def test_all_corruption_scenarios_are_reproducible_and_reportable():
    results = run_scenarios(SyntheticConfig(seed=3, rows=80), corruption_rate=0.25)
    assert set(results["scenario"]) == set(CORRUPTION_SCENARIOS)
    assert results[["date_accuracy", "reference_accuracy", "amount_accuracy"]].apply(
        lambda column: column.between(0, 1).all()
    ).all()


def test_repair_normalizes_format_without_inventing_missing_values():
    truth, extracted = make_batch(SyntheticConfig(seed=4, rows=20), scenario="missing_date")
    repaired = repair_documents(extracted)
    assert (repaired.loc[repaired["document_date"] == "", "document_date"] == "").all()
    assert "repair_actions" in repaired
