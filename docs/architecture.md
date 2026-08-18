# Architecture

```text
synthetic truth -> corruption scenarios -> extraction table -> repair/normalization
                                                   |
                         field metrics <- validation <- quality policy -> accept/review/reject
```

## Boundaries

- `synthetic.py` owns reproducible truth and controlled failure scenarios.
- `repair.py` performs deterministic normalization only; it does not invent missing values.
- `quality.py` measures fields and routes records through a versioned policy.
- `api.py` exposes a small benchmark contract.
- `scripts/run_benchmark.py` is the reproducible command-line entry point.

## Reliability principle

The system distinguishes normalization, validation, and routing. A parser can produce a value, but the quality gate decides whether that value is safe to accept, needs review, or should be rejected.
