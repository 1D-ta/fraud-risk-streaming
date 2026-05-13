"""Build event-time-correct fraud features from transactions and delayed labels."""

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


FEATURE_COLUMNS = [
    "user_txn_count_24h",
    "user_amount_sum_7d",
    "merchant_fraud_rate_30d",
    "amount_zscore",
    "hour_of_day",
    "is_first_merchant",
]


def _ensure_features_table(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(
        """
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
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_features_transaction_id ON features(transaction_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_features_feature_timestamp ON features(feature_timestamp)")


def _trim_window(window: Deque[Tuple[datetime, float]], cutoff: datetime) -> None:
    while window and window[0][0] < cutoff:
        window.popleft()


def _trim_label_window(window: Deque[Tuple[datetime, int]], cutoff: datetime) -> None:
    while window and window[0][0] < cutoff:
        window.popleft()


def build_features(db_path: str = "data/fraud_risk.db") -> dict:
    """Build event-time-safe features and persist them to SQLite."""

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _ensure_features_table(connection)

        transactions = pd.read_sql_query(
            """
            SELECT transaction_id, user_id, merchant_id, amount, timestamp, category, is_fraud
            FROM transactions
            ORDER BY timestamp, transaction_id
            """,
            connection,
            parse_dates={"timestamp": {"format": "%Y-%m-%dT%H:%M:%S"}},
        )
        labels = pd.read_sql_query(
            """
            SELECT transaction_id, is_fraud, label_timestamp
            FROM labels
            ORDER BY label_timestamp, transaction_id
            """,
            connection,
            parse_dates={"label_timestamp": {"format": "%Y-%m-%dT%H:%M:%S"}},
        )

        if transactions.empty:
            raise ValueError("No transactions found. Run the transaction generator first.")
        if labels.empty:
            raise ValueError("No labels found. Run delayed label generation first.")

        transaction_lookup = {
            row.transaction_id: {
                "user_id": row.user_id,
                "merchant_id": row.merchant_id,
                "timestamp": row.timestamp.to_pydatetime(),
            }
            for row in transactions.itertuples(index=False)
        }

        user_24h: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(deque)
        user_7d: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(deque)
        user_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "sum": 0.0, "sum_sq": 0.0})
        user_seen_merchants: Dict[str, set] = defaultdict(set)
        merchant_label_history: Dict[str, Deque[Tuple[datetime, int]]] = defaultdict(deque)

        label_pointer = 0
        feature_rows: List[dict] = []

        for row in transactions.itertuples(index=False):
            current_timestamp: datetime = row.timestamp.to_pydatetime()

            while label_pointer < len(labels) and labels.iloc[label_pointer]["label_timestamp"].to_pydatetime() <= current_timestamp:
                label_row = labels.iloc[label_pointer]
                label_pointer += 1
                transaction_info = transaction_lookup[label_row["transaction_id"]]
                merchant_id = transaction_info["merchant_id"]
                transaction_timestamp = transaction_info["timestamp"]
                merchant_label_history[merchant_id].append((transaction_timestamp, int(label_row["is_fraud"])))

            user_id = row.user_id
            merchant_id = row.merchant_id
            amount = float(row.amount)

            recent_24h = user_24h[user_id]
            recent_7d = user_7d[user_id]

            _trim_window(recent_24h, current_timestamp - timedelta(hours=24))
            _trim_window(recent_7d, current_timestamp - timedelta(days=7))

            user_txn_count_24h = len(recent_24h)
            user_amount_sum_7d = sum(value for _, value in recent_7d)
            is_first_merchant = 1 if merchant_id not in user_seen_merchants[user_id] else 0

            stats = user_stats[user_id]
            if stats["count"] >= 2 and stats["sum_sq"] > 0:
                mean_amount = stats["sum"] / stats["count"]
                variance = max((stats["sum_sq"] / stats["count"]) - (mean_amount ** 2), 0.0)
                std_amount = variance ** 0.5
                amount_zscore = 0.0 if std_amount == 0 else (amount - mean_amount) / std_amount
            else:
                amount_zscore = 0.0

            label_window = merchant_label_history[merchant_id]
            _trim_label_window(label_window, current_timestamp - timedelta(days=30))
            merchant_fraud_rate_30d = (
                sum(is_fraud for _, is_fraud in label_window) / len(label_window)
                if label_window
                else 0.0
            )

            feature_rows.append(
                {
                    "transaction_id": row.transaction_id,
                    "feature_timestamp": current_timestamp.replace(microsecond=0).isoformat(),
                    "user_txn_count_24h": int(user_txn_count_24h),
                    "user_amount_sum_7d": float(user_amount_sum_7d),
                    "merchant_fraud_rate_30d": float(merchant_fraud_rate_30d),
                    "amount_zscore": float(amount_zscore),
                    "hour_of_day": int(current_timestamp.hour),
                    "is_first_merchant": int(is_first_merchant),
                }
            )

            recent_24h.append((current_timestamp, amount))
            recent_7d.append((current_timestamp, amount))
            user_seen_merchants[user_id].add(merchant_id)
            stats["count"] += 1.0
            stats["sum"] += amount
            stats["sum_sq"] += amount * amount

        features_df = pd.DataFrame(feature_rows)
        connection.execute("DELETE FROM features")
        features_df.to_sql("features", connection, if_exists="append", index=False)

    report = {
        "n_features": int(len(features_df)),
        "feature_stats": {
            column: {
                "mean": float(features_df[column].mean()),
                "std": float(features_df[column].std()),
                "min": float(features_df[column].min()),
                "max": float(features_df[column].max()),
            }
            for column in FEATURE_COLUMNS
        },
    }

    report_path = Path("artifacts/reports/feature_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Built features for {len(features_df):,} transactions")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build event-time-safe fraud features.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_features(db_path=args.db_path)


if __name__ == "__main__":
    main()
