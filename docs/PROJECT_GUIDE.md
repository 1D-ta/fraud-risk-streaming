# Fraud Risk Streaming: Engineering Design

**A production-grade fraud detection system addressing delayed labels, event-time correctness, and review capacity constraints in real-time transaction monitoring.**

---

## Problem Statement

Financial fraud detection presents three fundamental engineering challenges that distinguish it from standard ML classification:

**Delayed Labels**: Fraud confirmation arrives hours to days after transactions occur. Chargebacks, investigation outcomes, and customer disputes create label delays ranging from 2-72 hours. Training pipelines must handle temporal misalignment between transaction events and label availability.

**Event-Time Correctness**: Features must reflect information available at transaction time, not at model training time. Using future information (data leakage) inflates offline metrics but fails in production. A transaction at T₀ can only use features computed from data before T₀.

**Review Capacity Constraints**: Human reviewers can examine only a fraction of transactions (typically 1-10%). The system must optimize fraud detection within this hard capacity limit, balancing precision and recall under operational constraints.

These challenges require careful architectural decisions around temporal semantics, data modeling, and production monitoring.

---

## Architecture

### System Overview

```
┌─────────────────┐
│   Simulation    │  Synthetic transactions + delayed labels
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Feature Store  │  SQLite with event-time semantics
│   (SQLite DB)   │  - transactions (event_time)
└────────┬────────┘  - labels (label_time)
         │           - features (computed at event_time)
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌─────────┐
│Training │ │ Scoring │  Real-time inference
│Pipeline │ │ Service │  - Feature computation
└────┬────┘ └────┬────┘  - Model scoring
     │           │        - Review routing
     ▼           ▼
┌─────────────────┐
│  Review Queue   │  Capacity-constrained prioritization
│  + Monitoring   │  - Drift detection
└─────────────────┘  - Performance tracking
```

### Event-Time Semantics

The architecture enforces strict temporal ordering. Every data operation respects event-time boundaries:

- **Transactions** stored with `event_time` (when transaction occurred)
- **Labels** stored with `label_time` (when fraud confirmed)
- **Features** computed using only data where `event_time < current_transaction_time`
- **Scores** generated at transaction time with available features

This prevents temporal leakage while supporting delayed label integration for model retraining.

### Technology Choices

**SQLite** serves as the feature store for several reasons: ACID transaction guarantees ensure consistency, temporal queries with indexes provide efficient event-time filtering, zero configuration simplifies deployment, and single-file portability aids development. For production scale-out, the schema design translates directly to PostgreSQL or distributed stores.

**Python/scikit-learn** provides rapid prototyping with production-ready ML primitives. The modular design supports migration to TensorFlow or PyTorch for deep learning models.

---

## Data Model

### Schema Design

```sql
CREATE TABLE transactions (
  transaction_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  merchant_id TEXT NOT NULL,
  device_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  amount REAL NOT NULL CHECK (amount > 0),
  currency TEXT NOT NULL,
  merchant_category TEXT NOT NULL,
  channel TEXT NOT NULL,
  location_city TEXT NOT NULL,
  is_international INTEGER NOT NULL,
  fraud_pattern TEXT
);

CREATE TABLE labels (
  transaction_id TEXT PRIMARY KEY,
  label_timestamp TEXT NOT NULL,
  is_fraud INTEGER NOT NULL,
  label_source TEXT NOT NULL,
  label_delay_hours REAL NOT NULL,
  is_mature INTEGER NOT NULL,
  FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE features (
  transaction_id TEXT PRIMARY KEY,
  feature_timestamp TEXT NOT NULL,
  user_txn_count_1h INTEGER NOT NULL,
  user_txn_count_24h INTEGER NOT NULL,
  user_avg_amount_7d REAL NOT NULL,
  user_amount_zscore_7d REAL NOT NULL,
  user_unique_merchants_24h INTEGER NOT NULL,
  merchant_txn_count_1h INTEGER NOT NULL,
  device_user_count_24h INTEGER NOT NULL,
  is_new_device_for_user INTEGER NOT NULL,
  city_change_flag_24h INTEGER NOT NULL,
  amount REAL NOT NULL,
  hour_of_day INTEGER NOT NULL,
  is_weekend INTEGER NOT NULL,
  is_international INTEGER NOT NULL,
  FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

### Temporal Correctness Guarantees

The schema enforces temporal safety through explicit timestamp columns and foreign key constraints. Feature computation queries include temporal filters:

```sql
SELECT 
  COUNT(*) as txn_count,
  AVG(amount) as avg_amount
