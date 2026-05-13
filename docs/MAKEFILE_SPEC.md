# Makefile Specification: Fraud Risk Streaming

This document provides complete specifications for all Makefile commands in the fraud risk streaming system.

---

## Overview

The Makefile orchestrates the entire fraud detection pipeline, from database initialization to failure injection. All commands are designed to be idempotent and can be run multiple times safely.

**Location**: `Makefile` (project root)

**Usage**: `make <command> [PARAMETERS]`

---

## Command Categories

1. **Setup Commands**: Initialize environment and database
2. **Pipeline Commands**: Run individual pipeline steps
3. **Failure Injection Commands**: Inject failure scenarios
4. **Utility Commands**: Testing, cleaning, help

---

## Setup Commands

### `make help`

Display all available commands with descriptions.

**Parameters**: None

**Output**: Help text to stdout

**Example**:
```bash
make help
```

**Expected Output**:
```
Fraud Risk Streaming - Makefile Commands

Setup:
  make setup              Install dependencies
  make init-db            Initialize SQLite database

Pipeline:
  make simulate           Generate 100k transactions
  ...
```

---

### `make setup`

Install Python dependencies and create virtual environment.

**Parameters**: None

**Dependencies**: Python 3.9+, pip

**Actions**:
1. Create virtual environment in `.venv/`
2. Install packages from `requirements.txt`

**Output**:
- `.venv/` directory with Python environment
- Installed packages: pandas, numpy, scikit-learn, matplotlib, seaborn, pytest

**Example**:
```bash
make setup
```

**Expected Output**:
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
Successfully installed pandas-2.0.3 numpy-1.24.3 scikit-learn-1.3.0 ...
```

**Validation**:
```bash
.venv/bin/python --version
# Expected: Python 3.9.x or higher

.venv/bin/pip list | grep pandas
# Expected: pandas 2.0.3
```

**Notes**:
- Run this command first before any other commands
- Safe to run multiple times (will recreate venv)
- Uses system Python 3

---

### `make init-db`

Initialize SQLite database with schema.

**Parameters**: None

**Dependencies**: `make setup` (virtual environment must exist)

**Actions**:
1. Create `data/` directory if not exists
2. Create `data/fraud_risk.db` SQLite database
3. Create `transactions` table with indexes

**Output**:
- `data/fraud_risk.db` (SQLite database file)
- Console message: "✓ Database initialized: data/fraud_risk.db"

**Example**:
```bash
make init-db
```

**Expected Output**:
```
.venv/bin/python simulation/init_db.py
✓ Database initialized: data/fraud_risk.db
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db ".tables"
# Expected: transactions

sqlite3 data/fraud_risk.db ".schema transactions"
# Expected: CREATE TABLE transactions (...)
```

**Notes**:
- Safe to run multiple times (uses IF NOT EXISTS)
- Creates empty database with schema only
- No data until `make simulate` is run

---

## Pipeline Commands

### `make simulate`

Generate 100,000 synthetic transactions with fraud patterns.

**Parameters**: None

**Dependencies**: `make init-db`

**Actions**:
1. Generate 100k transactions over 30 days
2. Assign fraud labels (2% fraud rate)
3. Insert into `transactions` table
4. Generate statistics report

**Output**:
- `transactions` table populated with 100k rows
- `artifacts/reports/transaction_stats.json`

**Example**:
```bash
make simulate
```

**Expected Output**:
```
.venv/bin/python simulation/generate_transactions.py
✓ Generated 100,000 transactions (2,000 fraud)
✓ Report saved to artifacts/reports/transaction_stats.json
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM transactions"
# Expected: 100000

sqlite3 data/fraud_risk.db "SELECT SUM(is_fraud) FROM transactions"
# Expected: ~2000 (2% fraud rate)

