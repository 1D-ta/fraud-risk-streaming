# SQLite Schema Specification: Fraud Risk Streaming

This document describes the live SQLite schema used by the restored implementation in `data/schemas/schema.sql`.

## Overview

- Database: `data/fraud_risk.db`
- Tables: 5
- Indexes: 16
- Design goal: support delayed labels, event-time-safe features, scoring, and capacity-constrained review routing

## 1. `transactions`

Stores the synthetic transaction stream.

```sql
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL,
    merchant_category TEXT NOT NULL CHECK (merchant_category IN ('retail', 'food', 'travel', 'entertainment', 'other')),
    channel TEXT NOT NULL CHECK (channel IN ('mobile', 'web', 'atm', 'phone')),
    location_city TEXT NOT NULL,
    is_international INTEGER NOT NULL CHECK (is_international IN (0, 1)),
    fraud_pattern TEXT
);
```

Columns:
- `transaction_id`: primary key
- `user_id`: user identifier
- `merchant_id`: merchant identifier
- `device_id`: device identifier used for device velocity features
- `timestamp`: event time in ISO 8601 format
- `amount`: transaction amount
- `currency`: transaction currency
- `merchant_category`: normalized category label
- `channel`: payment channel
- `location_city`: transaction city
- `is_international`: domestic/international flag
- `fraud_pattern`: synthetic fraud tag used by the simulator

Indexes:
- `idx_transactions_timestamp`
- `idx_transactions_user_id`
- `idx_transactions_merchant_id`
- `idx_transactions_device_id`

## 2. `labels`

Stores delayed fraud labels with maturity tracking.

```sql
CREATE TABLE labels (
    transaction_id TEXT PRIMARY KEY,
    label_timestamp TEXT NOT NULL,
    is_fraud INTEGER NOT NULL CHECK (is_fraud IN (0, 1)),
    label_source TEXT NOT NULL,
    label_delay_hours REAL NOT NULL,
    is_mature INTEGER NOT NULL CHECK (is_mature IN (0, 1)),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

Columns:
- `transaction_id`: foreign key to `transactions`
- `label_timestamp`: time the label arrived
- `is_fraud`: binary label
- `label_source`: `chargeback`, `manual_review`, or `model_approved`
- `label_delay_hours`: delay between transaction and label arrival
- `is_mature`: flag used to filter training rows

Indexes:
- `idx_labels_label_timestamp`
- `idx_labels_transaction_id`
- `idx_labels_is_mature`

## 3. `features`

Stores the 13 event-time-safe features used by training and scoring.

```sql
CREATE TABLE features (
    transaction_id TEXT PRIMARY KEY,
    feature_timestamp TEXT NOT NULL,
    user_txn_count_1h INTEGER NOT NULL CHECK (user_txn_count_1h >= 0),
    user_txn_count_24h INTEGER NOT NULL CHECK (user_txn_count_24h >= 0),
    user_avg_amount_7d REAL NOT NULL CHECK (user_avg_amount_7d >= 0),
    user_amount_zscore_7d REAL NOT NULL,
    user_unique_merchants_24h INTEGER NOT NULL CHECK (user_unique_merchants_24h >= 0),
    merchant_txn_count_1h INTEGER NOT NULL CHECK (merchant_txn_count_1h >= 0),
    device_user_count_24h INTEGER NOT NULL CHECK (device_user_count_24h >= 0),
    is_new_device_for_user INTEGER NOT NULL CHECK (is_new_device_for_user IN (0, 1)),
    city_change_flag_24h INTEGER NOT NULL CHECK (city_change_flag_24h IN (0, 1)),
    amount REAL NOT NULL CHECK (amount > 0),
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    is_international INTEGER NOT NULL CHECK (is_international IN (0, 1)),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

Indexes:
- `idx_features_transaction_id`
- `idx_features_feature_timestamp`

## 4. `scores`

Stores model output, risk banding, decisioning, and reason codes.

```sql
CREATE TABLE scores (
    transaction_id TEXT PRIMARY KEY,
    score_timestamp TEXT NOT NULL,
    fraud_score REAL NOT NULL CHECK (fraud_score >= 0 AND fraud_score <= 1),
    risk_band TEXT NOT NULL CHECK (risk_band IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    decision TEXT NOT NULL CHECK (decision IN ('manual_review', 'approve', 'monitor')),
    reason_codes TEXT NOT NULL,
    model_version TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

Indexes:
- `idx_scores_transaction_id`
- `idx_scores_risk_band`
- `idx_scores_score`
- `idx_scores_model_version`

## 5. `review_queue`

Stores the capacity-limited manual review batch.

```sql
CREATE TABLE review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    review_batch_id TEXT NOT NULL,
    fraud_score REAL NOT NULL CHECK (fraud_score >= 0 AND fraud_score <= 1),
    review_rank INTEGER NOT NULL CHECK (review_rank >= 0),
    decision TEXT NOT NULL,
    capacity_limit INTEGER NOT NULL CHECK (capacity_limit > 0),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
```

Indexes:
- `idx_review_queue_transaction_id`
- `idx_review_queue_batch_id`
- `idx_review_queue_rank`

## Event-Time Rules

- Features are computed using only data at or before the transaction timestamp.
- Labels are delayed and tracked separately so training can filter immature data.
- Scoring writes a single immutable row per transaction with the chosen model version.
- Review queue rows are ranked by `fraud_score` within a batch and constrained by capacity.

## Summary

The restored implementation intentionally uses a richer transaction schema and a 13-feature event-time model so the repository matches the original fraud-risk streaming plan rather than the simplified MVP variant.
