PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transactions (
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

CREATE TABLE IF NOT EXISTS labels (
    transaction_id TEXT PRIMARY KEY,
    label_timestamp TEXT NOT NULL,
    is_fraud INTEGER NOT NULL CHECK (is_fraud IN (0, 1)),
    label_source TEXT NOT NULL,
    label_delay_hours REAL NOT NULL,
    is_mature INTEGER NOT NULL CHECK (is_mature IN (0, 1)),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS features (
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

CREATE TABLE IF NOT EXISTS scores (
    transaction_id TEXT PRIMARY KEY,
    score_timestamp TEXT NOT NULL,
    fraud_score REAL NOT NULL CHECK (fraud_score >= 0 AND fraud_score <= 1),
    risk_band TEXT NOT NULL CHECK (risk_band IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    decision TEXT NOT NULL CHECK (decision IN ('manual_review', 'approve', 'monitor')),
    reason_codes TEXT NOT NULL,
    model_version TEXT NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    review_batch_id TEXT NOT NULL,
    fraud_score REAL NOT NULL CHECK (fraud_score >= 0 AND fraud_score <= 1),
    review_rank INTEGER NOT NULL CHECK (review_rank >= 0),
    decision TEXT NOT NULL,
    capacity_limit INTEGER NOT NULL CHECK (capacity_limit > 0),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON transactions(merchant_id);
CREATE INDEX IF NOT EXISTS idx_transactions_device_id ON transactions(device_id);

CREATE INDEX IF NOT EXISTS idx_labels_label_timestamp ON labels(label_timestamp);
CREATE INDEX IF NOT EXISTS idx_labels_transaction_id ON labels(transaction_id);
CREATE INDEX IF NOT EXISTS idx_labels_is_mature ON labels(is_mature);

CREATE INDEX IF NOT EXISTS idx_features_transaction_id ON features(transaction_id);
CREATE INDEX IF NOT EXISTS idx_features_feature_timestamp ON features(feature_timestamp);

CREATE INDEX IF NOT EXISTS idx_scores_transaction_id ON scores(transaction_id);
CREATE INDEX IF NOT EXISTS idx_scores_risk_band ON scores(risk_band);
CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(fraud_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_model_version ON scores(model_version);

CREATE INDEX IF NOT EXISTS idx_review_queue_transaction_id ON review_queue(transaction_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_batch_id ON review_queue(review_batch_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_rank ON review_queue(review_rank);
