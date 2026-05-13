"""Simulate a false positive burst through a sharp distribution shift."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from fraud_risk.failure_injection import write_report


def inject_distribution_shift(db_path: str = "data/fraud_risk.db", amount_multiplier: float = 10.0) -> dict:
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        frame = pd.read_sql_query(
            """
            SELECT f.transaction_id, t.timestamp, t.amount,
                   f.user_txn_count_24h, f.user_amount_sum_7d,
                   f.merchant_fraud_rate_30d, f.amount_zscore,
                   f.hour_of_day, f.is_first_merchant
            FROM features f
            JOIN transactions t ON f.transaction_id = t.transaction_id
            ORDER BY t.timestamp, f.transaction_id
            """,
            connection,
            parse_dates=["timestamp"],
        )

        if frame.empty:
            raise ValueError("No features found. Build features before injecting failures.")

        cutoff = frame["timestamp"].quantile(0.80)
        affected = frame[frame["timestamp"] >= cutoff].copy()
        if affected.empty:
            affected = frame.tail(max(1, len(frame) // 5)).copy()

        affected["amount"] = affected["amount"] * amount_multiplier
        affected["user_amount_sum_7d"] = affected["user_amount_sum_7d"] * amount_multiplier
        affected["amount_zscore"] = affected["amount_zscore"] + 4.0
        affected["merchant_fraud_rate_30d"] = affected["merchant_fraud_rate_30d"].clip(upper=1.0)
        affected["user_txn_count_24h"] = affected["user_txn_count_24h"] + 2

        transaction_rows = [
            (float(row.amount), row.transaction_id)
            for row in affected.itertuples(index=False)
        ]
        feature_rows = [
            (
                int(row.user_txn_count_24h),
                float(row.user_amount_sum_7d),
                float(row.merchant_fraud_rate_30d),
                float(row.amount_zscore),
                int(row.hour_of_day),
                int(row.is_first_merchant),
                row.transaction_id,
            )
            for row in affected.itertuples(index=False)
        ]

        connection.executemany(
            "UPDATE transactions SET amount = ? WHERE transaction_id = ?",
            transaction_rows,
        )
        connection.executemany(
            """
            UPDATE features
            SET user_txn_count_24h = ?,
                user_amount_sum_7d = ?,
                merchant_fraud_rate_30d = ?,
                amount_zscore = ?,
                hour_of_day = ?,
                is_first_merchant = ?
            WHERE transaction_id = ?
            """,
            feature_rows,
        )

    report = {
        "failure_type": "distribution_shift",
        "trigger": "Holiday shopping surge pushed amounts far above the training distribution",
        "symptom": "Review queue overflows with high-risk scores",
        "detection": "Drift monitoring shows PSI spikes on amount-sensitive features",
        "impact": "False positives increase and reviewers are overwhelmed",
        "root_cause": "The model was trained on a narrower spending distribution",
        "mitigation": "Raise thresholds temporarily and retrain on recent data",
        "prevention": "Monitor feature distributions and seasonality",
        "affected_transactions": int(len(affected)),
        "amount_multiplier": float(amount_multiplier),
        "status": "injected",
    }

    write_report("failure_distribution_shift.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject a distribution shift failure.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--amount-multiplier", type=float, default=10.0, help="Scale factor for recent transaction amounts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = inject_distribution_shift(db_path=args.db_path, amount_multiplier=args.amount_multiplier)
    print("Injected distribution shift")
    print(f"Affected transactions: {report['affected_transactions']}")
    print(f"Amount multiplier: {report['amount_multiplier']:.1f}x")


if __name__ == "__main__":
    main()