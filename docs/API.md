# API Reference

This project is organized as a set of small command-line modules. Each module can be run directly or imported from Python.

## Simulation

### `simulation.init_db.init_database(db_path="data/fraud_risk.db")`

Initializes the SQLite database from `data/schemas/schema.sql`.

Returns: the database path as a string.

### `simulation.generate_transactions.generate_transactions(...)`

Generates synthetic transactions and persists them to `transactions`.

Key arguments:
- `num_transactions`: number of rows to generate
- `fraud_rate`: target fraud rate
- `db_path`: SQLite database path
- `seed`: random seed for reproducibility

Outputs:
- `data/fraud_risk.db`
- `artifacts/reports/transaction_stats.json`

### `simulation.generate_labels.generate_labels(db_path="data/fraud_risk.db", seed=42)`

Creates delayed labels with a 3-7 day delay distribution.

Outputs:
- `artifacts/reports/label_delay_stats.json`

### `simulation.analyze_maturity.analyze_maturity(...)`

Summarizes how many transactions have sufficiently mature labels for training.

## Feature Engineering

### `features.build_features.build_features(db_path="data/fraud_risk.db")`

Builds event-time-safe features and writes them to the `features` table.

Outputs:
- `artifacts/reports/feature_stats.json`

### `features.check_leakage.check_leakage(db_path="data/fraud_risk.db")`

Verifies that `feature_timestamp` never exceeds `timestamp`.

Outputs:
- `artifacts/reports/leakage_check.json`

## Training

### `training.train_model.train_models(db_path="data/fraud_risk.db", maturity_days=7)`

Trains the baseline model candidates and writes model artifacts.

Outputs:
- `artifacts/models/logistic_regression.pkl`
- `artifacts/models/gradient_boosting.pkl`
- `artifacts/reports/training_report_v1.json`

### `training.evaluate_model.evaluate_models(db_path="data/fraud_risk.db", maturity_days=7)`

Evaluates the candidate models, selects the production model, and writes the compatibility alias.

Outputs:
- `artifacts/models/production_model.pkl`
- `artifacts/models/fraud_model_v1.pkl`
- `artifacts/reports/evaluation.json`

## Scoring and Review

### `scoring.score_transactions.score_transactions(db_path="data/fraud_risk.db")`

Scores all transactions with the production model and stores results in `scores`.

Outputs:
- `artifacts/reports/scoring_stats.json`

### `review.build_queue.build_review_queue(db_path="data/fraud_risk.db", capacity=100)`

Builds a capacity-constrained manual review queue from high-risk scores.

Outputs:
- `artifacts/reports/review_queue_stats.json`

## Monitoring

### `monitoring.drift_detection.drift_report(db_path="data/fraud_risk.db")`

Computes PSI-style drift metrics for the feature set and score distribution.

Outputs:
- `artifacts/reports/drift_report.json`

### `monitoring.performance_tracker.performance_report(db_path="data/fraud_risk.db", top_k=100)`

Computes PR-AUC, precision at top-k, and related performance metrics.

Outputs:
- `artifacts/reports/performance_metrics.json`
- `artifacts/reports/monitoring_dashboard.html`

## Demo

### `scripts.demo.run_demo(...)`

Runs the entire pipeline in order and writes a compact summary report.

Outputs:
- `artifacts/reports/demo_summary.json`

## Failure Injection

### `scripts.failure_injection.inject_label_delay.inject_label_delay_spike(...)`

Simulates a label delay spike.

### `scripts.failure_injection.inject_feature_lag.inject_feature_lag(...)`

Simulates stale features for the newest transactions.

### `scripts.failure_injection.inject_distribution_shift.inject_distribution_shift(...)`

Simulates a false positive burst caused by a sudden distribution shift.

### `scripts.failure_injection.inject_leakage.inject_leakage_bug(...)`

Simulates a leakage bug by storing future fraud information in a hidden feature column.