cat artifacts/reports/transaction_stats.json | jq '.fraud_rate'
# Expected: 0.02
```

**Performance**: ~30 seconds

**Notes**:
- Uses fixed random seed (42) for reproducibility
- Fraud patterns: velocity spikes, large amounts, late-night transactions
- Safe to run multiple times (replaces existing data)

---

### `make backfill-labels`

Generate delayed fraud labels (3-7 days after transaction).

**Parameters**: None

**Dependencies**: `make simulate`

**Actions**:
1. Read transactions from database
2. Generate label delays (uniform random 3-7 days)
3. Create `labels` table
4. Insert labels with timestamps
5. Generate delay statistics report

**Output**:
- `labels` table populated with 100k rows
- `artifacts/reports/label_delay_stats.json`

**Example**:
```bash
make backfill-labels
```

**Expected Output**:
```
.venv/bin/python simulation/generate_labels.py
✓ Generated 100,000 delayed labels
✓ Mean delay: 5.0 days
✓ Report saved to artifacts/reports/label_delay_stats.json
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM labels"
# Expected: 100000

sqlite3 data/fraud_risk.db "SELECT AVG(delay_days) FROM labels"
# Expected: ~5.0

cat artifacts/reports/label_delay_stats.json | jq '.delay_stats.median_days'
# Expected: 5.0
```

**Performance**: ~10 seconds

**Notes**:
- Label timestamp always > transaction timestamp + 3 days
- Simulates realistic fraud label arrival delay
- Safe to run multiple times (replaces existing labels)

---

### `make build-features`

Build event-time-correct features for all transactions.

**Parameters**: None

**Dependencies**: `make backfill-labels`

**Actions**:
1. Read transactions from database
2. Compute 6 features for each transaction:
   - `user_txn_count_24h`: User transactions in last 24 hours
   - `user_amount_sum_7d`: User amount sum in last 7 days
   - `merchant_fraud_rate_30d`: Merchant fraud rate in last 30 days
   - `amount_zscore`: Z-score of amount vs user history
   - `hour_of_day`: Hour of transaction (0-23)
   - `is_first_merchant`: First transaction with merchant (0/1)
3. Create `features` table
4. Insert features with timestamps
5. Generate feature statistics report

**Output**:
- `features` table populated with 100k rows
- `artifacts/reports/feature_stats.json`

**Example**:
```bash
make build-features
```

**Expected Output**:
```
.venv/bin/python features/build_features.py
  Processed 10,000 / 100,000 transactions
  Processed 20,000 / 100,000 transactions
  ...
✓ Built features for 100,000 transactions
✓ Report saved to artifacts/reports/feature_stats.json
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM features"
# Expected: 100000

cat artifacts/reports/feature_stats.json | jq '.feature_stats.user_txn_count_24h.mean'
# Expected: ~2.5
```

**Performance**: ~2 minutes (iterative feature computation)

**Notes**:
- All features use only data before transaction timestamp
- Feature computation is slow (intentionally simple for clarity)
- Safe to run multiple times (replaces existing features)
- **Critical**: Must use `timestamp < transaction_timestamp` (not `<=`)

---

### `make check-leakage`

Verify no features use future data (leakage check).

**Parameters**: None

**Dependencies**: `make build-features`

**Actions**:
1. Query database for features with `feature_timestamp > transaction_timestamp`
2. Count violations
3. Generate leakage report
4. Raise error if violations found

**Output**:
- `artifacts/reports/leakage_check.json`
- Exit code 0 if PASS, 1 if FAIL

**Example**:
```bash
make check-leakage
```

**Expected Output (PASS)**:
```
.venv/bin/python features/check_leakage.py
✓ Leakage check PASSED: All features use only past data
```

**Expected Output (FAIL)**:
```
.venv/bin/python features/check_leakage.py
✗ LEAKAGE DETECTED: 1234 features use future data!
ValueError: Leakage check failed: 1234 violations
```

**Validation**:
```bash
cat artifacts/reports/leakage_check.json | jq '.leakage_check'
# Expected: "PASS"

cat artifacts/reports/leakage_check.json | jq '.violations'
# Expected: 0
```

**Performance**: <5 seconds

**Notes**:
- **Critical check**: Must pass before training
- Automated in CI/CD pipeline
- If fails, fix feature code and rebuild features

---

### `make train`

Train LogisticRegression and GradientBoosting models on mature labels.

**Parameters**: None

**Dependencies**: `make check-leakage` (must pass)

**Actions**:
1. Load transactions with mature labels (>7 days old)
2. Temporal split: train on days 1-21, validate on days 22-28
3. Train LogisticRegression model
4. Train GradientBoostingClassifier model
5. Save both models
6. Generate training metadata report

**Output**:
- `artifacts/models/logistic_regression.pkl`
- `artifacts/models/gradient_boosting.pkl`
- `artifacts/reports/training_metadata.json`

**Example**:
```bash
make train
```

**Expected Output**:
```
.venv/bin/python training/train.py
Training set: 75,000 transactions (1,500 fraud)
Validation set: 18,000 transactions (360 fraud)

