# System Architecture: Fraud Risk Streaming

## 1. Overview

This document describes the architecture of the fraud risk streaming system, focusing on **event-time correctness**, **delayed label handling**, and **capacity-constrained review queues**.

**Core Principle**: Every component respects event-time semantics. Features, training, and scoring never use information from the future.

---

## 2. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRAUD RISK STREAMING PIPELINE                     │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   Transaction    │
                              │    Generator     │
                              │  (100k txns)     │
                              └────────┬─────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │      SQLite: transactions        │
                    │  (transaction_id, user_id,       │
                    │   merchant_id, amount,           │
                    │   timestamp, category)           │
                    └──────────┬───────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
    ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
    │ Label Generator  │  │   Feature    │  │  Training Data   │
    │ (3-7 day delay)  │  │   Builder    │  │   Preparation    │
    └────────┬─────────┘  └──────┬───────┘  └────────┬─────────┘
             │                   │                     │
             ▼                   ▼                     │
    ┌──────────────────┐  ┌──────────────────┐       │
    │ SQLite: labels   │  │ SQLite: features │       │
    │ (transaction_id, │  │ (transaction_id, │       │
    │  is_fraud,       │  │  user_txn_count, │       │
    │  label_timestamp,│  │  merchant_fraud, │       │
    │  delay_days)     │  │  amount_zscore,  │       │
    └──────────────────┘  │  hour_of_day)    │       │
                          └──────────┬───────┘       │
                                     │               │
                                     └───────┬───────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   Model Training     │
                                  │  (LogReg + GBM)      │
                                  │  - Mature labels     │
                                  │  - Temporal split    │
                                  │  - Class balancing   │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   Model Artifacts    │
                                  │ artifacts/models/    │
                                  │ - logistic_*.pkl     │
                                  │ - gradient_*.pkl     │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │  Scoring Worker      │
                                  │  - Load model        │
                                  │  - Predict scores    │
                                  │  - Assign risk bands │
                                  │  - Extract reasons   │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   SQLite: scores     │
                                  │ (transaction_id,     │
                                  │  score, risk_band,   │
                                  │  reason_code_1/2/3,  │
                                  │  score_timestamp)    │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ Review Queue Builder │
                                  │ - Filter HIGH/CRIT   │
                                  │ - Sort by score      │
                                  │ - Apply capacity=100 │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ SQLite: review_queue │
                                  │ (transaction_id,     │
                                  │  score, risk_band,   │
                                  │  capacity_exceeded,  │
                                  │  review_status)      │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   Monitoring &       │
                                  │   Reporting          │
                                  │ - Drift detection    │
                                  │ - Performance track  │
                                  │ - Dashboard HTML     │
                                  └──────────────────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │  artifacts/reports/  │
                                  │ - drift_report.json  │
                                  │ - performance_*.json │
                                  │ - monitoring_*.html  │
                                  └──────────────────────┘

Legend:
  ┌─────┐
  │ Box │  = Component or Data Store
  └─────┘
     │
     ▼     = Data Flow Direction
```

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRAUD RISK STREAMING SYSTEM                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Transaction     │  Generates 100k synthetic transactions
│  Generator       │  with realistic fraud patterns
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│                         SQLite Database                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ transactions │  │   labels     │  │   features   │           │
│  │              │  │  (delayed)   │  │ (event-time) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │   scores     │  │ review_queue │                             │
│  └──────────────┘  └──────────────┘                             │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│ Label Generator  │  │Feature Builder│  │Model Training│
│ (3-7 day delay)  │  │(leakage check)│  │(mature only) │
└──────────────────┘  └──────────────┘  └────────┬─────┘
                                                  │
                                                  ▼
                                         ┌──────────────────┐
                                         │  Trained Models  │
                                         │ (LogReg + GBM)   │
                                         └────────┬─────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                      SCORING PIPELINE                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Risk Scoring │→ │ Reason Codes │→ │ Review Queue │           │
│  │ (0-1 score)  │  │ (top 3 feat) │  │ (capacity=100)│           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ Failure Injection│  Simulates 4 realistic failure modes
│ & Monitoring     │  with incident reports
└──────────────────┘
```

