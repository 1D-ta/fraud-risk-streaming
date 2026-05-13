PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('retail', 'food', 'travel', 'entertainment', 'other')),
    is_fraud INTEGER CHECK (is_fraud IN (0, 1) OR is_fraud IS NULL)
);

CREATE TABLE IF NOT EXISTS labels (
    transaction_id TEXT PRIMARY KEY,
    is_fraud INTEGER NOT NULL CHECK (is_fraud IN (0, 1)),
    label_timestamp TEXT NOT NULL,
    delay_days REAL NOT NULL CHECK (delay_days >= 3.0 AND delay_days <= 7.0),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS features (
    transaction_id TEXT PRIMARY KEY,
    feature_timestamp TEXT NOT NULL,
    user_txn_count_24h INTEGER NOT NULL CHECK (user_txn_count_24h >= 0),
    user_amount_sum_7d REAL NOT NULL CHECK (user_amount_sum_7d >= 0),
    merchant_fraud_rate_30d REAL NOT NULL CHECK (merchant_fraud_rate_30d >= 0 AND merchant_fraud_rate_30d <= 1),
    amount_zscore REAL NOT NULL,
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    is_first_merchant INTEGER NOT NULL CHECK (is_first_merchant IN (0, 1)),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS scores (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    risk_band TEXT NOT NULL CHECK (risk_band IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    reason_code_1 TEXT,
    reason_code_2 TEXT,
    reason_code_3 TEXT,
    score_timestamp TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS review_queue (
    transaction_id TEXT PRIMARY KEY,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    risk_band TEXT NOT NULL CHECK (risk_band IN ('HIGH', 'CRITICAL')),
    queue_timestamp TEXT NOT NULL,
    capacity_exceeded INTEGER NOT NULL CHECK (capacity_exceeded IN (0, 1)),
    review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'AUTO_APPROVED')),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON transactions(merchant_id);

CREATE INDEX IF NOT EXISTS idx_labels_label_timestamp ON labels(label_timestamp);
CREATE INDEX IF NOT EXISTS idx_labels_transaction_id ON labels(transaction_id);

CREATE INDEX IF NOT EXISTS idx_features_transaction_id ON features(transaction_id);
CREATE INDEX IF NOT EXISTS idx_features_feature_timestamp ON features(feature_timestamp);

CREATE INDEX IF NOT EXISTS idx_scores_transaction_id ON scores(transaction_id);
CREATE INDEX IF NOT EXISTS idx_scores_risk_band ON scores(risk_band);
CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score DESC);

CREATE INDEX IF NOT EXISTS idx_review_queue_transaction_id ON review_queue(transaction_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_capacity_exceeded ON review_queue(capacity_exceeded);
