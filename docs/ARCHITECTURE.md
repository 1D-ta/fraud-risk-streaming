# Architecture

## Scope

This repository is a local batch prototype for fraud-risk scoring with delayed labels.

- Storage: SQLite
- Modeling: scikit-learn
- Execution: Python modules and Make targets
- Monitoring: JSON reports and a local HTML dashboard

This implementation does not include distributed streaming or online serving.

## System Flow

```
Transactions (event_time)
  ↓
Labels (+3-7d delay)
  ↓
Maturity Check (≥7d)
  ↓
Features (event-time safe)
  ↓
Training (mature labels only)
  ↓
Models (LR + GBDT)
  ↓
Scoring (risk bands)
  ↓
Review Queue (capacity=500)
  ↓
Monitoring (drift + performance)
```

## Pipeline

1. `simulation/init_db.py`
2. `simulation/generate_transactions.py`
3. `simulation/generate_labels.py`
4. `simulation/analyze_maturity.py`
5. `features/build_features.py`
6. `features/check_leakage.py`
7. `training/train_model.py`
8. `training/evaluate_model.py`
9. `scoring/score_transactions.py`
10. `review/build_queue.py`
11. `monitoring/drift_detection.py`
12. `monitoring/performance_tracker.py`

`scripts/demo.py` runs the full flow and writes `artifacts/reports/demo_summary.json`.

## Data Model

Tables are defined in `data/schemas/schema.sql`:

- `transactions`
- `labels`
- `features`
- `scores`
- `review_queue`

## Implemented Constraints

- Label maturity window: 7 days (`fraud_risk/config.py`)
- Review queue capacity: 500 (`fraud_risk/config.py`)
- Top-k monitoring cutoff: 100 (`fraud_risk/config.py`)

## Event-Time and Leakage Controls

- Features are computed from historical windows relative to transaction time
- Leakage check fails when `feature_timestamp > transaction_timestamp`
- Training and evaluation use mature labels based on `MATURE_LABEL_AGE_DAYS`

## Model Selection & Calibration

- Logistic Regression: naturally calibrated probabilities
- Gradient Boosting: requires calibration (deferred in prototype)
- Production deployment would include isotonic calibration
- Threshold tuning tied to review capacity, not F1-score
- Evaluation uses precision@k where k = review capacity

Model selection uses PR-AUC on validation set. The best model is retrained on train+validation and saved as `production_model.pkl`.

## Runtime Outputs

- Models: `artifacts/models/*.pkl`
- Reports: `artifacts/reports/*.json`
- Dashboard: `artifacts/reports/monitoring_dashboard.html`
