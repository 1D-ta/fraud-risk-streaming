"""Simulate a leakage bug by writing future fraud information into a hidden feature."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from fraud_risk.failure_injection import write_report


def _ensure_future_fraud_column(connection: sqlite3.Connection) -> None:
    column_names = {row[1] for row in connection.execute("PRAGMA table_info(features)").fetchall()}
    if "future_fraud_count" not in column_names:
        connection.execute("ALTER TABLE features ADD COLUMN future_fraud_count INTEGER DEFAULT 0")


def inject_leakage_bug(db_path: str = "data/fraud_risk.db") -> dict:
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _ensure_future_fraud_column(connection)

        frame = pd.read_sql_query(
            """
            SELECT t.transaction_id, t.user_id, t.timestamp, l.is_fraud
            FROM transactions t
            JOIN labels l ON t.transaction_id = l.transaction_id
            ORDER BY t.user_id, t.timestamp, t.transaction_id
            """,
            connection,
            parse_dates=["timestamp"],
        )

        if frame.empty:
            raise ValueError("No labeled transactions found. Generate data before injecting failures.")

        def future_count(group: pd.DataFrame) -> pd.Series:
            future_inclusive = group["is_fraud"].iloc[::-1].cumsum().iloc[::-1]
            return future_inclusive - group["is_fraud"]

        frame["future_fraud_count"] = frame.groupby("user_id", group_keys=False).apply(future_count).astype(int)

        update_rows = [
            (int(row.future_fraud_count), row.transaction_id)
            for row in frame.itertuples(index=False)
        ]
        connection.executemany(
            "UPDATE features SET future_fraud_count = ? WHERE transaction_id = ?",
            update_rows,
        )

    report = {
        "failure_type": "leakage_bug",
        "trigger": "A feature accidentally used future labels from the same user",
        "symptom": "Validation metrics look suspiciously perfect",
        "detection": "Leakage checks and production monitoring disagree",
        "impact": "The model looks great offline and fails in production",
        "root_cause": "A hidden feature stores future fraud counts",
        "mitigation": "Remove the leaky feature and retrain the model",
        "prevention": "Automated leakage checks and temporal validation",
        "affected_transactions": int(len(frame)),
        "max_future_fraud_count": int(frame["future_fraud_count"].max()),
        "status": "injected",
    }

    write_report("failure_leakage.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject a leakage bug failure.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = inject_leakage_bug(db_path=args.db_path)
    print("Injected leakage bug")
    print(f"Affected transactions: {report['affected_transactions']}")
    print(f"Max future fraud count: {report['max_future_fraud_count']}")


if __name__ == "__main__":
    main()