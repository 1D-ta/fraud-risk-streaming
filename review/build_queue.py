"""Build a capacity-constrained manual review queue from scored transactions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from fraud_risk.config import REVIEW_CAPACITY


def build_review_queue(db_path: str = "data/fraud_risk.db", capacity: int = REVIEW_CAPACITY) -> dict:
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")

        scored = pd.read_sql_query(
            """
            SELECT
                s.transaction_id,
                s.fraud_score,
                s.risk_band,
                s.decision,
                l.is_fraud,
                t.amount,
                t.user_id,
                t.merchant_id
            FROM scores s
            JOIN transactions t ON s.transaction_id = t.transaction_id
            JOIN labels l ON s.transaction_id = l.transaction_id
            WHERE s.risk_band IN ('HIGH', 'CRITICAL')
            ORDER BY s.fraud_score DESC, s.transaction_id
            """,
            connection,
        )

        if scored.empty:
            review_queue = pd.DataFrame(
                columns=["transaction_id", "review_batch_id", "fraud_score", "review_rank", "decision", "capacity_limit"]
            )
            queue_size = 0
            overflow_size = 0
            review_batch_id = pd.Timestamp.utcnow().floor("s").isoformat()
        else:
            review_batch_id = pd.Timestamp.utcnow().floor("s").isoformat()
            review_queue = scored.head(capacity).copy().reset_index(drop=True)
            review_queue["review_batch_id"] = review_batch_id
            review_queue["review_rank"] = review_queue.index.astype(int)
            review_queue["capacity_limit"] = int(capacity)
            review_queue["decision"] = "manual_review"
            review_queue = review_queue[["transaction_id", "review_batch_id", "fraud_score", "review_rank", "decision", "capacity_limit"]]
            queue_size = int(len(review_queue))
            overflow_size = int(max(0, len(scored) - queue_size))

        connection.execute("DELETE FROM review_queue")
        if not review_queue.empty:
            review_queue.to_sql("review_queue", connection, if_exists="append", index=False)

        queue_precision = 0.0
        if queue_size > 0:
            queue_precision = float(
                review_queue.merge(
                    scored[["transaction_id", "is_fraud"]],
                    on="transaction_id",
                    how="left",
                )["is_fraud"].mean()
            )

    total_high_risk = int(len(scored))
    report = {
        "total_high_risk": total_high_risk,
        "queue_size": queue_size,
        "overflow_size": overflow_size,
        "capacity": capacity,
        "capacity_exceeded_rate": float(overflow_size / total_high_risk) if total_high_risk else 0.0,
        "queue_precision_estimate": queue_precision,
        "review_batch_id": review_batch_id,
        "status": "queued",
    }

    report_path = Path("artifacts/reports/review_queue_stats.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Review queue built")
    print(f"Saved review queue report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the fraud review queue.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--capacity", type=int, default=REVIEW_CAPACITY, help="Review queue capacity")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_review_queue(db_path=args.db_path, capacity=args.capacity)


if __name__ == "__main__":
    main()
