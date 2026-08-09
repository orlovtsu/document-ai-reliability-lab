import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from document_ai.quality import assess_batch, field_metrics
from document_ai.synthetic import SyntheticConfig, make_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic document reliability benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--corruption-rate", type=float, default=0.18)
    args = parser.parse_args()
    truth, extracted = make_batch(
        SyntheticConfig(seed=args.seed, rows=args.rows), args.corruption_rate
    )
    _, quality_counts = assess_batch(extracted)
    print(f"documents={len(truth)} extracted_rows={len(extracted)}")
    print("field metrics:")
    for metric in field_metrics(truth, extracted):
        print(f"  {metric['field']}: {metric['exact_match_rate']:.3f}")
    print(f"quality_counts={quality_counts}")


if __name__ == "__main__":
    main()