---

## 3. Component Details

### 3.1 Transaction Generator

**Purpose**: Simulate realistic transaction stream with fraud patterns.

**Location**: `simulation/generate_transactions.py`

**Inputs**: None (configuration in code)

**Outputs**: 
- SQLite table: `transactions`
- Report: `artifacts/reports/transaction_stats.json`

**Key Features**:
- 100,000 transactions over 30 days
- 2% fraud rate (2,000 fraudulent transactions)
- Fraud patterns:
  - **Velocity spikes**: 5+ transactions in 1 hour
  - **Unusual merchants**: First-time merchant for user
  - **Large amounts**: >3 standard deviations from user mean
  - **Late-night transactions**: 2am-5am local time

**Schema**:
```sql
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    amount REAL NOT NULL,
    timestamp TEXT NOT NULL,  -- ISO 8601 format
    category TEXT NOT NULL,
    is_fraud INTEGER  -- NULL initially, filled by label generator
);
```

**Event-Time Guarantee**: `timestamp` is the transaction event time, never modified.

---

### 3.2 Label Generator

**Purpose**: Simulate delayed fraud label arrival (3-7 days after transaction).

**Location**: `simulation/generate_labels.py`

**Inputs**: 
- `transactions` table (with `is_fraud` column)

**Outputs**:
- SQLite table: `labels`
- Report: `artifacts/reports/label_delay_stats.json`

**Key Features**:
- Labels arrive 3-7 days after transaction (uniform random)
- Simulates real-world label delay (chargebacks, investigations)
- Tracks label arrival time separately from transaction time

