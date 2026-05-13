"""Generate delayed fraud labels for the transaction stream."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from fraud_risk.config import MATURE_LABEL_AGE_DAYS
from fraud_risk.time_utils import days_between


def _ensure_labels_table(connection: sqlite3.Connection) -> None:
    """Ensure labels table exists with full schema."""
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            transaction_id TEXT PRIMARY KEY,
            label_timestamp TEXT NOT NULL,
            is_fraud INTEGER NOT NULL CHECK (is_fraud IN (0, 1)),
            label_source TEXT NOT NULL,
            label_delay_hours REAL NOT NULL,
            is_mature INTEGER NOT NULL CHECK (is_mature IN (0, 1)),
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_labels_label_timestamp ON labels(label_timestamp)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_labels_transaction_id ON labels(transaction_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_labels_is_mature ON labels(is_mature)")


def _determine_label_source(rng: random.Random, is_fraud: int) -> str:
    """Randomly determine label source based on fraud status."""
    if is_fraud:
        # Fraud is confirmed through chargeback or manual review
        return rng.choice(["chargeback", "manual_review"])
    else:
        # Non-fraud is confirmed through various sources
        return rng.choice(["manual_review", "model_approved"])


def generate_labels(db_path: str = "data/fraud_risk.db", seed: int = 42) -> dict:
    """Populate the labels table with delayed confirmations and mature flags."""

    rng_numpy = np.random.default_rng(seed)
    rng = random.Random(seed)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _ensure_labels_table(connection)

        transactions = pd.read_sql_query(
            "SELECT transaction_id, timestamp, fraud_pattern FROM transactions ORDER BY timestamp, transaction_id",
            connection,
            parse_dates={"timestamp": {"format": "%Y-%m-%dT%H:%M:%S"}},
        )

        if transactions.empty:
            raise ValueError("No transactions found. Run the transaction generator first.")

        # Generate realistic delays (3-7 days).
        delays_hours = []
        for is_fraud_flag in (transactions["fraud_pattern"].notna()):
            delay_h = rng_numpy.uniform(72, 168)
            delays_hours.append(float(delay_h))

        label_timestamps = transactions["timestamp"] + pd.to_timedelta(delays_hours, unit="h")

        # Determine which labels are mature.
        latest_label_time = label_timestamps.max() + timedelta(days=14)
        
        is_mature = []
        for label_ts in label_timestamps:
            age_days = days_between(label_ts, latest_label_time)
            is_mature.append(1 if age_days >= MATURE_LABEL_AGE_DAYS else 0)

        label_sources = [
            _determine_label_source(rng, 1 if fraud_pattern else 0)
            for fraud_pattern in transactions["fraud_pattern"].notna()
        ]

        labels = pd.DataFrame(
            {
                "transaction_id": transactions["transaction_id"],
                "label_timestamp": label_timestamps.dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "is_fraud": (transactions["fraud_pattern"].notna()).astype(int),
                "label_source": label_sources,
                "label_delay_hours": delays_hours,
                "is_mature": is_mature,
            }
        )

        connection.execute("DELETE FROM labels")
        labels.to_sql("labels", connection, if_exists="append", index=False)

    mature_count = int(np.sum(is_mature))
    fraud_count = int(labels["is_fraud"].sum())

    report = {
        "n_labels": int(len(labels)),
        "n_fraud_labels": fraud_count,
        "n_mature_labels": mature_count,
        "mature_rate": mature_count / len(labels) if len(labels) > 0 else 0.0,
        "delay_stats_hours": {
            "mean": float(np.mean(delays_hours)),
            "median": float(np.median(delays_hours)),
            "min": float(np.min(delays_hours)),
            "max": float(np.max(delays_hours)),
            "p95": float(np.percentile(delays_hours, 95)),
        },
        "delay_stats_days": {
            "mean": float(np.mean(delays_hours) / 24),
            "median": float(np.median(delays_hours) / 24),
            "min": float(np.min(delays_hours) / 24),
            "max": float(np.max(delays_hours) / 24),
            "p95": float(np.percentile(delays_hours, 95) / 24),
        },
        "label_sources": {
            source: int((np.array(label_sources) == source).sum())
            for source in set(label_sources)
        },
    }

    report_path = Path("artifacts/reports/label_delay_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Generated {len(labels):,} delayed labels ({fraud_count} fraud, {mature_count} mature)")
    print(f"Mean delay: {report['delay_stats_days']['mean']:.2f} days")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate delayed fraud labels.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_labels(db_path=args.db_path, seed=args.seed)


if __name__ == "__main__":
    main()
