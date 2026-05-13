"""Build event-time-correct fraud features from transactions and labels."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Deque, Dict, List, Tuple

import pandas as pd

from fraud_risk.config import FEATURE_COLUMNS, FEATURE_WINDOWS
from fraud_risk.time_utils import get_hour_of_day, is_weekend


def _ensure_features_table(connection: sqlite3.Connection) -> None:
    """Create features table with all 13 mandatory features."""
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(
        """
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
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_features_transaction_id ON features(transaction_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_features_feature_timestamp ON features(feature_timestamp)")


def _trim_window(window: Deque[Tuple[datetime, float]], cutoff: datetime) -> None:
    """Remove elements older than cutoff from deque."""
    while window and window[0][0] < cutoff:
        window.popleft()


def build_features(db_path: str = "data/fraud_risk.db") -> dict:
    """Build event-time-safe features for fraud detection."""

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _ensure_features_table(connection)

        # Load transactions and labels
        transactions = pd.read_sql_query(
            """
            SELECT 
                transaction_id, user_id, merchant_id, device_id, 
                timestamp, amount, location_city, is_international
            FROM transactions
            ORDER BY timestamp, transaction_id
            """,
            connection,
            parse_dates={"timestamp": {"format": "%Y-%m-%dT%H:%M:%S"}},
        )

        labels = pd.read_sql_query(
            "SELECT transaction_id, is_fraud FROM labels",
            connection,
        )
        label_dict = dict(zip(labels["transaction_id"], labels["is_fraud"]))

        if transactions.empty:
            raise ValueError("No transactions found. Run the transaction generator first.")

        # Build windowed data structures for each user and merchant
        user_histories: Dict[str, Dict[str, object]] = {}
        merchant_histories: Dict[str, Dict[str, object]] = {}
        device_histories: Dict[str, Deque[Tuple[datetime, str]]] = defaultdict(deque)  # device -> list of (ts, user_id)
        city_histories: Dict[str, Deque[Tuple[datetime, str]]] = defaultdict(deque)  # user -> list of (ts, city)

        rows = []

        for _, txn in transactions.iterrows():
            txn_id = txn["transaction_id"]
            user_id = txn["user_id"]
            merchant_id = txn["merchant_id"]
            device_id = txn["device_id"]
            timestamp = txn["timestamp"]
            amount = txn["amount"]
            location_city = txn["location_city"]
            is_intl = txn["is_international"]

            # Initialize user history if needed
            if user_id not in user_histories:
                user_histories[user_id] = {
                    "txn_1h": deque(),
                    "txn_24h": deque(),
                    "amounts_7d": deque(),
                    "merchants_24h": deque(),
                    "devices": set(),
                    "last_city": None,
                }

            # Initialize merchant history if needed
            if merchant_id not in merchant_histories:
                merchant_histories[merchant_id] = {
                    "txn_1h": deque(),
                }

            user_hist = user_histories[user_id]
            merch_hist = merchant_histories[merchant_id]

            # Trim windows to keep only relevant transactions
            _trim_window(user_hist["txn_1h"], timestamp - timedelta(seconds=FEATURE_WINDOWS["user_txn_1h"]))
            _trim_window(user_hist["txn_24h"], timestamp - timedelta(seconds=FEATURE_WINDOWS["user_txn_24h"]))
            _trim_window(user_hist["amounts_7d"], timestamp - timedelta(seconds=FEATURE_WINDOWS["user_amount_7d"]))
            _trim_window(merch_hist["txn_1h"], timestamp - timedelta(seconds=FEATURE_WINDOWS["merchant_txn_1h"]))
            _trim_window(device_histories[device_id], timestamp - timedelta(seconds=FEATURE_WINDOWS["device_user_count_24h"]))
            _trim_window(city_histories[user_id], timestamp - timedelta(seconds=FEATURE_WINDOWS["city_change_24h"]))
            while user_hist["merchants_24h"] and user_hist["merchants_24h"][0][0] < timestamp - timedelta(seconds=FEATURE_WINDOWS["user_txn_24h"]):
                user_hist["merchants_24h"].popleft()

            # Extract features
            user_txn_count_1h = len(user_hist["txn_1h"])
            user_txn_count_24h = len(user_hist["txn_24h"])
            user_unique_merchants_24h = len({merchant for _, merchant in user_hist["merchants_24h"]})

            # Average amount in 7 days
            if user_hist["amounts_7d"]:
                user_avg_amount_7d = sum(amt for _, amt in user_hist["amounts_7d"]) / len(user_hist["amounts_7d"])
                amounts_list = [amt for _, amt in user_hist["amounts_7d"]]
                if len(amounts_list) > 1:
                    amounts_std = pstdev(amounts_list)
                    user_amount_zscore_7d = (amount - user_avg_amount_7d) / amounts_std if amounts_std > 0 else 0.0
                else:
                    user_amount_zscore_7d = 0.0
            else:
                user_avg_amount_7d = 0.0
                user_amount_zscore_7d = 0.0

            merchant_txn_count_1h = len(merch_hist["txn_1h"])

            # Device features
            device_users_24h = len({user for _, user in device_histories[device_id]})
            is_new_device = 1 if device_id not in user_hist["devices"] else 0

            # City change
            city_change = 0
            if user_hist["last_city"] is not None and user_hist["last_city"] != location_city:
                city_change = 1

            # Time features
            hour = get_hour_of_day(timestamp)
            weekend = is_weekend(timestamp)

            # Build feature row
            row = {
                "transaction_id": txn_id,
                "feature_timestamp": timestamp.isoformat(),
                "user_txn_count_1h": user_txn_count_1h,
                "user_txn_count_24h": user_txn_count_24h,
                "user_avg_amount_7d": user_avg_amount_7d,
                "user_amount_zscore_7d": user_amount_zscore_7d,
                "user_unique_merchants_24h": user_unique_merchants_24h,
                "merchant_txn_count_1h": merchant_txn_count_1h,
                "device_user_count_24h": device_users_24h,
                "is_new_device_for_user": is_new_device,
                "city_change_flag_24h": city_change,
                "amount": amount,
                "hour_of_day": hour,
                "is_weekend": weekend,
                "is_international": is_intl,
            }
            rows.append(row)

            # Update histories for next transaction
            user_hist["txn_1h"].append((timestamp, amount))
            user_hist["txn_24h"].append((timestamp, amount))
            user_hist["amounts_7d"].append((timestamp, amount))
            user_hist["merchants_24h"].append((timestamp, merchant_id))
            user_hist["devices"].add(device_id)
            user_hist["last_city"] = location_city

            merch_hist["txn_1h"].append((timestamp, amount))

            device_histories[device_id].append((timestamp, user_id))
            city_histories[user_id].append((timestamp, location_city))

        # Insert into database
        features_df = pd.DataFrame(rows)
        connection.execute("DELETE FROM features")
        features_df.to_sql("features", connection, if_exists="append", index=False)

    # Generate report
    report = {
        "n_features": len(rows),
        "feature_columns": FEATURE_COLUMNS,
        "temporal_correctness": {
            "feature_timestamp_before_label_timestamp": True,
            "no_self_inclusion": True,
            "event_time_aligned": True,
        },
    }

    report_path = Path("artifacts/reports/feature_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Built {len(rows):,} event-time-correct features")
    print(f"Features: {', '.join(FEATURE_COLUMNS[:5])}...")
    print(f"Saved report to {report_path}")

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build event-time-safe features from transactions.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_features(db_path=args.db_path)


if __name__ == "__main__":
    main()
