from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from .synthetic import SyntheticConfig, corrupt_documents, generate_ground_truth


class Extractor(Protocol):
    name: str
    latency_ms: int
    cost_units: float

    def extract(self, truth: pd.DataFrame, config: SyntheticConfig) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class SyntheticExtractor:
    name: str
    latency_ms: int
    cost_units: float
    corruption_rate: float
    scenario: str

    def extract(self, truth: pd.DataFrame, config: SyntheticConfig) -> pd.DataFrame:
        return corrupt_documents(
            truth,
            seed=config.seed + (0 if self.name == "primary" else 700),
            corruption_rate=self.corruption_rate,
            scenario=self.scenario,
        )


PRIMARY_EXTRACTOR = SyntheticExtractor("primary", 180, 1.0, 0.18, "mixed")
FALLBACK_EXTRACTOR = SyntheticExtractor("fallback", 950, 4.5, 0.10, "mixed")


def extract_with(provider: Extractor, config: SyntheticConfig) -> pd.DataFrame:
    return provider.extract(generate_ground_truth(config), config)