Training LogisticRegression...
Training GradientBoostingClassifier...

✓ Models trained and saved to artifacts/models/
✓ Metadata saved to artifacts/reports/training_metadata.json
```

**Validation**:
```bash
ls -lh artifacts/models/*.pkl
# Expected: logistic_regression.pkl, gradient_boosting.pkl

cat artifacts/reports/training_metadata.json | jq '.train_size'
# Expected: ~75000
```

**Performance**: ~1 minute

**Notes**:
- Only uses transactions >7 days old (mature labels)
- Temporal split ensures no future leakage
- Both models use `class_weight='balanced'` for imbalanced classes
- Safe to run multiple times (replaces existing models)

---

### `make evaluate`

Evaluate trained models on validation set.

**Parameters**: None

**Dependencies**: `make train`

**Actions**:
1. Load validation data (days 22-28)
2. Load both trained models
3. Compute metrics for each model:
   - PR-AUC (Precision-Recall Area Under Curve)
   - Precision@100 (precision of top 100 scored transactions)
   - Recall@100 (recall of top 100 scored transactions)
   - F1 Score
   - Confusion Matrix
4. Select best model by PR-AUC
5. Save best model as `production_model.pkl`
6. Generate evaluation report

**Output**:
- `artifacts/models/production_model.pkl`
- `artifacts/reports/evaluation.json`

**Example**:
```bash
make evaluate
```

**Expected Output**:
```
.venv/bin/python training/evaluate.py

LOGISTIC_REGRESSION Results:
  PR-AUC: 0.6234
  Precision@100: 0.14
  Recall@100: 0.07
  F1 Score: 0.3456

GRADIENT_BOOSTING Results:
  PR-AUC: 0.6512
  Precision@100: 0.15
  Recall@100: 0.08
  F1 Score: 0.3678

✓ Best model: gradient_boosting (PR-AUC: 0.6512)
✓ Saved as artifacts/models/production_model.pkl
✓ Evaluation report saved to artifacts/reports/evaluation.json
```

**Validation**:
```bash
cat artifacts/reports/evaluation.json | jq '.gradient_boosting.pr_auc'
# Expected: >0.60

ls -lh artifacts/models/production_model.pkl
# Expected: file exists
```

**Performance**: ~30 seconds

**Notes**:
- PR-AUC is primary metric (better than ROC-AUC for imbalanced classes)
- Precision@100 measures review queue effectiveness
- Best model typically GradientBoosting (higher PR-AUC)

---

### `make score`

Score all transactions with production model.

**Parameters**: None

**Dependencies**: `make evaluate`

**Actions**:
1. Load production model
2. Load all transactions with features
3. Compute fraud probability (0-1) for each transaction
4. Assign risk band:
   - CRITICAL: score >= 0.9
   - HIGH: 0.7 <= score < 0.9
   - MEDIUM: 0.3 <= score < 0.7
   - LOW: score < 0.3
5. Extract reason codes (top 3 contributing features)
6. Create `scores` table
7. Insert scores
8. Generate scoring statistics report

**Output**:
- `scores` table populated with 100k rows
- `artifacts/reports/scoring_stats.json`

**Example**:
```bash
make score
```

**Expected Output**:
```
.venv/bin/python scoring/score_transactions.py
✓ Scored 100,000 transactions
  Risk bands: {'LOW': 89000, 'MEDIUM': 9000, 'HIGH': 1500, 'CRITICAL': 500}
✓ Report saved to artifacts/reports/scoring_stats.json
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM scores"
# Expected: 100000

sqlite3 data/fraud_risk.db "SELECT risk_band, COUNT(*) FROM scores GROUP BY risk_band"
# Expected: LOW, MEDIUM, HIGH, CRITICAL counts

cat artifacts/reports/scoring_stats.json | jq '.risk_band_distribution'
# Expected: {"LOW": 89000, "MEDIUM": 9000, "HIGH": 1500, "CRITICAL": 500}
```

**Performance**: ~10 seconds

**Notes**:
- All transactions scored, not just recent ones
- Reason codes help explain predictions
- Safe to run multiple times (replaces existing scores)

---

### `make build-review-queue`

Build capacity-constrained review queue.

**Parameters**: None

**Dependencies**: `make score`

**Actions**:
1. Query HIGH and CRITICAL transactions
2. Sort by score descending
3. Select top 100 for review queue (capacity constraint)
4. Mark remaining as overflow (capacity_exceeded=1)
5. Create `review_queue` table
6. Insert queue entries
7. Generate review queue statistics report

**Output**:
- `review_queue` table populated
- `artifacts/reports/review_queue_stats.json`

**Example**:
```bash
make build-review-queue
```

**Expected Output**:
```
.venv/bin/python review/build_queue.py
✓ Review queue built
  Total HIGH/CRITICAL: 2,000
  Queue size: 100
  Overflow: 1,900
✓ Report saved to artifacts/reports/review_queue_stats.json
```

**Validation**:
```bash
sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM review_queue WHERE capacity_exceeded = 0"
# Expected: 100

sqlite3 data/fraud_risk.db "SELECT COUNT(*) FROM review_queue WHERE capacity_exceeded = 1"
# Expected: ~1900

cat artifacts/reports/review_queue_stats.json | jq '.capacity_exceeded_rate'
# Expected: ~0.95 (95% overflow)
```

**Performance**: <5 seconds

**Notes**:
- Capacity constraint: 100 transactions/day
- Top 100 by score go to queue
- Overflow transactions auto-approved with flag
- Queue precision typically 15% (vs 2% base rate)

---

## Failure Injection Commands

### `make inject-failure SCENARIO=<scenario>`

Inject one of 4 failure scenarios.

**Parameters**:
- `SCENARIO` (required): One of `label_delay`, `feature_lag`, `distribution_shift`, `leakage`

**Dependencies**: `make build-review-queue` (full pipeline must be run first)

**Actions**: Depends on scenario (see below)

**Output**: Depends on scenario (see below)

---

#### Scenario 1: `SCENARIO=label_delay`

Simulate label delay spike (50% of labels delayed 14+ days).

**Actions**:
1. Select 50% of labels randomly
2. Add 7-14 extra days of delay
3. Update `labels` table
4. Generate failure report

**Output**:
- Modified `labels` table
- `artifacts/reports/failure_label_delay.json`

**Example**:
```bash
make inject-failure SCENARIO=label_delay
```

**Expected Output**:
```
.venv/bin/python scripts/failure_injection/inject_label_delay.py
✓ Injected label delay spike
  Affected labels: 50,000
  New median delay: 8.5 days
```

**Impact**:
- Maturity rate drops from 93% to ~47%
- Training data shrinks
- Model recall drops

**Detection**:
```bash
python simulation/analyze_maturity.py
# Expected: maturity_rate < 0.5
```

---

#### Scenario 2: `SCENARIO=feature_lag`

Simulate feature lag (missing last 3 days of transaction data).

**Actions**:
1. Identify transactions in last 3 days
2. Zero out velocity features for these transactions
3. Update `features` table
4. Generate failure report

**Output**:
- Modified `features` table
- `artifacts/reports/failure_feature_lag.json`

**Example**:
```bash
make inject-failure SCENARIO=feature_lag
```

**Expected Output**:
```
.venv/bin/python scripts/failure_injection/inject_feature_lag.py
✓ Injected feature lag
  Affected transactions: 10,000
  Lag: 3 days
```

**Impact**:
- Recent transactions have zero velocity features
- Model blind to recent fraud patterns
- Recall drops for new fraud

**Detection**:
```bash
sqlite3 data/fraud_risk.db "SELECT AVG(user_txn_count_24h) FROM features WHERE transaction_id IN (SELECT transaction_id FROM transactions ORDER BY timestamp DESC LIMIT 10000)"
# Expected: ~0 (vs ~2.5 baseline)
```

---

#### Scenario 3: `SCENARIO=distribution_shift`

Simulate distribution shift (10x transaction amounts).

**Actions**:
1. Select last 1000 transactions
2. Multiply amounts by 10
3. Update `transactions` table
4. Generate failure report

**Output**:
- Modified `transactions` table
- `artifacts/reports/failure_distribution_shift.json`

**Example**:
```bash
make inject-failure SCENARIO=distribution_shift
```

**Expected Output**:
```
.venv/bin/python scripts/failure_injection/inject_distribution_shift.py
✓ Injected distribution shift
  Affected transactions: 1,000
  Amount multiplier: 10x
```

**Impact**:
- False positive rate spikes
- Review queue overwhelmed
- Legitimate transactions blocked

**Detection**:
- Re-run `make score` and `make build-review-queue`
- Check review queue size (should exceed capacity)

---

#### Scenario 4: `SCENARIO=leakage`

Simulate leakage bug (future data in features).

**Actions**:
1. For each transaction, count future fraud by same user
2. Add `future_fraud_count` column to `features` table
3. Update features with leaky data
4. Generate failure report

**Output**:
- Modified `features` table (new column)
- `artifacts/reports/failure_leakage.json`

**Example**:
```bash
make inject-failure SCENARIO=leakage
```

**Expected Output**:
```
.venv/bin/python scripts/failure_injection/inject_leakage.py
✓ Injected leakage bug
  Leaky feature: future_fraud_count
  Run leakage checker to detect!
```

**Impact**:
- Validation metrics too good (PR-AUC > 0.95)
- Production performance much worse
- Model useless in production

**Detection**:
- Re-train model with leaky feature
- Validation PR-AUC will be unrealistically high
- Production performance will be poor

---

## Utility Commands

### `make run-full`

Run complete pipeline from start to finish.

**Parameters**: None

**Dependencies**: `make setup` (virtual environment must exist)

**Actions**:
1. Initialize database
2. Generate transactions
3. Generate labels
4. Build features
5. Check leakage
6. Train models
7. Evaluate models
8. Score transactions
9. Build review queue

**Output**: All pipeline outputs (see individual commands)

**Example**:
```bash
make run-full
```

**Expected Output**:
```
Running full pipeline...
.venv/bin/python simulation/init_db.py
✓ Database initialized: data/fraud_risk.db
.venv/bin/python simulation/generate_transactions.py
✓ Generated 100,000 transactions (2,000 fraud)
...
✓ Pipeline complete! Check artifacts/reports/ for results.
```

**Performance**: ~5 minutes

**Validation**:
```bash
# Check all tables exist
sqlite3 data/fraud_risk.db ".tables"
# Expected: transactions, labels, features, scores, review_queue

# Check all reports exist
ls artifacts/reports/*.json | wc -l
# Expected: 8 files

# Check models exist
ls artifacts/models/*.pkl | wc -l
# Expected: 3 files
```

**Notes**:
- Runs entire pipeline in sequence
- Safe to run multiple times (replaces all data)
- Use for demos and end-to-end testing

---

### `make test`

Run all automated tests.

**Parameters**: None

**Dependencies**: `make run-full` (pipeline must be run first)

**Actions**:
1. Run pytest on `tests/` directory
2. Execute all test files:
   - `test_simulation.py`
   - `test_labels.py`
   - `test_features.py`
   - `test_training.py`
   - `test_scoring.py`
   - `test_failure_injection.py`
   - `test_end_to_end.py`

**Output**: Test results to stdout

**Example**:
```bash
make test
```

**Expected Output**:
```
.venv/bin/pytest tests/ -v
======================== test session starts =========================
tests/test_simulation.py::test_transaction_count PASSED
tests/test_simulation.py::test_fraud_rate PASSED
tests/test_labels.py::test_label_count PASSED
...
======================== 25 passed in 10.5s =========================
```

**Validation**:
```bash
echo $?
# Expected: 0 (all tests passed)
```

**Performance**: ~10 seconds

**Notes**:
- All tests must pass before committing
- Tests validate data integrity, not model performance
- Use `-v` flag for verbose output

---

### `make clean`

Remove all generated files and artifacts.

**Parameters**: None

**Dependencies**: None

**Actions**:
1. Remove SQLite database (`data/*.db`)
2. Remove trained models (`artifacts/models/*.pkl`)
3. Remove reports (`artifacts/reports/*.json`)
4. Remove pytest cache
5. Remove Python cache files (`__pycache__`, `*.pyc`)

**Output**: Clean workspace

**Example**:
```bash
make clean
```

**Expected Output**:
```
rm -rf data/*.db
rm -rf artifacts/models/*.pkl
rm -rf artifacts/reports/*.json
...
```

**Validation**:
```bash
ls data/*.db 2>/dev/null | wc -l
# Expected: 0

ls artifacts/models/*.pkl 2>/dev/null | wc -l
# Expected: 0
```

**Notes**:
- Does NOT remove virtual environment (`.venv/`)
- Does NOT remove source code
- Safe to run anytime
- Use before re-running full pipeline

---

## Command Dependencies

```
make setup
    └─> make init-db
            └─> make simulate
                    └─> make backfill-labels
                            └─> make build-features
                                    └─> make check-leakage
                                            └─> make train
                                                    └─> make evaluate
                                                            └─> make score
                                                                    └─> make build-review-queue
                                                                            └─> make inject-failure
```

**Notes**:
- Each command depends on previous commands
- `make run-full` runs all commands in sequence
- Safe to run individual commands if dependencies met

---

## Error Handling

### Common Errors

**Error**: `make: .venv/bin/python: No such file or directory`
- **Cause**: Virtual environment not created
- **Fix**: Run `make setup` first

**Error**: `sqlite3.OperationalError: no such table: transactions`
- **Cause**: Database not initialized
- **Fix**: Run `make init-db` first

**Error**: `ValueError: Leakage check failed: 1234 violations`
- **Cause**: Features use future data
- **Fix**: Fix feature code, run `make build-features` again

**Error**: `FileNotFoundError: artifacts/models/production_model.pkl`
- **Cause**: Models not trained
- **Fix**: Run `make train` and `make evaluate` first

---

## Performance Benchmarks

| Command | Time | Memory | Disk I/O |
|---------|------|--------|----------|
| `make setup` | 30s | 100 MB | 50 MB |
| `make init-db` | <1s | 10 MB | 1 MB |
| `make simulate` | 30s | 500 MB | 20 MB |
| `make backfill-labels` | 10s | 200 MB | 5 MB |
| `make build-features` | 2m | 1 GB | 10 MB |
| `make check-leakage` | 5s | 100 MB | 1 MB |
| `make train` | 1m | 500 MB | 10 MB |
| `make evaluate` | 30s | 300 MB | 5 MB |
| `make score` | 10s | 500 MB | 5 MB |
| `make build-review-queue` | 5s | 100 MB | 1 MB |
| `make run-full` | 5m | 1 GB | 50 MB |
| `make test` | 10s | 200 MB | 1 MB |

**System Requirements**:
- CPU: 2+ cores
- RAM: 2 GB minimum
- Disk: 100 MB free space
- OS: macOS, Linux, Windows (WSL)

---

## Best Practices

1. **Always run `make setup` first** before any other commands
2. **Run `make run-full`** for demos and end-to-end testing
3. **Run `make test`** before committing code
4. **Run `make clean`** before re-running full pipeline
5. **Check exit codes** to detect failures: `echo $?`
6. **Use `make help`** to see all available commands

---

## Troubleshooting

### Pipeline Fails Midway

**Symptom**: `make run-full` fails at some step

**Diagnosis**:
```bash
# Check which step failed
make run-full 2>&1 | grep "Error"

# Check database state
sqlite3 data/fraud_risk.db ".tables"

# Check reports
ls -lh artifacts/reports/
```

**Fix**:
1. Run `make clean` to remove partial results
2. Run `make run-full` again
3. If still fails, run individual commands to isolate issue

### Tests Fail

**Symptom**: `make test` shows failures

**Diagnosis**:
```bash
# Run tests with verbose output
.venv/bin/pytest tests/ -v -s

# Check specific test
.venv/bin/pytest tests/test_features.py::test_no_leakage -v
```

**Fix**:
1. Read test failure message
2. Check corresponding data/reports
3. Fix issue and re-run pipeline
4. Re-run tests

### Slow Performance

**Symptom**: Commands take much longer than benchmarks

**Diagnosis**:
```bash
# Check system resources
top
df -h

# Profile Python code
.venv/bin/python -m cProfile simulation/generate_transactions.py
```

**Fix**:
1. Close other applications
2. Check disk space
3. Optimize feature computation (if needed)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial Makefile specification |
