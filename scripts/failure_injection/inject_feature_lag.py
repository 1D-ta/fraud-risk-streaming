"""Simulate feature lag by making the newest features stale and sparse."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import timedelta
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from fraud_risk.failure_injection import write_report, write_incident_report


def inject_feature_lag(db_path: str = "data/fraud_risk.db", lag_days: int = 3) -> dict:
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        frame = pd.read_sql_query(
            """
            SELECT f.transaction_id, t.timestamp, f.feature_timestamp,
                 f.user_txn_count_1h, f.user_txn_count_24h,
                 f.user_avg_amount_7d, f.user_amount_zscore_7d,
                 f.user_unique_merchants_24h, f.merchant_txn_count_1h,
                 f.device_user_count_24h, f.is_new_device_for_user,
                 f.city_change_flag_24h, f.amount,
                 f.hour_of_day, f.is_weekend, f.is_international
            FROM features f
            JOIN transactions t ON f.transaction_id = t.transaction_id
            ORDER BY t.timestamp, f.transaction_id
            """,
            connection,
            parse_dates=["timestamp", "feature_timestamp"],
        )

        if frame.empty:
            raise ValueError("No features found. Build features before injecting failures.")

        cutoff = frame["timestamp"].max() - pd.Timedelta(days=lag_days)
        affected = frame[frame["timestamp"] >= cutoff].copy()
        if affected.empty:
            affected = frame.tail(max(1, len(frame) // 10)).copy()

        affected["feature_timestamp"] = affected["timestamp"] - pd.to_timedelta(lag_days, unit="D")
        affected["user_txn_count_1h"] = 0
        affected["user_txn_count_24h"] = 0
        affected["user_avg_amount_7d"] = 0.0
        affected["user_amount_zscore_7d"] = 0.0
        affected["user_unique_merchants_24h"] = 0
        affected["merchant_txn_count_1h"] = 0
        affected["device_user_count_24h"] = 0
        affected["is_new_device_for_user"] = 1
        affected["city_change_flag_24h"] = 1

        update_rows = [
            (
                row.feature_timestamp.to_pydatetime().replace(microsecond=0).isoformat(),
                int(row.user_txn_count_1h),
                int(row.user_txn_count_24h),
                float(row.user_avg_amount_7d),
                float(row.user_amount_zscore_7d),
                int(row.user_unique_merchants_24h),
                int(row.merchant_txn_count_1h),
                int(row.device_user_count_24h),
                int(row.is_new_device_for_user),
                int(row.city_change_flag_24h),
                float(row.amount),
                int(row.hour_of_day),
                int(row.is_weekend),
                int(row.is_international),
                row.transaction_id,
            )
            for row in affected.itertuples(index=False)
        ]
        connection.executemany(
            """
            UPDATE features
            SET feature_timestamp = ?,
                user_txn_count_1h = ?,
                user_txn_count_24h = ?,
                user_avg_amount_7d = ?,
                user_amount_zscore_7d = ?,
                user_unique_merchants_24h = ?,
                merchant_txn_count_1h = ?,
                device_user_count_24h = ?,
                is_new_device_for_user = ?,
                city_change_flag_24h = ?,
                amount = ?,
                hour_of_day = ?,
                is_weekend = ?,
                is_international = ?
            WHERE transaction_id = ?
            """,
            update_rows,
        )

    report = {
        "failure_type": "feature_lag",
        "trigger": "Feature pipeline delay left recent data stale",
        "symptom": "Newest transactions have zeroed velocity features",
        "detection": "Feature freshness monitoring shows old feature timestamps",
        "impact": "Recent fraud is under-scored and recall drops",
        "root_cause": "Feature job lagged behind the event stream",
        "mitigation": "Backfill the missing window and re-score affected transactions",
        "prevention": "Alert on feature lag and automate backfills",
        "affected_transactions": int(len(affected)),
        "lag_days": int(lag_days),
        "status": "injected",
    }

    write_report("failure_feature_lag.json", report)
    write_incident_report("feature_lag", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject a feature lag failure.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--lag-days", type=int, default=3, help="How many days of freshness to remove")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = inject_feature_lag(db_path=args.db_path, lag_days=args.lag_days)
    print("Injected feature lag")
    print(f"Affected transactions: {report['affected_transactions']}")
    print(f"Lag days: {report['lag_days']}")


if __name__ == "__main__":
    main()