FROM transactions t
WHERE t.user_id = ?
  AND t.timestamp < ?  -- Critical: only historical data
  AND t.timestamp >= datetime(?, '-7 days')
```

Indexes on `(user_id, timestamp)`, `(merchant_id, timestamp)`, and `(device_id, timestamp)` optimize these temporal range queries.

---

## Leakage Prevention

### Concrete Strategies

**User Aggregates**: Computing `user_fraud_rate` requires filtering by event time:

```python
# INCORRECT - Uses all historical data including future
user_fraud_rate = total_frauds / total_transactions

# CORRECT - Uses only data before event_time
query = """
  SELECT 
    SUM(CASE WHEN l.is_fraud = 1 THEN 1 ELSE 0 END) as frauds,
    COUNT(*) as total
  FROM transactions t
  LEFT JOIN labels l ON t.transaction_id = l.transaction_id
  WHERE t.user_id = ?
    AND t.timestamp < ?
    AND t.timestamp >= datetime(?, '-30 days')
"""
```

**Merchant Velocity**: Transaction counts must exclude the current transaction:

```python
# Merchant transaction count in last hour
query = """
  SELECT COUNT(*) 
  FROM transactions
  WHERE merchant_id = ?
    AND timestamp < ?
    AND timestamp >= datetime(?, '-1 hour')
"""
```

**Device Fingerprinting**: New device detection requires historical device-user associations:

```python
# Check if device seen before for this user
query = """
  SELECT COUNT(*) 
  FROM transactions
  WHERE user_id = ? 
    AND device_id = ?
    AND timestamp < ?
"""
is_new_device = (count == 0)
```

### Validation

Automated leakage detection compares feature distributions between training and inference. Features computed at training time should match features computable at inference time for the same transaction.

---

## Delayed Label Handling

### Maturity Windows

Labels arrive with variable delays. The system defines a **maturity window** (e.g., 72 hours) after which labels are considered stable. Transactions without labels after the maturity window are treated as non-fraud for training purposes.

```python
is_mature = (current_time - transaction_time) > maturity_window
```

### Label Propagation

Training pipeline joins transactions with labels using temporal awareness:

```sql
SELECT 
  t.transaction_id,
  t.timestamp as event_time,
  l.label_timestamp,
  l.is_fraud,
  f.*
FROM transactions t
LEFT JOIN labels l ON t.transaction_id = l.transaction_id
JOIN features f ON t.transaction_id = f.transaction_id
WHERE l.is_mature = 1 OR l.transaction_id IS NULL
```

Unlabeled mature transactions are assigned `is_fraud = 0`, accepting false negatives to maintain training data volume. This tradeoff is monitored via precision/recall metrics on labeled test sets.

---

## Review Queue Management

### Capacity Constraints

The review queue implements hard capacity limits (e.g., 100 transactions per day). Scoring service routes transactions exceeding a risk threshold:

```python
if fraud_score > threshold:
    add_to_review_queue(transaction_id, fraud_score)
```

### Prioritization Logic

Queue entries are ranked by fraud score descending. When capacity is reached, lower-scored transactions are rejected:

```sql
INSERT INTO review_queue (transaction_id, fraud_score, review_rank)
SELECT 
  transaction_id,
  fraud_score,
  ROW_NUMBER() OVER (ORDER BY fraud_score DESC) as rank
FROM scores
WHERE fraud_score > ?
  AND rank <= ?  -- Capacity limit
