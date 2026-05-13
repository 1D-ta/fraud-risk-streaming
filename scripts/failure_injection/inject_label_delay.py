"""Simulate a label delay spike by pushing some label timestamps forward."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import timedelta
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from fraud_risk.failure_injection import write_report


def inject_label_delay_spike(db_path: str = "data/fraud_risk.db", seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        labels = pd.read_sql_query(
            "SELECT transaction_id, is_fraud, label_timestamp, delay_days FROM labels ORDER BY label_timestamp, transaction_id",
            connection,
            parse_dates=["label_timestamp"],
        )

        if labels.empty:
            raise ValueError("No labels found. Generate data before injecting failures.")

        affected_count = max(1, len(labels) // 2)
        affected_indices = rng.choice(labels.index.to_numpy(), size=affected_count, replace=False)
        extra_delay = rng.uniform(7.0, 14.0, size=affected_count)

        labels.loc[affected_indices, "label_timestamp"] = labels.loc[affected_indices, "label_timestamp"] + pd.to_timedelta(extra_delay, unit="D")
        labels.loc[affected_indices, "delay_days"] = (labels.loc[affected_indices, "delay_days"] + extra_delay).clip(upper=7.0)

        update_rows = [
            (
                pd.Timestamp(row.label_timestamp).floor("s").isoformat(),
                float(row.delay_days),
                row.transaction_id,
            )
            for row in labels.itertuples(index=False)
        ]
        connection.executemany(
            "UPDATE labels SET label_timestamp = ?, delay_days = ? WHERE transaction_id = ?",
            update_rows,
        )

    report = {
        "failure_type": "label_delay_spike",
        "trigger": "Simulated upstream label provider outage",
        "symptom": "A large share of labels arrive 14+ days late",
        "detection": "Maturity analysis shows a sharp drop in mature labels",
        "impact": "Training data shrinks and recall drops",
        "root_cause": "Delayed chargeback and investigation processing",
        "mitigation": "Wait for labels or retrain on the reduced mature subset",
        "prevention": "Monitor label arrival rate and p95 delay",
        "affected_labels": int(affected_count),
        "extra_delay_days_added_mean": float(extra_delay.mean()),
        "median_delay_days": float(labels["delay_days"].median()),
        "p95_delay_days": float(labels["delay_days"].quantile(0.95)),
        "status": "injected",
    }

    write_report("failure_label_delay.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject a label delay spike failure.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = inject_label_delay_spike(db_path=args.db_path, seed=args.seed)
    print("Injected label delay spike")
    print(f"Affected labels: {report['affected_labels']}")
    print(f"Median delay: {report['median_delay_days']:.2f} days")


if __name__ == "__main__":
    main()