from dataclasses import dataclass

import numpy as np
import pandas as pd

FIELDS = ["document_type", "document_date", "reference_id", "total_amount", "line_count"]
CORRUPTION_SCENARIOS = ["clean", "missing_date", "date_shift", "identifier_typo", "amount_noise", "duplicate_row", "mixed"]


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 42
    rows: int = 500


def generate_ground_truth(config: SyntheticConfig = SyntheticConfig()) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    dates = pd.date_range("2025-01-01", periods=config.rows, freq="D")
    truth = pd.DataFrame(
        {
            "document_id": [f"doc-{index:06d}" for index in range(config.rows)],
            "document_type": rng.choice(["statement", "invoice", "form"], config.rows),
            "document_date": dates.strftime("%Y-%m-%d"),
            "reference_id": [f"REF-{rng.integers(100000, 999999)}" for _ in range(config.rows)],
            "subtotal": np.round(rng.lognormal(4.55, 0.55, config.rows), 2),
            "tax_amount": np.round(rng.lognormal(2.8, 0.45, config.rows), 2),
            "line_count": rng.integers(1, 18, config.rows),
        }
    )
    truth["total_amount"] = np.round(truth["subtotal"] + truth["tax_amount"], 2)
    return truth


def _drop_character(value: str, rng: np.random.Generator) -> str:
    if len(value) < 3:
        return value
    index = int(rng.integers(0, len(value)))
    return value[:index] + value[index + 1 :]


def corrupt_documents(
    truth: pd.DataFrame,
    seed: int = 42,
    corruption_rate: float = 0.18,
    scenario: str = "mixed",
) -> pd.DataFrame:
    if scenario not in CORRUPTION_SCENARIOS:
        raise ValueError(f"unknown corruption scenario: {scenario}")
    rng = np.random.default_rng(seed + 1000)
    extracted = truth.drop(columns=["document_id"]).copy()
    extracted["document_id"] = truth["document_id"]
    extracted["source_row"] = np.arange(len(truth))
    extracted["corruption_scenario"] = scenario
    for field in FIELDS:
        extracted[f"confidence_{field}"] = 0.98

    date_scenarios = {"date_shift", "mixed"}
    identifier_scenarios = {"identifier_typo", "mixed"}
    amount_scenarios = {"amount_noise", "mixed"}
    if scenario in date_scenarios:
        field = "document_date"
        mask = rng.random(len(extracted)) < corruption_rate
        extracted.loc[mask, field] = extracted.loc[mask, field].map(lambda value: _drop_character(value, rng))
        extracted.loc[mask, "confidence_document_date"] = 0.55
    if scenario in {"missing_date", "mixed"}:
        missing_mask = rng.random(len(extracted)) < corruption_rate / 2
        extracted.loc[missing_mask, "document_date"] = ""
        extracted.loc[missing_mask, "confidence_document_date"] = 0.1
    if scenario in identifier_scenarios:
        mask = rng.random(len(extracted)) < corruption_rate
        extracted.loc[mask, "reference_id"] = extracted.loc[mask, "reference_id"].map(lambda value: _drop_character(value, rng))
        extracted.loc[mask, "confidence_reference_id"] = 0.55
    if scenario in amount_scenarios:
        amount_mask = rng.random(len(extracted)) < corruption_rate
        extracted.loc[amount_mask, "total_amount"] = np.round(
            extracted.loc[amount_mask, "total_amount"] * rng.uniform(0.85, 1.15, amount_mask.sum()), 2
        )
        extracted.loc[amount_mask, "confidence_total_amount"] = 0.6
    duplicate_count = max(1, int(len(extracted) * corruption_rate / 8)) if len(extracted) and scenario in {"duplicate_row", "mixed"} else 0
    if duplicate_count:
        duplicates = extracted.sample(duplicate_count, random_state=seed).copy()
        duplicates["is_duplicate"] = True
        extracted["is_duplicate"] = False
        extracted = pd.concat([extracted, duplicates], ignore_index=True)
    else:
        extracted["is_duplicate"] = False
    return extracted


def make_batch(config: SyntheticConfig = SyntheticConfig(), corruption_rate: float = 0.18, scenario: str = "mixed"):
    truth = generate_ground_truth(config)
    extracted = corrupt_documents(truth, config.seed, corruption_rate, scenario)
    return truth, extracted
