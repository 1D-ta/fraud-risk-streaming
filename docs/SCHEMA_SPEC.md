# SQLite Schema Specification: Fraud Risk Streaming

This document provides complete specifications for all SQLite tables, indexes, and constraints in the fraud risk streaming system.

---

## Overview

**Database**: `data/fraud_risk.db`  
**Engine**: SQLite 3  
**Total Tables**: 5  
**Total Indexes**: 11  
**Storage**: Single file (~50 MB for 100k transactions)

---

## Table of Contents

1. [transactions](#1-transactions-table)
2. [labels](#2-labels-table)
3. [features](#3-features-table)
4. [scores](#4-scores-table)
5. [review_queue](#5-review_queue-table)
6. [Relationships](#6-table-relationships)
7. [Event-Time Correctness Rules](#7-event-time-correctness-rules)
8. [Example Queries](#8-example-queries)

---

## 1. transactions Table

**Purpose**: Store raw transaction data with fraud labels.

**Row Count**: 100,000

**Storage**: ~20 MB

### Schema

```sql
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    amount REAL NOT NULL,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    is_fraud INTEGER
);
```

### Columns

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| `transaction_id` | TEXT | NO | Unique transaction identifier | `txn_00000001` |
| `user_id` | TEXT | NO | User identifier | `user_00123` |
| `merchant_id` | TEXT | NO | Merchant identifier | `merchant_0456` |
| `amount` | REAL | NO | Transaction amount in USD | `125.50` |
| `timestamp` | TEXT | NO | Transaction timestamp (ISO 8601) | `2024-01-15T14:30:00` |
| `category` | TEXT | NO | Transaction category | `retail`, `food`, `travel` |
| `is_fraud` | INTEGER | YES | Fraud label (0=legit, 1=fraud, NULL=unknown) | `0`, `1`, `NULL` |

### Constraints

- **Primary Key**: `transaction_id`
- **Check Constraints**:
  - `amount > 0`
  - `is_fraud IN (0, 1, NULL)`
  - `category IN ('retail', 'food', 'travel', 'entertainment', 'other')`

### Indexes

```sql
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_merchant_id ON transactions(merchant_id);
```

**Index Usage**:
- `idx_transactions_timestamp`: Temporal queries, feature computation
- `idx_transactions_user_id`: User velocity features
- `idx_transactions_merchant_id`: Merchant fraud rate features

### Data Distribution

| Metric | Value |
|--------|-------|
| Total Rows | 100,000 |
| Unique Users | ~10,000 |
| Unique Merchants | ~1,000 |
| Fraud Rate | 2% (2,000 frauds) |
| Amount Range | $1 - $500 |
| Date Range | 30 days |

### Example Rows

```sql
SELECT * FROM transactions LIMIT 3;
```

| transaction_id | user_id | merchant_id | amount | timestamp | category | is_fraud |
|----------------|---------|-------------|--------|-----------|----------|----------|
| txn_00000001 | user_00123 | merchant_0456 | 125.50 | 2024-01-01T10:30:00 | retail | 0 |
| txn_00000002 | user_00456 | merchant_0789 | 45.20 | 2024-01-01T11:15:00 | food | 0 |
| txn_00000003 | user_00123 | merchant_0456 | 850.00 | 2024-01-01T14:45:00 | retail | 1 |

---

## 2. labels Table

**Purpose**: Store delayed fraud labels with arrival timestamps.

**Row Count**: 100,000 (one per transaction)

**Storage**: ~5 MB

### Schema

```sql
CREATE TABLE labels (
    transaction_id TEXT PRIMARY KEY,
    is_fraud INTEGER NOT NULL,
    label_timestamp TEXT NOT NULL,
    delay_days REAL NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

### Columns

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| `transaction_id` | TEXT | NO | Transaction identifier (FK) | `txn_00000001` |
| `is_fraud` | INTEGER | NO | Fraud label (0=legit, 1=fraud) | `0`, `1` |
| `label_timestamp` | TEXT | NO | When label arrived (ISO 8601) | `2024-01-06T10:30:00` |
| `delay_days` | REAL | NO | Days between transaction and label | `5.0` |

### Constraints

- **Primary Key**: `transaction_id`
- **Foreign Key**: `transaction_id` → `transactions(transaction_id)`
- **Check Constraints**:
  - `is_fraud IN (0, 1)`
  - `delay_days >= 3.0 AND delay_days <= 7.0`

### Indexes

```sql
CREATE INDEX idx_labels_label_timestamp ON labels(label_timestamp);
CREATE INDEX idx_labels_transaction_id ON labels(transaction_id);
```

**Index Usage**:
- `idx_labels_label_timestamp`: Label arrival monitoring
- `idx_labels_transaction_id`: Join with transactions

### Data Distribution

| Metric | Value |
|--------|-------|
| Total Rows | 100,000 |
| Mean Delay | 5.0 days |
| Median Delay | 5.0 days |
| Min Delay | 3.0 days |
| Max Delay | 7.0 days |
| P95 Delay | 6.8 days |

### Event-Time Rule

**Critical Constraint**: `label_timestamp > transaction_timestamp + 3 days`

```sql
-- Verify constraint
SELECT COUNT(*) as violations
FROM labels l
JOIN transactions t ON l.transaction_id = t.transaction_id
WHERE julianday(l.label_timestamp) - julianday(t.timestamp) < 3.0;
-- Expected: 0 violations
```

### Example Rows

```sql
SELECT * FROM labels LIMIT 3;
```

| transaction_id | is_fraud | label_timestamp | delay_days |
|----------------|----------|-----------------|------------|
| txn_00000001 | 0 | 2024-01-06T10:30:00 | 5.0 |
| txn_00000002 | 0 | 2024-01-05T11:15:00 | 4.0 |
| txn_00000003 | 1 | 2024-01-08T14:45:00 | 7.0 |

---

## 3. features Table

**Purpose**: Store event-time-correct features for fraud detection.

**Row Count**: 100,000 (one per transaction)

**Storage**: ~15 MB

### Schema

```sql
CREATE TABLE features (
    transaction_id TEXT PRIMARY KEY,
    feature_timestamp TEXT NOT NULL,
    user_txn_count_24h INTEGER NOT NULL,
    user_amount_sum_7d REAL NOT NULL,
    merchant_fraud_rate_30d REAL NOT NULL,
    amount_zscore REAL NOT NULL,
    hour_of_day INTEGER NOT NULL,
    is_first_merchant INTEGER NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

### Columns

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| `transaction_id` | TEXT | NO | Transaction identifier (FK) | `txn_00000001` |
| `feature_timestamp` | TEXT | NO | When features were computed | `2024-01-01T10:30:00` |
| `user_txn_count_24h` | INTEGER | NO | User transactions in last 24 hours | `3` |
| `user_amount_sum_7d` | REAL | NO | User amount sum in last 7 days | `450.75` |
| `merchant_fraud_rate_30d` | REAL | NO | Merchant fraud rate in last 30 days | `0.05` |
| `amount_zscore` | REAL | NO | Z-score of amount vs user history | `2.5` |
| `hour_of_day` | INTEGER | NO | Hour of transaction (0-23) | `14` |
| `is_first_merchant` | INTEGER | NO | First transaction with merchant (0/1) | `0`, `1` |

### Constraints

- **Primary Key**: `transaction_id`
- **Foreign Key**: `transaction_id` → `transactions(transaction_id)`
- **Check Constraints**:
  - `user_txn_count_24h >= 0`
  - `user_amount_sum_7d >= 0`
  - `merchant_fraud_rate_30d >= 0 AND merchant_fraud_rate_30d <= 1`
  - `hour_of_day >= 0 AND hour_of_day <= 23`
  - `is_first_merchant IN (0, 1)`

### Indexes

```sql
CREATE INDEX idx_features_transaction_id ON features(transaction_id);
CREATE INDEX idx_features_feature_timestamp ON features(feature_timestamp);
```

**Index Usage**:
- `idx_features_transaction_id`: Join with transactions
- `idx_features_feature_timestamp`: Leakage checking

### Data Distribution

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| `user_txn_count_24h` | 2.5 | 1.8 | 0 | 15 |
| `user_amount_sum_7d` | 350.0 | 200.0 | 0 | 2000 |
| `merchant_fraud_rate_30d` | 0.02 | 0.05 | 0 | 0.5 |
| `amount_zscore` | 0.0 | 1.5 | -3 | 5 |
| `hour_of_day` | 12 | 6 | 0 | 23 |
| `is_first_merchant` | 0.3 | 0.46 | 0 | 1 |

### Event-Time Rule

**Critical Constraint**: `feature_timestamp <= transaction_timestamp`

```sql
-- Verify constraint (leakage check)
SELECT COUNT(*) as violations
FROM features f
JOIN transactions t ON f.transaction_id = t.transaction_id
WHERE f.feature_timestamp > t.timestamp;
-- Expected: 0 violations
```

### Feature Computation Logic

**Example: user_txn_count_24h**
```sql
-- Count user transactions in last 24 hours (before this transaction)
SELECT COUNT(*) as user_txn_count_24h
FROM transactions
WHERE user_id = ?
  AND timestamp < ?  -- CRITICAL: Use < not <=
  AND timestamp >= datetime(?, '-1 day');
```

**Example: merchant_fraud_rate_30d**
```sql
-- Compute merchant fraud rate in last 30 days (before this transaction)
SELECT AVG(is_fraud) as merchant_fraud_rate_30d
FROM transactions
WHERE merchant_id = ?
  AND timestamp < ?  -- CRITICAL: Use < not <=
  AND timestamp >= datetime(?, '-30 days');
```

### Example Rows

```sql
SELECT * FROM features LIMIT 3;
```

| transaction_id | feature_timestamp | user_txn_count_24h | user_amount_sum_7d | merchant_fraud_rate_30d | amount_zscore | hour_of_day | is_first_merchant |
|----------------|-------------------|--------------------|--------------------|-------------------------|---------------|-------------|-------------------|
| txn_00000001 | 2024-01-01T10:30:00 | 0 | 0.0 | 0.0 | 0.0 | 10 | 1 |
| txn_00000002 | 2024-01-01T11:15:00 | 0 | 0.0 | 0.0 | 0.0 | 11 | 1 |
| txn_00000003 | 2024-01-01T14:45:00 | 1 | 125.50 | 0.0 | 2.5 | 14 | 0 |

---

## 4. scores Table

**Purpose**: Store model predictions with risk bands and reason codes.

**Row Count**: 100,000 (one per transaction)

**Storage**: ~10 MB

### Schema

```sql
CREATE TABLE scores (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL,
    risk_band TEXT NOT NULL,
    reason_code_1 TEXT,
    reason_code_2 TEXT,
    reason_code_3 TEXT,
    score_timestamp TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

### Columns

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| `transaction_id` | TEXT | NO | Transaction identifier (FK) | `txn_00000001` |
| `score` | REAL | NO | Fraud probability (0-1) | `0.85` |
| `risk_band` | TEXT | NO | Risk category | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `reason_code_1` | TEXT | YES | Top contributing feature | `user_txn_count_24h` |
| `reason_code_2` | TEXT | YES | 2nd contributing feature | `amount_zscore` |
| `reason_code_3` | TEXT | YES | 3rd contributing feature | `merchant_fraud_rate_30d` |
| `score_timestamp` | TEXT | NO | When score was computed | `2024-01-30T10:00:00` |

### Constraints

- **Primary Key**: `transaction_id`
- **Foreign Key**: `transaction_id` → `transactions(transaction_id)`
- **Check Constraints**:
  - `score >= 0 AND score <= 1`
  - `risk_band IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')`

### Indexes

```sql
CREATE INDEX idx_scores_transaction_id ON scores(transaction_id);
CREATE INDEX idx_scores_risk_band ON scores(risk_band);
CREATE INDEX idx_scores_score ON scores(score DESC);
```

**Index Usage**:
- `idx_scores_transaction_id`: Join with transactions
- `idx_scores_risk_band`: Filter by risk band
- `idx_scores_score`: Sort by score (review queue)

### Risk Band Thresholds

| Risk Band | Score Range | Expected % | Description |
|-----------|-------------|------------|-------------|
| `CRITICAL` | >= 0.9 | 0.5% | Highest risk, immediate review |
| `HIGH` | 0.7 - 0.9 | 1.5% | High risk, review if capacity |
| `MEDIUM` | 0.3 - 0.7 | 10% | Medium risk, monitor |
| `LOW` | < 0.3 | 88% | Low risk, auto-approve |

### Data Distribution

| Metric | Value |
|--------|-------|
| Total Rows | 100,000 |
| Mean Score | 0.15 |
| Median Score | 0.08 |
| P95 Score | 0.65 |
| P99 Score | 0.85 |

### Example Rows

```sql
SELECT * FROM scores LIMIT 3;
```

| transaction_id | score | risk_band | reason_code_1 | reason_code_2 | reason_code_3 | score_timestamp |
|----------------|-------|-----------|---------------|---------------|---------------|-----------------|
| txn_00000001 | 0.05 | LOW | hour_of_day | user_txn_count_24h | amount_zscore | 2024-01-30T10:00:00 |
| txn_00000002 | 0.12 | LOW | merchant_fraud_rate_30d | amount_zscore | hour_of_day | 2024-01-30T10:00:00 |
| txn_00000003 | 0.92 | CRITICAL | amount_zscore | user_txn_count_24h | merchant_fraud_rate_30d | 2024-01-30T10:00:00 |

---

## 5. review_queue Table

**Purpose**: Store transactions flagged for manual review with capacity constraints.

**Row Count**: ~2,000 (HIGH + CRITICAL transactions)

**Storage**: ~2 MB

### Schema

```sql
CREATE TABLE review_queue (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL,
    risk_band TEXT NOT NULL,
    queue_timestamp TEXT NOT NULL,
    capacity_exceeded INTEGER NOT NULL,
    review_status TEXT DEFAULT 'PENDING',
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

### Columns

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| `transaction_id` | TEXT | NO | Transaction identifier (FK) | `txn_00000003` |
| `score` | REAL | NO | Fraud probability (0-1) | `0.92` |
| `risk_band` | TEXT | NO | Risk category (HIGH or CRITICAL) | `CRITICAL`, `HIGH` |
| `queue_timestamp` | TEXT | NO | When added to queue | `2024-01-30T10:00:00` |
| `capacity_exceeded` | INTEGER | NO | 1 if beyond capacity, 0 otherwise | `0`, `1` |
| `review_status` | TEXT | NO | Review status | `PENDING`, `APPROVED`, `REJECTED` |

### Constraints

- **Primary Key**: `transaction_id`
- **Foreign Key**: `transaction_id` → `transactions(transaction_id)`
- **Check Constraints**:
  - `score >= 0 AND score <= 1`
  - `risk_band IN ('HIGH', 'CRITICAL')`
  - `capacity_exceeded IN (0, 1)`
  - `review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'AUTO_APPROVED')`

### Indexes

```sql
CREATE INDEX idx_review_queue_transaction_id ON review_queue(transaction_id);
CREATE INDEX idx_review_queue_capacity_exceeded ON review_queue(capacity_exceeded);
```

**Index Usage**:
- `idx_review_queue_transaction_id`: Join with transactions
- `idx_review_queue_capacity_exceeded`: Filter by capacity status

### Capacity Policy

| Metric | Value |
|--------|-------|
| Daily Capacity | 100 transactions |
| Selection Method | Top 100 by score |
| Overflow Policy | Auto-approve with flag |

### Data Distribution

| Metric | Value |
|--------|-------|
| Total Rows | ~2,000 |
| In Queue (capacity_exceeded=0) | 100 |
| Overflow (capacity_exceeded=1) | ~1,900 |
| Capacity Exceeded Rate | ~95% |

### Example Rows

```sql
SELECT * FROM review_queue LIMIT 3;
```

| transaction_id | score | risk_band | queue_timestamp | capacity_exceeded | review_status |
|----------------|-------|-----------|-----------------|-------------------|---------------|
| txn_00000003 | 0.92 | CRITICAL | 2024-01-30T10:00:00 | 0 | PENDING |
| txn_00000456 | 0.88 | HIGH | 2024-01-30T10:00:00 | 0 | PENDING |
| txn_00001234 | 0.75 | HIGH | 2024-01-30T10:00:00 | 1 | AUTO_APPROVED |

---

## 6. Table Relationships

### Entity-Relationship Diagram (Text)

```
transactions (1) ──< (1) labels
     │
     │ (1)
     │
     ├──< (1) features
     │
     │ (1)
     │
     ├──< (1) scores
     │
     │ (1)
     │
     └──< (0..1) review_queue
```

### Foreign Key Relationships

```sql
-- labels → transactions
ALTER TABLE labels 
ADD FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);

-- features → transactions
ALTER TABLE features 
ADD FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);

-- scores → transactions
ALTER TABLE scores 
ADD FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);

-- review_queue → transactions
ALTER TABLE review_queue 
ADD FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);
```

### Join Patterns

**Full Transaction View**:
```sql
SELECT 
    t.transaction_id,
    t.user_id,
    t.merchant_id,
    t.amount,
    t.timestamp,
    t.category,
    l.is_fraud,
    l.label_timestamp,
    l.delay_days,
    f.user_txn_count_24h,
    f.user_amount_sum_7d,
    f.merchant_fraud_rate_30d,
    f.amount_zscore,
    f.hour_of_day,
    f.is_first_merchant,
    s.score,
    s.risk_band,
    s.reason_code_1,
    rq.review_status
FROM transactions t
LEFT JOIN labels l ON t.transaction_id = l.transaction_id
LEFT JOIN features f ON t.transaction_id = f.transaction_id
LEFT JOIN scores s ON t.transaction_id = s.transaction_id
LEFT JOIN review_queue rq ON t.transaction_id = rq.transaction_id;
```

---

## 7. Event-Time Correctness Rules

### Rule 1: Label Timestamp After Transaction

**Constraint**: Labels must arrive after transaction time.

```sql
-- Validation query
SELECT COUNT(*) as violations
FROM labels l
JOIN transactions t ON l.transaction_id = t.transaction_id
WHERE l.label_timestamp <= t.timestamp;
-- Expected: 0 violations
```

### Rule 2: Feature Timestamp At Or Before Transaction

**Constraint**: Features must use only data available at transaction time.

```sql
-- Validation query (leakage check)
SELECT COUNT(*) as violations
FROM features f
JOIN transactions t ON f.transaction_id = t.transaction_id
WHERE f.feature_timestamp > t.timestamp;
-- Expected: 0 violations
```

### Rule 3: Mature Label Filter

**Constraint**: Training must use only transactions with mature labels (>7 days old).

```sql
-- Mature transactions query
SELECT 
    t.transaction_id,
    t.timestamp,
    l.is_fraud,
    f.*
FROM transactions t
JOIN labels l ON t.transaction_id = l.transaction_id
JOIN features f ON t.transaction_id = f.transaction_id
WHERE julianday('now') - julianday(t.timestamp) > 7;
```

### Rule 4: Feature Computation Uses Past Data Only

**Constraint**: All feature queries must use `timestamp < transaction_timestamp`.

```sql
-- Example: User velocity feature (CORRECT)
SELECT COUNT(*) as user_txn_count_24h
FROM transactions
WHERE user_id = ?
  AND timestamp < ?  -- CRITICAL: Use < not <=
  AND timestamp >= datetime(?, '-1 day');

-- Example: User velocity feature (WRONG - LEAKAGE!)
SELECT COUNT(*) as user_txn_count_24h
FROM transactions
WHERE user_id = ?
  AND timestamp <= ?  -- WRONG: Includes current transaction
  AND timestamp >= datetime(?, '-1 day');
```

---

## 8. Example Queries

### Query 1: Transaction Statistics

```sql
SELECT 
    COUNT(*) as total_transactions,
    SUM(is_fraud) as fraud_count,
    AVG(is_fraud) as fraud_rate,
    AVG(amount) as avg_amount,
    MIN(timestamp) as start_date,
    MAX(timestamp) as end_date
FROM transactions;
```

**Expected Output**:
```
total_transactions: 100000
fraud_count: 2000
fraud_rate: 0.02
avg_amount: 125.50
start_date: 2024-01-01T00:00:00
end_date: 2024-01-30T23:59:59
```

### Query 2: Label Delay Analysis

```sql
SELECT 
    AVG(delay_days) as mean_delay,
    MIN(delay_days) as min_delay,
    MAX(delay_days) as max_delay,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delay_days) as median_delay,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_days) as p95_delay
FROM labels;
```

**Expected Output**:
```
mean_delay: 5.0
min_delay: 3.0
max_delay: 7.0
median_delay: 5.0
p95_delay: 6.8
```

### Query 3: Feature Statistics

```sql
SELECT 
    AVG(user_txn_count_24h) as avg_user_txn_24h,
    AVG(user_amount_sum_7d) as avg_user_amount_7d,
    AVG(merchant_fraud_rate_30d) as avg_merchant_fraud_rate,
    AVG(amount_zscore) as avg_amount_zscore
FROM features;
```

**Expected Output**:
```
avg_user_txn_24h: 2.5
avg_user_amount_7d: 350.0
avg_merchant_fraud_rate: 0.02
avg_amount_zscore: 0.0
```

### Query 4: Risk Band Distribution

```sql
SELECT 
    risk_band,
    COUNT(*) as count,
    AVG(score) as avg_score,
    MIN(score) as min_score,
    MAX(score) as max_score
FROM scores
GROUP BY risk_band
ORDER BY 
    CASE risk_band
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**Expected Output**:
```
risk_band  | count | avg_score | min_score | max_score
-----------|-------|-----------|-----------|----------
CRITICAL   | 500   | 0.92      | 0.90      | 0.99
HIGH       | 1500  | 0.78      | 0.70      | 0.89
MEDIUM     | 10000 | 0.45      | 0.30      | 0.69
LOW        | 88000 | 0.10      | 0.00      | 0.29
```

### Query 5: Review Queue Status

```sql
SELECT 
    capacity_exceeded,
    COUNT(*) as count,
    AVG(score) as avg_score,
    COUNT(CASE WHEN review_status = 'PENDING' THEN 1 END) as pending,
    COUNT(CASE WHEN review_status = 'APPROVED' THEN 1 END) as approved,
    COUNT(CASE WHEN review_status = 'REJECTED' THEN 1 END) as rejected
FROM review_queue
GROUP BY capacity_exceeded;
```

**Expected Output**:
```
capacity_exceeded | count | avg_score | pending | approved | rejected
------------------|-------|-----------|---------|----------|----------
0                 | 100   | 0.88      | 100     | 0        | 0
1                 | 1900  | 0.75      | 0       | 1900     | 0
```

### Query 6: Fraud Detection Performance

```sql
SELECT 
    s.risk_band,
    COUNT(*) as total,
    SUM(t.is_fraud) as fraud_count,
    AVG(t.is_fraud) as precision
FROM scores s
JOIN transactions t ON s.transaction_id = t.transaction_id
GROUP BY s.risk_band
ORDER BY 
    CASE s.risk_band
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**Expected Output**:
```
risk_band  | total | fraud_count | precision
-----------|-------|-------------|----------
CRITICAL   | 500   | 150         | 0.30
HIGH       | 1500  | 180         | 0.12
MEDIUM     | 10000 | 500         | 0.05
LOW        | 88000 | 1170        | 0.01
```

### Query 7: Top Fraudulent Transactions

```sql
SELECT 
    t.transaction_id,
    t.user_id,
    t.merchant_id,
    t.amount,
    t.timestamp,
    s.score,
    s.risk_band,
    s.reason_code_1,
    s.reason_code_2,
    s.reason_code_3
FROM transactions t
JOIN scores s ON t.transaction_id = s.transaction_id
WHERE t.is_fraud = 1
ORDER BY s.score DESC
LIMIT 10;
```

### Query 8: Leakage Check (Critical)

```sql
-- Check for features using future data
SELECT 
    f.transaction_id,
    t.timestamp as transaction_time,
    f.feature_timestamp,
    julianday(f.feature_timestamp) - julianday(t.timestamp) as time_diff_days
FROM features f
JOIN transactions t ON f.transaction_id = t.transaction_id
WHERE f.feature_timestamp > t.timestamp;
-- Expected: 0 rows (no leakage)
```

### Query 9: Maturity Analysis

```sql
-- Check how many transactions have mature labels
SELECT 
    COUNT(*) as total_transactions,
    SUM(CASE WHEN julianday('now') - julianday(t.timestamp) > 7 THEN 1 ELSE 0 END) as mature_transactions,
    AVG(CASE WHEN julianday('now') - julianday(t.timestamp) > 7 THEN 1 ELSE 0 END) as maturity_rate
FROM transactions t
JOIN labels l ON t.transaction_id = l.transaction_id;
```

**Expected Output**:
```
total_transactions: 100000
mature_transactions: 93000
maturity_rate: 0.93
```

### Query 10: User Fraud Pattern

```sql
-- Find users with highest fraud rate
SELECT 
    t.user_id,
    COUNT(*) as total_txns,
    SUM(t.is_fraud) as fraud_txns,
    AVG(t.is_fraud) as fraud_rate,
    AVG(t.amount) as avg_amount
FROM transactions t
GROUP BY t.user_id
HAVING COUNT(*) >= 10
ORDER BY fraud_rate DESC, total_txns DESC
LIMIT 10;
```

---

## 9. Performance Optimization

### Index Strategy

**Principle**: Index columns used in WHERE, JOIN, and ORDER BY clauses.

**Indexes Created**:
1. `idx_transactions_timestamp`: Temporal queries
2. `idx_transactions_user_id`: User aggregations
3. `idx_transactions_merchant_id`: Merchant aggregations
4. `idx_labels_label_timestamp`: Label monitoring
5. `idx_features_feature_timestamp`: Leakage checking
6. `idx_scores_risk_band`: Risk filtering
7. `idx_scores_score`: Review queue sorting

### Query Optimization Tips

1. **Use indexes**: Ensure WHERE clauses use indexed columns
2. **Limit results**: Use LIMIT for large result sets
3. **Avoid SELECT ***: Select only needed columns
4. **Use EXPLAIN**: Analyze query plans
5. **Batch inserts**: Use transactions for bulk inserts

### Example: Optimized Feature Query

```sql
-- Slow (no index)
SELECT COUNT(*) 
FROM transactions 
WHERE user_id = 'user_00123' 
  AND timestamp < '2024-01-15T10:00:00';

-- Fast (uses idx_transactions_user_id and idx_transactions_timestamp)
SELECT COUNT(*) 
FROM transactions 
WHERE user_id = 'user_00123' 
  AND timestamp < '2024-01-15T10:00:00';
```

---

## 10. Backup and Recovery

### Backup Strategy

```bash
# Backup database
cp data/fraud_risk.db data/fraud_risk_backup_$(date +%Y%m%d).db

# Backup with compression
sqlite3 data/fraud_risk.db ".backup data/fraud_risk_backup.db"
gzip data/fraud_risk_backup.db
```

### Recovery Strategy

```bash
# Restore from backup
cp data/fraud_risk_backup_20240115.db data/fraud_risk.db

# Restore from compressed backup
gunzip data/fraud_risk_backup.db.gz
cp data/fraud_risk_backup.db data/fraud_risk.db
```

---

## 11. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-13 | System | Initial schema specification |
