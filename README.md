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

## Performance Benchmarks

Based on demo run with 2,000 transactions:

| Metric | Value |
|--------|-------|
| **Pipeline Execution Time** | ~6 seconds |
| **Transactions Generated** | 2,000 |
| **Labels with Delays** | 2,000 (3-7 day delay) |
| **Features Engineered** | 2,000 (event-time safe) |
| **Transactions Scored** | 2,000 |

### Model Performance

| Metric | Value |
|--------|-------|
| **PR-AUC** | 84.40% |
| **ROC-AUC** | 99.77% |
| **F1-Score** | 82.35% |

### Resource Usage

- **Database Size**: ~500 KB (SQLite)
- **Processing Throughput**: ~333 transactions/second
- **Memory Footprint**: <100 MB
- **Model Size**: <1 MB (pickled scikit-learn models)

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

## Screenshots & Visualizations

### Monitoring Dashboard

The system generates an interactive HTML dashboard with comprehensive monitoring visualizations:

**Location**: `artifacts/reports/monitoring_dashboard.html`

**Contents**:
- **Model Performance Metrics**: PR-AUC, ROC-AUC, F1-Score trends over time
- **Distribution Drift Detection**: Feature distribution comparisons (training vs production)
- **Score Distribution**: Histogram of fraud risk scores by risk band
- **Review Queue Analytics**: Capacity utilization and overflow tracking
- **Label Delay Analysis**: Distribution of label arrival delays

**How to View**:
```bash
# Generate the dashboard
make monitor

# Open in browser (macOS)
open artifacts/reports/monitoring_dashboard.html

# Open in browser (Linux)
xdg-open artifacts/reports/monitoring_dashboard.html

# Open in browser (Windows)
start artifacts/reports/monitoring_dashboard.html
```

### Available Reports

All reports are generated in `artifacts/reports/` after running the pipeline:

| Report | Description |
|--------|-------------|
| `monitoring_dashboard.html` | Interactive HTML dashboard with all visualizations |
| `drift_report.json` | Feature drift metrics (KS statistic, p-values) |
| `performance_metrics.json` | Model performance on validation set |
| `demo_summary.json` | End-to-end pipeline execution summary |
| `incident_*.md` | Failure injection incident reports |

### Future Enhancements

Planned visualizations for future releases:
- Real-time score distribution updates
- Feature importance evolution over time
- Review queue throughput metrics
- Precision-Recall curves by risk band
- Confusion matrix heatmaps

## License

MIT License