**Schema**:
```sql
CREATE TABLE labels (
    transaction_id TEXT PRIMARY KEY,
    is_fraud INTEGER NOT NULL,
    label_timestamp TEXT NOT NULL,  -- When label arrived
    delay_days REAL NOT NULL,  -- label_timestamp - transaction_timestamp
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

**Event-Time Guarantee**: `label_timestamp > transaction_timestamp + 3 days`

**Delay Report**:
```json
{
  "median_delay_days": 5.0,
  "p95_delay_days": 6.8,
  "max_delay_days": 7.0,
  "transactions_with_labels": 100000,
  "label_arrival_histogram": {
    "3": 14285,
    "4": 20000,
    "5": 20000,
    "6": 20000,
    "7": 14285
  }
}
```

---

### 3.3 Feature Builder

**Purpose**: Build event-time-correct features for fraud detection.

**Location**: `features/build_features.py`

**Inputs**:
- `transactions` table
- `labels` table (for historical fraud rates)

**Outputs**:
- SQLite table: `features`
- Report: `artifacts/reports/feature_stats.json`
- Leakage check: `artifacts/reports/leakage_check.json`

**Key Features**:
1. **user_txn_count_24h**: Count of user transactions in last 24 hours
2. **user_amount_sum_7d**: Sum of user transaction amounts in last 7 days
3. **merchant_fraud_rate_30d**: Fraud rate for merchant in last 30 days
4. **amount_zscore**: Z-score of amount vs user's historical mean/std
5. **hour_of_day**: Hour of transaction (0-23)
6. **is_first_merchant**: 1 if user's first transaction with this merchant

**Schema**:
```sql
CREATE TABLE features (
    transaction_id TEXT PRIMARY KEY,
    feature_timestamp TEXT NOT NULL,  -- When features were computed
    user_txn_count_24h INTEGER NOT NULL,
    user_amount_sum_7d REAL NOT NULL,
    merchant_fraud_rate_30d REAL NOT NULL,
    amount_zscore REAL NOT NULL,
    hour_of_day INTEGER NOT NULL,
    is_first_merchant INTEGER NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

**Event-Time Guarantee**: 
```python
# Hard constraint in SQL queries
WHERE feature_timestamp <= transaction_timestamp
```

**Leakage Checker**:
```python
def check_leakage(db_path: str) -> Dict[str, Any]:
    """Verify no features use future data."""
    query = """
    SELECT 
        COUNT(*) as violations
    FROM features f
    JOIN transactions t ON f.transaction_id = t.transaction_id
    WHERE f.feature_timestamp > t.timestamp
    """
    violations = execute_query(query)
    
    if violations > 0:
        raise LeakageError(f"Found {violations} features with future data!")
    
    return {"leakage_violations": 0, "status": "PASS"}
```

---

### 3.4 Model Training

**Purpose**: Train fraud detection models on mature labels only.

**Location**: `training/train.py`

**Inputs**:
- `transactions` table
- `labels` table (filtered for maturity)
- `features` table

**Outputs**:
- Trained models: `artifacts/models/logistic_regression.pkl`, `gradient_boosting.pkl`
- Training report: `artifacts/reports/training_metadata.json`
- Feature importance: `artifacts/reports/feature_importance.json`

**Key Features**:
- **Mature label filter**: Only use transactions >7 days old
- **Temporal split**: Train on days 1-21, validate on days 22-28
- **Two models**: LogisticRegression (baseline), GradientBoostingClassifier (production)
- **Class imbalance handling**: Use `class_weight='balanced'`

**Mature Label Filter**:
```sql
SELECT 
    t.transaction_id,
    t.timestamp,
    l.is_fraud,
    f.*
FROM transactions t
JOIN labels l ON t.transaction_id = l.transaction_id
JOIN features f ON t.transaction_id = f.transaction_id
WHERE julianday('now') - julianday(t.timestamp) > 7  -- Mature labels only
```

**Training Pipeline**:
```python
def train_models(db_path: str) -> Dict[str, Any]:
    # 1. Load mature data
    data = load_mature_data(db_path, maturity_days=7)
    
    # 2. Temporal split
    train_data = data[data['day'] <= 21]
    val_data = data[data['day'] > 21]
    
    # 3. Train models
    lr_model = LogisticRegression(class_weight='balanced')
    gbm_model = GradientBoostingClassifier(n_estimators=100)
    
    lr_model.fit(train_data[FEATURES], train_data['is_fraud'])
    gbm_model.fit(train_data[FEATURES], train_data['is_fraud'])
    
    # 4. Evaluate
    lr_metrics = evaluate_model(lr_model, val_data)
    gbm_metrics = evaluate_model(gbm_model, val_data)
    
    # 5. Save best model
    best_model = gbm_model if gbm_metrics['pr_auc'] > lr_metrics['pr_auc'] else lr_model
    save_model(best_model, 'artifacts/models/production_model.pkl')
    
    return {'lr_metrics': lr_metrics, 'gbm_metrics': gbm_metrics}
```

---

### 3.5 Model Evaluation

**Purpose**: Evaluate models on imbalanced fraud detection task.

**Location**: `training/evaluate.py`

**Inputs**:
- Trained model
- Validation data (days 22-28)

**Outputs**:
- Evaluation report: `artifacts/reports/evaluation.json`

**Metrics**:
1. **PR-AUC** (Precision-Recall Area Under Curve): Primary metric for imbalanced classes
2. **Precision@100**: Precision of top 100 scored transactions (review queue size)
3. **Recall@100**: Recall of top 100 scored transactions
4. **F1 Score**: Harmonic mean of precision and recall
5. **Confusion Matrix**: True positives, false positives, true negatives, false negatives

**Evaluation Code**:
```python
def evaluate_model(model, val_data: pd.DataFrame) -> Dict[str, float]:
    y_true = val_data['is_fraud']
    y_pred_proba = model.predict_proba(val_data[FEATURES])[:, 1]
    
    # PR-AUC (primary metric)
    precision, recall, _ = precision_recall_curve(y_true, y_pred_proba)
    pr_auc = auc(recall, precision)
    
    # Precision@100 (review queue metric)
    top_100_indices = np.argsort(y_pred_proba)[-100:]
    precision_at_100 = y_true.iloc[top_100_indices].mean()
    recall_at_100 = y_true.iloc[top_100_indices].sum() / y_true.sum()
    
    return {
        'pr_auc': pr_auc,
        'precision_at_100': precision_at_100,
        'recall_at_100': recall_at_100,
        'f1_score': f1_score(y_true, y_pred_proba > 0.5)
    }
```

---

### 3.6 Scoring Pipeline

**Purpose**: Score new transactions and assign risk bands.

**Location**: `scoring/score_transactions.py`

**Inputs**:
- Trained model: `artifacts/models/production_model.pkl`
- New transactions with features

**Outputs**:
- SQLite table: `scores`
- Scoring report: `artifacts/reports/scoring_stats.json`

**Risk Bands**:
- **CRITICAL**: score >= 0.9 (top 0.1%)
- **HIGH**: 0.7 <= score < 0.9 (top 1%)
- **MEDIUM**: 0.3 <= score < 0.7 (top 10%)
- **LOW**: score < 0.3 (bottom 90%)

**Schema**:
```sql
CREATE TABLE scores (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL,  -- 0-1 fraud probability
    risk_band TEXT NOT NULL,  -- CRITICAL, HIGH, MEDIUM, LOW
    reason_code_1 TEXT,  -- Top contributing feature
    reason_code_2 TEXT,
    reason_code_3 TEXT,
    score_timestamp TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

**Reason Codes**:
```python
def get_reason_codes(model, features: pd.DataFrame) -> List[str]:
    """Get top 3 features contributing to score."""
    if hasattr(model, 'coef_'):  # LogisticRegression
        feature_importance = np.abs(model.coef_[0])
    else:  # GradientBoosting
        feature_importance = model.feature_importances_
    
    top_3_indices = np.argsort(feature_importance)[-3:][::-1]
    return [FEATURE_NAMES[i] for i in top_3_indices]
```

---

### 3.7 Review Queue

**Purpose**: Route high-risk transactions to manual review with capacity constraint.

**Location**: `review/build_queue.py`

**Inputs**:
- `scores` table
- Capacity policy: 100 transactions/day

**Outputs**:
- SQLite table: `review_queue`
- Queue report: `artifacts/reports/review_queue_stats.json`

**Schema**:
```sql
CREATE TABLE review_queue (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL,
    risk_band TEXT NOT NULL,
    queue_timestamp TEXT NOT NULL,
    capacity_exceeded INTEGER NOT NULL,  -- 1 if beyond capacity
    review_status TEXT DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

**Capacity Policy**:
```python
def build_review_queue(db_path: str, capacity: int = 100) -> Dict[str, Any]:
    """Route top-scored transactions to review queue."""
    # Get all HIGH and CRITICAL transactions
    high_risk = get_high_risk_transactions(db_path)
    
    # Sort by score descending
    high_risk = high_risk.sort_values('score', ascending=False)
    
    # Top 100 go to queue
    queue = high_risk.head(capacity).copy()
    queue['capacity_exceeded'] = 0
    
    # Remaining are auto-approved with flag
    overflow = high_risk.tail(len(high_risk) - capacity).copy()
    overflow['capacity_exceeded'] = 1
    
    # Save to database
    save_review_queue(db_path, pd.concat([queue, overflow]))
    
    return {
        'queue_size': len(queue),
        'overflow_size': len(overflow),
        'capacity_exceeded_rate': len(overflow) / len(high_risk)
    }
```

---

### 3.8 Failure Injection

**Purpose**: Simulate realistic failure modes for incident response practice.

**Location**: `scripts/failure_injection/`

**Scenarios**:
1. **Label Delay Spike**: `inject_label_delay.py`
2. **Feature Lag**: `inject_feature_lag.py`
3. **False Positive Burst**: `inject_distribution_shift.py`
4. **Leakage Bug**: `inject_leakage.py`

**Outputs**:
- Incident reports: `INCIDENTS.md`
- Failure metrics: `artifacts/reports/failure_*.json`

See [FAILURE_INJECTION_GUIDE.md](FAILURE_INJECTION_GUIDE.md) for details.

---

## 4. Data Flow

### 4.1 Training Flow

```
1. Generate Transactions
   └─> transactions table (100k rows)

2. Generate Labels (delayed 3-7 days)
   └─> labels table (100k rows)

3. Build Features (event-time correct)
   └─> features table (100k rows)
   └─> leakage_check.json (PASS/FAIL)

4. Train Models (mature labels only)
   └─> Filter: transactions >7 days old
   └─> Split: days 1-21 train, 22-28 val
   └─> Train: LogReg + GBM
   └─> Evaluate: PR-AUC, Precision@100
   └─> Save: production_model.pkl

5. Generate Reports
   └─> training_metadata.json
   └─> evaluation.json
   └─> feature_importance.json
```

### 4.2 Scoring Flow

```
1. Load New Transactions
   └─> transactions table (new rows)

2. Build Features (event-time correct)
   └─> features table (new rows)
   └─> leakage_check.json (PASS/FAIL)

3. Score Transactions
   └─> Load: production_model.pkl
   └─> Predict: fraud probability (0-1)
   └─> Assign: risk band (CRITICAL/HIGH/MEDIUM/LOW)
   └─> Extract: reason codes (top 3 features)
   └─> Save: scores table

4. Build Review Queue
   └─> Filter: HIGH + CRITICAL transactions
   └─> Sort: by score descending
   └─> Select: top 100 (capacity)
   └─> Flag: overflow as capacity_exceeded
   └─> Save: review_queue table

5. Generate Reports
   └─> scoring_stats.json
   └─> review_queue_stats.json
```

---

## 5. SQLite as Persistence Layer

### 5.1 Why SQLite?

**Advantages**:
- ✅ **Zero setup**: Single file, no server
- ✅ **ACID transactions**: Data integrity guaranteed
- ✅ **SQL queries**: Expressive filtering and aggregation
- ✅ **Portable**: Works on any OS, easy to share
- ✅ **Fast enough**: 100k rows in <1 second
- ✅ **Credible**: Production databases use SQL, this proves you understand it

**Disadvantages** (acceptable for portfolio project):
- ❌ No distributed queries (not needed for 100k rows)
- ❌ No streaming (batch simulation is sufficient)
- ❌ Limited concurrency (single writer, not a problem here)

### 5.2 Database Schema

See [SCHEMA_SPEC.md](SCHEMA_SPEC.md) for complete schema.

**Tables**:
1. `transactions`: Raw transaction data
2. `labels`: Delayed fraud labels
3. `features`: Event-time-correct features
4. `scores`: Model predictions
5. `review_queue`: Transactions for manual review

**Indexes**:
```sql
-- Speed up temporal queries
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_labels_label_timestamp ON labels(label_timestamp);
CREATE INDEX idx_features_feature_timestamp ON features(feature_timestamp);

-- Speed up joins
CREATE INDEX idx_labels_transaction_id ON labels(transaction_id);
CREATE INDEX idx_features_transaction_id ON features(transaction_id);
CREATE INDEX idx_scores_transaction_id ON scores(transaction_id);

-- Speed up review queue queries
CREATE INDEX idx_scores_risk_band ON scores(risk_band);
CREATE INDEX idx_scores_score ON scores(score DESC);
```

---

## 6. Event-Time Correctness Principles

### 6.1 Core Principle

**Every feature must use only data available at transaction time.**

```python
# ✅ CORRECT: Use data before transaction
SELECT COUNT(*) 
FROM transactions 
WHERE user_id = ? 
  AND timestamp < ?  -- Transaction timestamp

# ❌ WRONG: Uses data after transaction (leakage!)
SELECT COUNT(*) 
FROM transactions 
WHERE user_id = ? 
  AND timestamp <= ?  -- Includes transaction itself
```

### 6.2 Leakage Prevention

**Automated Checks**:
1. **Feature timestamp check**: `feature_timestamp <= transaction_timestamp`
2. **Label maturity check**: Only train on transactions >7 days old
3. **Temporal split**: Train on earlier days, validate on later days

**Code Review Checklist**:
- [ ] All SQL queries use `WHERE timestamp < transaction_timestamp`
- [ ] No features use labels (except historical fraud rates)
- [ ] No features use future transactions
- [ ] Training data filtered for label maturity

### 6.3 Common Leakage Bugs

| Bug | Example | Fix |
|-----|---------|-----|
| **Self-inclusion** | `COUNT(*) WHERE timestamp <= T` | Use `timestamp < T` |
| **Label leakage** | Use `is_fraud` in features | Only use historical fraud rates |
| **Future data** | Use transactions after T | Filter `timestamp < T` |
| **Processing time** | Use `CURRENT_TIMESTAMP` | Use `transaction_timestamp` |

---

## 7. System Credibility

### 7.1 Why This Architecture Matters

**Interview Talking Points**:

1. **Delayed Labels**: Most ML projects ignore this. Real fraud systems must handle it.
2. **Event-Time Features**: Prevents leakage, ensures reproducibility.
3. **Capacity Constraints**: Real review teams have limits, system must adapt.
4. **SQLite**: Proves you understand databases without infrastructure drag.
5. **Failure Injection**: Shows you think about what goes wrong, not just happy path.

### 7.2 Production Readiness

**What This System Demonstrates**:
- ✅ Event-time correctness (no leakage)
- ✅ Delayed label handling (realistic constraint)
- ✅ Capacity-aware scoring (business constraint)
- ✅ Failure mode analysis (operational maturity)
- ✅ Reproducible pipeline (Makefile orchestration)

**What's Missing** (intentionally):
- ❌ Real-time streaming (Kafka, Flink)
- ❌ Distributed training (Spark, Ray)
- ❌ Model serving (REST API, gRPC)
- ❌ Monitoring dashboards (Grafana, Datadog)
- ❌ A/B testing framework

**Why Missing**: This is a portfolio project to demonstrate ML engineering principles, not infrastructure skills. Adding these would obscure the core concepts.

---

## 8. Design Decisions

### 8.1 Key Decisions

| Decision | Rationale |
|----------|-----------|
| **SQLite over Postgres** | Zero setup, portable, fast enough for 100k rows |
| **Batch over streaming** | Simpler to implement, proves same principles |
| **Synthetic over real data** | No privacy issues, controllable fraud patterns |
| **LogReg + GBM over deep learning** | Focus on engineering, not model complexity |
| **Makefile over Airflow** | Simpler orchestration, no dependencies |
| **7-day maturity window** | Realistic for fraud (chargebacks take days) |
| **100 transaction review capacity** | Realistic constraint for small fraud team |

### 8.2 Tradeoffs

| Tradeoff | Choice | Why |
|----------|--------|-----|
| **Realism vs Simplicity** | Simplicity | Portfolio project, not production |
| **Performance vs Clarity** | Clarity | Code readability over optimization |
| **Features vs Time** | Time | 7-day project, not 7-month project |
| **Testing vs Coverage** | Coverage | Prove you test, not 100% coverage |

---

## 9. Future Enhancements

**If This Were Production**:

1. **Streaming**: Replace batch with Kafka + Flink
2. **Distributed Training**: Use Spark MLlib or Ray
3. **Model Serving**: REST API with FastAPI
4. **Monitoring**: Prometheus + Grafana dashboards
5. **A/B Testing**: Shadow mode, gradual rollout
6. **Feature Store**: Centralized feature management
7. **Model Registry**: MLflow or custom registry
8. **Alerting**: PagerDuty integration for failures

**Why Not Now**: These add complexity without demonstrating core ML engineering skills. The current architecture proves you understand the principles.

---

## 10. References

- [Event-Time vs Processing-Time](https://www.oreilly.com/radar/the-world-beyond-batch-streaming-101/)
- [Delayed Feedback in ML](https://arxiv.org/abs/1907.06558)
- [SQLite Performance](https://www.sqlite.org/whentouse.html)
- [Fraud Detection Handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/)

---

## 11. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial architecture document |
