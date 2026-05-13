"""Analyze how many transactions have mature fraud labels."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


def analyze_maturity(db_path: str = "data/fraud_risk.db", maturity_days: int = 7) -> dict:
    """Measure label maturity using the most recent transaction timestamp as the reference point."""

    with sqlite3.connect(db_path) as connection:
        current_date_raw = pd.read_sql_query(
            "SELECT MAX(label_timestamp) AS max_ts FROM labels",
            connection,
        )["max_ts"].iloc[0]

        if current_date_raw is None:
            raise ValueError("No labels found. Run the label generator first.")

        current_date = datetime.fromisoformat(current_date_raw)
        maturity_query = """
        SELECT
            COUNT(*) AS total_transactions,
            SUM(CASE WHEN l.is_mature = 1 THEN 1 ELSE 0 END) AS mature_transactions,
            SUM(CASE WHEN l.is_mature = 1 AND l.is_fraud = 1 THEN 1 ELSE 0 END) AS mature_fraud
        FROM transactions t
        JOIN labels l ON t.transaction_id = l.transaction_id
        """
        result = pd.read_sql_query(maturity_query, connection).iloc[0]

    total = int(result["total_transactions"])
    mature = int(result["mature_transactions"])
    mature_fraud = int(result["mature_fraud"])

    report = {
        "maturity_window_days": maturity_days,
        "current_date": current_date.isoformat(),
        "total_transactions": total,
        "mature_transactions": mature,
        "mature_fraud": mature_fraud,
        "maturity_rate": float(mature / total) if total else 0.0,
        "mature_fraud_rate": float(mature_fraud / mature) if mature else 0.0,
    }

    report_path = Path("artifacts/reports/maturity_analysis.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Maturity analysis complete")
    print(f"Total transactions: {total:,}")
    print(f"Mature (>{maturity_days}d): {mature:,}")
    print(f"Mature fraud: {mature_fraud:,}")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze label maturity.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--maturity-days", type=int, default=7, help="Maturity window in days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyze_maturity(db_path=args.db_path, maturity_days=args.maturity_days)


if __name__ == "__main__":
    main()
