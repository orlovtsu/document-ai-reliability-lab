# Provider Adapter Architecture

The production-inspired architecture has two optional cloud boundaries:

```text
PDF/image bytes
    |
    v
AzureDocumentIntelligenceAdapter  -- quality gate -- accept
    |                                  |
    +---------- fallback --------------+
                                       v
                         OpenAIVisionFallbackAdapter
                                       |
                              repair / reconcile
                                       |
                              review or accept
```

The public lab keeps these adapters disabled by default. They expose the integration contract without requiring credentials, SDK calls, or real documents.

## Why dependency injection

Both adapters accept a `backend` callable. This makes the boundary testable with deterministic fixtures and lets a governed application inject its own SDK client, timeout policy, retry policy, and audit logger.

```python
from document_ai.cloud_adapters import AzureDocumentIntelligenceAdapter

adapter = AzureDocumentIntelligenceAdapter(
    backend=lambda payload: {
        "fields": {"document_date": "2025-01-01"},
        "confidence": {"document_date": 0.92},
        "pages_seen": 2,
    }
)
result = adapter.extract(b"synthetic-document-bytes")
```

The repository intentionally does not embed API keys, endpoints, or production payloads. The adapters are architecture examples, not a request to upload confidential documents to a third party.
