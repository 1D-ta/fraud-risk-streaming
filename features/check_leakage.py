"""Check that feature timestamps do not use future information."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def check_leakage(db_path: str = "data/fraud_risk.db") -> dict:
    """Validate feature timestamps against transaction timestamps."""

    with sqlite3.connect(db_path) as connection:
        violations = connection.execute(
            """
            SELECT COUNT(*)
            FROM features f
            JOIN transactions t ON f.transaction_id = t.transaction_id
            WHERE f.feature_timestamp > t.timestamp
            """
        ).fetchone()[0]

    report = {
        "leakage_check": "PASS" if violations == 0 else "FAIL",
        "violations": int(violations),
        "check_timestamp": __import__("pandas").Timestamp.now().isoformat(),
        "rule": "feature_timestamp <= transaction_timestamp",
    }

    report_path = Path("artifacts/reports/leakage_check.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if violations:
        raise ValueError(f"Leakage check failed: {violations} violations")

    print("Leakage check passed: all features use only historical data")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check feature leakage.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    check_leakage(db_path=args.db_path)


if __name__ == "__main__":
    main()
