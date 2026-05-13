# Fraud Risk Pipeline Prototype

Batch fraud-risk scoring system with delayed label handling and capacity-constrained review queues.

## Constraints Modeled

- Label delay: 3-7 days post-transaction (chargebacks, manual review)
- Label maturity: 7-day window for training eligibility
- Review capacity: 500 transactions/day hard limit

## Implementation

- Storage: SQLite
- Models: Logistic Regression + Gradient Boosting
- Features: 13 event-time-safe features with temporal leakage checks
- Monitoring: Drift detection, performance tracking
- Failure injection: 4 simulated incident scenarios

## Run

```bash
make setup
make init-db
make demo
```

`make demo` runs end-to-end pipeline and writes reports to `artifacts/reports/`.

## Pipeline Steps

```bash
make simulate          # Generate 100K synthetic transactions
make backfill-labels   # Generate delayed labels
make analyze-maturity  # Check label maturity coverage
make build-features    # Build event-time features
make check-leakage     # Validate temporal correctness
make train             # Train models on mature labels
make evaluate          # Select production model
make score             # Score transactions
make review-queue      # Build capacity-constrained queue
make monitor           # Generate drift and performance reports
```

## Key Outputs

- Models: `artifacts/models/production_model.pkl`
- Reports: `artifacts/reports/*.json`
- Dashboard: `artifacts/reports/monitoring_dashboard.html`

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Failure Scenarios

See [INCIDENTS.md](INCIDENTS.md) for simulated operational incidents.

## Testing

```bash
make test
```

## Notes

- This is a local prototype using synthetic data
- Metrics validate pipeline correctness, not business performance
- Production deployment would replace SQLite, add orchestration, and implement online serving