```

### Threshold Optimization

Threshold selection balances precision (fraud rate in reviewed transactions) and recall (fraction of fraud caught). Offline analysis evaluates precision@k for various capacity levels, selecting thresholds that maximize fraud detection within operational constraints.

---

## Monitoring & Observability

### Drift Detection

**Population Stability Index (PSI)** tracks prediction distribution shifts:

```python
PSI = sum((actual_pct - expected_pct) * ln(actual_pct / expected_pct))
```

PSI > 0.1 indicates minor shift; PSI > 0.25 indicates major shift requiring investigation. Feature-level PSI identifies which inputs are drifting.

### Performance Tracking

Key metrics monitored over time:
- **Precision@k**: Fraud rate in top-k scored transactions
- **Recall@threshold**: Fraction of fraud caught above threshold
- **Score distribution**: Detect calibration drift
- **Label delay distribution**: Monitor data pipeline health
- **Review queue utilization**: Capacity planning

### Failure Injection

The system includes controlled failure scenarios for testing:
- **Label delay injection**: Simulate extended label delays
- **Distribution shift**: Introduce covariate shift in features
- **Feature lag**: Simulate stale feature computation
- **Leakage injection**: Deliberately introduce temporal leakage for detection testing

These scenarios validate monitoring alerting and model degradation detection.

---

## Production Considerations

### Known Limitations

**SQLite Scalability**: Single-writer limitation constrains write throughput to ~1000 TPS. Migration to PostgreSQL or distributed databases required for higher volumes.

**Feature Computation Latency**: Current implementation computes features synchronously. Production systems require feature caching or precomputation for sub-100ms latency.

**Model Retraining**: Manual retraining process. Production requires automated retraining pipelines triggered by drift detection or scheduled intervals.

**Label Feedback Loop**: Delayed labels create training lag. Active learning strategies could prioritize labeling high-uncertainty transactions.

### Migration Path

**Phase 1 (Current)**: SQLite-based prototype with batch scoring. Suitable for <10K transactions/day.

**Phase 2**: PostgreSQL migration with connection pooling. Feature caching layer (Redis). Supports 100K transactions/day.

**Phase 3**: Distributed feature store (Cassandra/DynamoDB). Real-time feature computation (Flink/Spark Streaming). Horizontal scaling to millions of transactions/day.

**Phase 4**: Online learning with streaming model updates. Automated retraining pipelines. A/B testing framework for model variants.

### Scaling Tradeoffs

**Consistency vs. Latency**: Strong consistency (ACID transactions) ensures correctness but limits throughput. Eventual consistency models (e.g., Cassandra) improve latency but complicate temporal correctness guarantees.

**Batch vs. Streaming**: Batch scoring simplifies implementation and reduces infrastructure complexity. Streaming scoring (Kafka + Flink) provides lower latency but requires distributed state management.

**Feature Freshness vs. Computation Cost**: Real-time feature computation provides maximum freshness but increases latency. Precomputed features reduce latency but may be stale. Hybrid approaches cache stable features while computing volatile features on-demand.

---

## Design Decisions Summary

**Event-time semantics**: Chosen over processing-time to ensure reproducibility and prevent leakage. Adds complexity but critical for correctness.

**SQLite for prototyping**: Enables rapid development with production-like semantics. Migration path to distributed systems is well-understood.

**Explicit maturity windows**: Balances training data volume against label quality. Configurable parameter allows tuning based on business requirements.

**Hard capacity constraints**: Reflects real operational limits. Forces explicit precision/recall tradeoffs rather than optimizing unconstrained metrics.

**Comprehensive monitoring**: Drift detection and failure injection validate production readiness. Monitoring-first design enables confident deployment.

The system demonstrates production ML engineering: temporal correctness, operational constraints, monitoring, and scalability planning. Each design decision reflects real-world tradeoffs encountered in financial fraud detection systems.

---

*Engineering Design Document*  
*Version: 2.0*  
*Last Updated: 2026-05-13*