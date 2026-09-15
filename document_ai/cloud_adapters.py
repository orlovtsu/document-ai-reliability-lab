"""Optional cloud-provider adapters with dependency injection.

The public project never performs cloud calls by default. Production integrations can
inject a callable backend after configuring credentials and data governance outside
this repository. Tests use deterministic mock backends.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    fields: dict[str, Any]
    confidence: dict[str, float]
    pages_seen: int
    latency_ms: int
    cost_units: float


@dataclass
class AzureDocumentIntelligenceAdapter:
    """Adapter boundary for a managed document extraction provider."""

    backend: Callable[[bytes], dict[str, Any]] | None = None
    provider_name: str = "azure-document-intelligence"
    latency_ms: int = 180
    cost_units: float = 1.0

    def extract(self, document_bytes: bytes) -> ProviderResult:
        if self.backend is None:
            raise RuntimeError(
                "Azure adapter is disabled in the public lab; inject a governed backend explicitly."
            )
        payload = self.backend(document_bytes)
        return ProviderResult(
            provider=self.provider_name,
            fields=dict(payload.get("fields") or {}),
            confidence=dict(payload.get("confidence") or {}),
            pages_seen=int(payload.get("pages_seen") or 0),
            latency_ms=self.latency_ms,
            cost_units=self.cost_units,
        )


@dataclass
class OpenAIVisionFallbackAdapter:
    """Adapter boundary for a vision-language fallback provider."""

    backend: Callable[[bytes], dict[str, Any]] | None = None
    provider_name: str = "openai-vision-fallback"
    latency_ms: int = 950
    cost_units: float = 4.5

    def extract(self, document_bytes: bytes) -> ProviderResult:
        if self.backend is None:
            raise RuntimeError(
                "Vision fallback is disabled in the public lab; inject a governed backend explicitly."
            )
        payload = self.backend(document_bytes)
        return ProviderResult(
            provider=self.provider_name,
            fields=dict(payload.get("fields") or {}),
            confidence=dict(payload.get("confidence") or {}),
            pages_seen=int(payload.get("pages_seen") or 0),
            latency_ms=self.latency_ms,
            cost_units=self.cost_units,
        )
