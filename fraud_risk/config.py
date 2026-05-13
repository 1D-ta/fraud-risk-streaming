"""Centralized configuration for the fraud-risk-streaming system."""

from __future__ import annotations

import os
from pathlib import Path

# Database configuration
DB_PATH = os.getenv("FRAUD_DB_PATH", "data/fraud_risk.db")
DB_DIR = Path(DB_PATH).parent
DB_DIR.mkdir(parents=True, exist_ok=True)

# Label maturity configuration
MATURE_LABEL_AGE_DAYS = 7

# Model metadata
MODEL_VERSION = "production_model_v1"

# Feature window configurations (in seconds)
FEATURE_WINDOWS = {
    "user_txn_1h": 3600,
    "user_txn_24h": 86400,
    "user_amount_7d": 7 * 86400,
    "merchant_txn_1h": 3600,
    "merchant_fraud_rate_30d": 30 * 86400,
    "device_user_count_24h": 86400,
    "city_change_24h": 86400,
}

# Feature columns (13 mandatory from plan)
FEATURE_COLUMNS = [
    "user_txn_count_1h",
    "user_txn_count_24h",
    "user_avg_amount_7d",
    "user_amount_zscore_7d",
    "user_unique_merchants_24h",
    "merchant_txn_count_1h",
    "device_user_count_24h",
    "is_new_device_for_user",
    "city_change_flag_24h",
    "amount",
    "hour_of_day",
    "is_weekend",
    "is_international",
]

# Risk band thresholds
RISK_THRESHOLDS = {
    "CRITICAL": 0.85,
    "HIGH": 0.65,
    "MEDIUM": 0.35,
}

SCORE_DECISIONS = {
    "CRITICAL": "manual_review",
    "HIGH": "manual_review",
    "MEDIUM": "monitor",
    "LOW": "approve",
}

# Review queue configuration
REVIEW_CAPACITY = 500
TOP_K_REVIEW = 100

# Model configuration
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15

# Paths
ARTIFACTS_DIR = Path("artifacts")
MODELS_DIR = ARTIFACTS_DIR / "models"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Model files
PRODUCTION_MODEL_PATH = MODELS_DIR / "production_model.pkl"
LOGISTIC_REGRESSION_PATH = MODELS_DIR / "logistic_regression.pkl"
GRADIENT_BOOSTING_PATH = MODELS_DIR / "gradient_boosting.pkl"

# Simulation configuration
DEFAULT_NUM_TRANSACTIONS = 100000
DEFAULT_FRAUD_RATE = 0.02
DEFAULT_NUM_USERS = 10000
DEFAULT_NUM_MERCHANTS = 2000
DEFAULT_NUM_DEVICES = 5000
DEFAULT_CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Miami"]
DEFAULT_CHANNELS = ["mobile", "web", "atm", "phone"]
DEFAULT_CATEGORIES = ["retail", "food", "travel", "entertainment", "other"]
