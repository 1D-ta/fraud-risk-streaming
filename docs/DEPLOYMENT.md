# Deployment Guide

This project is designed to be run locally in a single Python virtual environment with SQLite as the persistence layer.

## Prerequisites

- Python 3.9+
- SQLite
- `pip` for installing dependencies

## Setup

```bash
make setup
```

If you prefer manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Full Pipeline

```bash
make init-db
make simulate
make backfill-labels
make analyze-maturity
make build-features
make check-leakage
make train
make evaluate
make score
make review-queue
make monitor
```

The end-to-end demo is available with:

```bash
make demo
```

## Failure Injection

Use these commands to reproduce the operational scenarios described in the documentation:

```bash
make inject-failure SCENARIO=label_delay
make inject-failure SCENARIO=feature_lag
make inject-failure SCENARIO=distribution_shift
make inject-failure SCENARIO=leakage
```

Each scenario writes a report under `artifacts/reports/` and can be followed by the relevant monitoring command.

## Validation

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

You can also run the demo directly to confirm that the entire pipeline still works after a change:

```bash
./.venv/bin/python scripts/demo.py --reset
```

## Outputs

- `data/fraud_risk.db` - SQLite database with transactions, labels, features, scores, and review queue data
- `artifacts/models/` - Serialized model artifacts
- `artifacts/reports/` - Training, scoring, monitoring, and failure-injection reports

## Troubleshooting

- If `make train` fails with missing data, rerun the pipeline from `make init-db` onward.
- If monitoring reports are empty, make sure `make score` and `make review-queue` completed first.
- If `make inject-failure` reports an unknown scenario, confirm the `SCENARIO` value exactly matches one of the supported names.
- If leakage checks fail, inspect recent feature changes for event-time violations before retraining.