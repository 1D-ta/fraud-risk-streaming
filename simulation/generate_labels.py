"""Generate delayed fraud labels for the transaction stream."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median

import numpy as np
import pandas as pd


def _ensure_labels_table(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            transaction_id TEXT PRIMARY KEY,
            is_fraud INTEGER NOT NULL CHECK (is_fraud IN (0, 1)),
            label_timestamp TEXT NOT NULL,
            delay_days REAL NOT NULL CHECK (delay_days >= 3.0 AND delay_days <= 7.0),
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_labels_label_timestamp ON labels(label_timestamp)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_labels_transaction_id ON labels(transaction_id)")


def generate_labels(db_path: str = "data/fraud_risk.db", seed: int = 42) -> dict:
    """Populate the labels table with delayed confirmations."""

    rng = np.random.default_rng(seed)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _ensure_labels_table(connection)

        transactions = pd.read_sql_query(
            "SELECT transaction_id, timestamp, is_fraud FROM transactions ORDER BY timestamp, transaction_id",
            connection,
            parse_dates={"timestamp": {"format": "%Y-%m-%dT%H:%M:%S"}},
        )

        if transactions.empty:
            raise ValueError("No transactions found. Run the transaction generator first.")

        delays = rng.uniform(3.0, 7.0, len(transactions))
        label_timestamps = transactions["timestamp"] + pd.to_timedelta(delays, unit="D")

        labels = pd.DataFrame(
            {
                "transaction_id": transactions["transaction_id"],
                "is_fraud": transactions["is_fraud"].astype(int),
                "label_timestamp": label_timestamps.dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "delay_days": delays,
            }
        )

        connection.execute("DELETE FROM labels")
        labels.to_sql("labels", connection, if_exists="append", index=False)

    report = {
        "n_labels": int(len(labels)),
        "delay_stats": {
            "mean_days": float(delays.mean()),
            "median_days": float(median(delays)),
            "min_days": float(delays.min()),
            "max_days": float(delays.max()),
            "p95_days": float(np.percentile(delays, 95)),
        },
        "delay_histogram": {
            "3-4": int(((delays >= 3.0) & (delays < 4.0)).sum()),
            "4-5": int(((delays >= 4.0) & (delays < 5.0)).sum()),
            "5-6": int(((delays >= 5.0) & (delays < 6.0)).sum()),
            "6-7": int(((delays >= 6.0) & (delays <= 7.0)).sum()),
        },
    }

    report_path = Path("artifacts/reports/label_delay_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Generated {len(labels):,} delayed labels")
    print(f"Mean delay: {report['delay_stats']['mean_days']:.2f} days")
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
