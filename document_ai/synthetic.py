from dataclasses import dataclass

import numpy as np
import pandas as pd


FIELDS = ["document_type", "document_date", "reference_id", "total_amount", "line_count"]


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 42
    rows: int = 500


def generate_ground_truth(config: SyntheticConfig = SyntheticConfig()) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    dates = pd.date_range("2025-01-01", periods=config.rows, freq="D")
    return pd.DataFrame(
        {
            "document_id": [f"doc-{index:06d}" for index in range(config.rows)],
            "document_type": rng.choice(["statement", "invoice", "form"], config.rows),
            "document_date": dates.strftime("%Y-%m-%d"),
            "reference_id": [f"REF-{rng.integers(100000, 999999)}" for _ in range(config.rows)],
            "total_amount": np.round(rng.lognormal(4.7, 0.55, config.rows), 2),
            "line_count": rng.integers(1, 18, config.rows),
        }
    )


def _drop_character(value: str, rng: np.random.Generator) -> str:
    if len(value) < 3:
        return value
    index = int(rng.integers(0, len(value)))
    return value[:index] + value[index + 1 :]


def corrupt_documents(
    truth: pd.DataFrame, seed: int = 42, corruption_rate: float = 0.18
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1000)
    extracted = truth.drop(columns=["document_id"]).copy()
    extracted["document_id"] = truth["document_id"]
    extracted["source_row"] = np.arange(len(truth))

    for field in ["document_date", "reference_id"]:
        mask = rng.random(len(extracted)) < corruption_rate
        extracted.loc[mask, field] = extracted.loc[mask, field].map(
            lambda value: _drop_character(value, rng)
        )
    missing_mask = rng.random(len(extracted)) < corruption_rate / 2
    extracted.loc[missing_mask, "document_date"] = ""
    amount_mask = rng.random(len(extracted)) < corruption_rate
    extracted.loc[amount_mask, "total_amount"] = np.round(
        extracted.loc[amount_mask, "total_amount"] * rng.uniform(0.85, 1.15, amount_mask.sum()), 2
    )
    duplicate_count = max(1, int(len(extracted) * corruption_rate / 8)) if len(extracted) else 0
    if duplicate_count:
        extracted = pd.concat([extracted, extracted.sample(duplicate_count, random_state=seed)], ignore_index=True)
    return extracted


def make_batch(config: SyntheticConfig = SyntheticConfig(), corruption_rate: float = 0.18):
    truth = generate_ground_truth(config)
    extracted = corrupt_documents(truth, config.seed, corruption_rate)
    return truth, extracted
