# Fraud Risk Streaming

A production-style fraud detection pipeline that handles delayed labels, enforces event-time correctness, and routes high-risk transactions into a capacity-constrained review queue.

Start with [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md), which now acts as the main handoff document for the completed day 1-7 build.

## Quick Start

```bash
make setup
make init-db
make simulate
make backfill-labels
make build-features
make train
make evaluate
make score
make review-queue
make monitor
```

For a single end-to-end run, use:

```bash
make demo
```

## What This Project Demonstrates

- Delayed fraud label handling with maturity-aware training windows
- Event-time-safe feature engineering and leakage checks
- Scoring with ranked review queue routing
- Drift and performance monitoring with a dashboard artifact
- Failure injection for label delay, feature lag, distribution shift, and leakage

## Key Commands

- `make demo` - Run the full pipeline and write `artifacts/reports/demo_summary.json`
- `make monitor` - Write `artifacts/reports/drift_report.json`, `artifacts/reports/performance_metrics.json`, and `artifacts/reports/monitoring_dashboard.html`
- `make inject-failure SCENARIO=label_delay|feature_lag|distribution_shift|leakage` - Reproduce the documented incident scenarios

## Documentation

- [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)
- [docs/PRD.md](docs/PRD.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API.md](docs/API.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [INCIDENTS.md](INCIDENTS.md)

## Testing

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Technology Stack

- Python 3.9+
- SQLite for durable local persistence and event-time queries
- pandas, NumPy, and scikit-learn for the pipeline and model training

## Status

The day 7 polish pass is complete: documentation, demo, and failure injection are now implemented and covered by tests.

## License

MIT License