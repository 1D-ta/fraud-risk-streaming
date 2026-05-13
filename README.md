# Fraud Risk Streaming

A fraud detection system that handles **delayed labels**, enforces **event-time correctness**, and routes transactions into a **capacity-constrained review queue**.

## Overview

**Core Problem**: Fraud labels arrive 3-7 days after transactions. This system demonstrates how to build features, train models, and score transactions without leaking future information while respecting manual review capacity constraints.

**Key Challenges Addressed**:
- Temporal leakage prevention (event-time-safe features)
- Training only on mature labels
- Distribution drift detection
- Capacity-aware review queue ranking

**Architecture**: SQLite for event-time queries and ACID guarantees, scikit-learn models, and JSON reporting. Failure injection scripts reproduce four documented incident scenarios.

## Setup & Run

```bash
make setup           # Create venv and install dependencies
make init-db         # Initialize database
make demo            # Run end-to-end pipeline (2,000 synthetic transactions)
```

**Full Pipeline** (run individually):

```bash
make simulate                # Generate synthetic transactions
make backfill-labels         # Create delayed labels (3-7 day distribution)
make build-features          # Build event-time features
make check-leakage           # Verify temporal correctness
make train                   # Train models on mature labels
make evaluate                # Evaluate and select production model
make score                   # Score transactions
make review-queue            # Build capacity-constrained queue (500-case cap)
make monitor                 # Generate drift and performance reports
```

**Key Outputs**:
- `artifacts/models/production_model.pkl` - selected model
- `artifacts/reports/drift_report.json` - feature distribution metrics
- `artifacts/reports/performance_metrics.json` - model evaluation
- `artifacts/reports/monitoring_dashboard.html` - visualization

## System Design

- **Transaction Generator**: 100,000 synthetic transactions with 2% fraud rate
- **Label Delay**: 3-7 day distribution; only labels >7 days old are considered mature for training
- **Features**: Event-time aggregates (user transaction count, merchant fraud rate, amount z-score, etc.)
- **Training**: LogisticRegression and GradientBoostingClassifier, evaluated on mature data only
- **Scoring**: Risk score (0-1) and risk band (LOW/MED/HIGH/CRITICAL)
- **Review Queue**: Capacity-constrained at 500 cases; ranked by score
- **Monitoring**: PSI-based drift detection, performance tracking, local HTML dashboard

## Constraints & Trade-offs

- **Synthetic Data**: Metrics (ROC-AUC, PR-AUC) are not production benchmarks; the generator produces separable patterns
- **Local Storage**: SQLite instead of distributed infrastructure (Kafka, Flink, etc.)
- **No Real-Time Streaming**: Batch-oriented pipeline; event-time semantics enforced in code
- **Failure Injection**: Simulates 4 realistic failure modes; see `docs/FAILURE_INJECTION_GUIDE.md`

## Testing

```bash
make test   # Run pytest on tests/
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design and data flow
- [docs/API.md](docs/API.md) - Module and function reference
- [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) - Implementation details
- [docs/FAILURE_INJECTION_GUIDE.md](docs/FAILURE_INJECTION_GUIDE.md) - Incident reproduction
- [INCIDENTS.md](INCIDENTS.md) - Four simulated failure scenarios

## Tech Stack

- Python 3.9+
- SQLite (ACID, event-time queries)
- pandas, NumPy, scikit-learn
- pytest for testing

## Monitoring Dashboard

Generate and view the HTML dashboard:

```bash
make monitor
open artifacts/reports/monitoring_dashboard.html
```