"""Generate synthetic fraud transactions for the streaming project."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Deque, Dict, List, Tuple

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from simulation.init_db import init_database


CATEGORIES = ("retail", "food", "travel", "entertainment", "other")
CATEGORY_WEIGHTS = (0.42, 0.24, 0.14, 0.12, 0.08)
CATEGORY_RISK = {
    "retail": 0.55,
    "food": 0.20,
    "travel": 0.45,
    "entertainment": 0.65,
    "other": 0.30,
}


@dataclass(frozen=True)
class TransactionRow:
    transaction_id: str
    user_id: str
    merchant_id: str
    amount: float
    timestamp: str
    category: str
    is_fraud: int


def _make_profiles(rng: random.Random, count: int, prefix: str) -> List[Dict[str, float]]:
    profiles: List[Dict[str, float]] = []
    for index in range(count):
        profiles.append(
            {
                "id": f"{prefix}_{index:05d}",
                "spend_scale": rng.uniform(0.75, 1.45),
                "night_owl": 1.0 if rng.random() < 0.18 else 0.0,
                "merchant_risk": rng.uniform(0.0, 1.0),
            }
        )
    return profiles


def _pick_skewed_index(rng: random.Random, size: int, exponent: float) -> int:
    position = int((rng.random() ** exponent) * size)
    return min(position, size - 1)


def _trim_window(window: Deque[Tuple[datetime, float]], cutoff: datetime) -> None:
    while window and window[0][0] < cutoff:
        window.popleft()


def _clear_tables(connection: sqlite3.Connection) -> None:
    cursor = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    for table_name in ("review_queue", "scores", "features", "labels", "transactions"):
        if table_name in tables:
            connection.execute(f"DELETE FROM {table_name}")


def _generate_rows(
    num_transactions: int,
    fraud_rate: float,
    seed: int,
    start_timestamp: str,
    span_days: int,
) -> List[TransactionRow]:
    rng = random.Random(seed)
    user_profiles = _make_profiles(rng, 10_000, "user")
    merchant_profiles = _make_profiles(rng, 1_000, "merchant")

    start_dt = datetime.fromisoformat(start_timestamp)
    end_dt = start_dt + timedelta(days=span_days)
    total_seconds = int((end_dt - start_dt).total_seconds())
    offsets = sorted(rng.randrange(total_seconds) for _ in range(num_transactions))

    user_histories: Dict[str, Dict[str, object]] = {}
    rows: List[TransactionRow] = []
    suspicion_scores: List[float] = []

    for index, offset in enumerate(offsets, start=1):
        timestamp = start_dt + timedelta(seconds=offset)
        user_profile = user_profiles[_pick_skewed_index(rng, len(user_profiles), exponent=1.8)]
        merchant_profile = merchant_profiles[_pick_skewed_index(rng, len(merchant_profiles), exponent=1.45)]
        user_id = user_profile["id"]
        merchant_id = merchant_profile["id"]
        category = rng.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]

        history = user_histories.setdefault(
            user_id,
            {
                "recent_24h": deque(),
                "recent_7d": deque(),
                "seen_merchants": set(),
                "count": 0,
                "sum": 0.0,
                "sum_sq": 0.0,
            },
        )

        recent_24h: Deque[Tuple[datetime, float]] = history["recent_24h"]  # type: ignore[assignment]
        recent_7d: Deque[Tuple[datetime, float]] = history["recent_7d"]  # type: ignore[assignment]
        seen_merchants = history["seen_merchants"]  # type: ignore[assignment]

        _trim_window(recent_24h, timestamp - timedelta(hours=24))
        _trim_window(recent_7d, timestamp - timedelta(days=7))

        user_txn_count_24h = len(recent_24h)
        is_first_merchant = 1 if merchant_id not in seen_merchants else 0
        hour_of_day = timestamp.hour

        if history["count"] >= 5:
            average_amount = history["sum"] / history["count"]
            variance = max((history["sum_sq"] / history["count"]) - (average_amount ** 2), 0.0)
            amount_std = variance ** 0.5
            amount_zscore = 0.0 if amount_std == 0 else (average_amount - average_amount) / amount_std
        else:
            amount_zscore = 0.0

        category_multiplier = {
            "retail": 1.05,
            "food": 0.75,
            "travel": 1.35,
            "entertainment": 1.25,
            "other": 0.90,
        }[category]
        base_amount = rng.lognormvariate(3.45, 0.75) * user_profile["spend_scale"] * category_multiplier
        amount = max(1.0, min(base_amount, 500.0))
        amount = round(amount, 2)

        burstiness = min(user_txn_count_24h / 8.0, 1.0)
        night_flag = 1.0 if 1 <= hour_of_day <= 5 or (user_profile["night_owl"] == 1.0 and hour_of_day in {22, 23, 0}) else 0.0
        amount_risk = min(amount / 220.0, 1.0)
        merchant_risk = merchant_profile["merchant_risk"]
        category_risk = CATEGORY_RISK[category]
        suspiciousness = (
            0.30 * amount_risk
            + 0.20 * burstiness
            + 0.18 * night_flag
            + 0.14 * is_first_merchant
            + 0.12 * category_risk
            + 0.06 * merchant_risk
            + 0.05 * (1.0 if amount >= 300.0 else 0.0)
            + rng.random() * 0.08
        )

        rows.append(
            TransactionRow(
                transaction_id=f"txn_{index:08d}",
                user_id=str(user_id),
                merchant_id=str(merchant_id),
                amount=amount,
                timestamp=timestamp.replace(microsecond=0).isoformat(),
                category=category,
                is_fraud=0,
            )
        )
        suspicion_scores.append(suspiciousness)

        recent_24h.append((timestamp, amount))
        recent_7d.append((timestamp, amount))
        seen_merchants.add(merchant_id)
        history["count"] = int(history["count"]) + 1
        history["sum"] = float(history["sum"]) + amount
        history["sum_sq"] = float(history["sum_sq"]) + (amount * amount)

    fraud_count = max(1, int(round(num_transactions * fraud_rate)))
    ranking = sorted(range(len(suspicion_scores)), key=suspicion_scores.__getitem__, reverse=True)
    fraud_indices = set(ranking[:fraud_count])

    return [
        TransactionRow(
            transaction_id=row.transaction_id,
            user_id=row.user_id,
            merchant_id=row.merchant_id,
            amount=row.amount,
            timestamp=row.timestamp,
            category=row.category,
            is_fraud=1 if index in fraud_indices else 0,
        )
        for index, row in enumerate(rows)
    ]


def generate_transactions(
    num_transactions: int = 100_000,
    fraud_rate: float = 0.02,
    db_path: str = "data/fraud_risk.db",
    seed: int = 42,
    start_timestamp: str = "2024-01-01T00:00:00",
    span_days: int = 30,
) -> dict:
    """Generate synthetic transactions and persist them to SQLite."""

    db_file = init_database(db_path)
    rows = _generate_rows(num_transactions, fraud_rate, seed, start_timestamp, span_days)

    amounts = [row.amount for row in rows]
    fraud_count = sum(row.is_fraud for row in rows)

    with sqlite3.connect(db_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _clear_tables(connection)
        connection.executemany(
            """
            INSERT INTO transactions (
                transaction_id,
                user_id,
                merchant_id,
                amount,
                timestamp,
                category,
                is_fraud
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.transaction_id,
                    row.user_id,
                    row.merchant_id,
                    row.amount,
                    row.timestamp,
                    row.category,
                    row.is_fraud,
                )
                for row in rows
            ],
        )

    report = {
        "n_transactions": num_transactions,
        "n_fraud": fraud_count,
        "fraud_rate": fraud_count / num_transactions if num_transactions else 0.0,
        "date_range": {
            "start": rows[0].timestamp if rows else None,
            "end": rows[-1].timestamp if rows else None,
        },
        "amount_stats": {
            "mean": round(mean(amounts), 4) if amounts else 0.0,
            "std": round(pstdev(amounts), 4) if len(amounts) > 1 else 0.0,
            "min": round(min(amounts), 2) if amounts else 0.0,
            "max": round(max(amounts), 2) if amounts else 0.0,
        },
    }

    report_path = Path("artifacts/reports/transaction_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Generated {num_transactions:,} transactions with {fraud_count:,} fraud labels")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud transactions.")
    parser.add_argument("--num-transactions", type=int, default=100_000, help="Number of transactions to generate")
    parser.add_argument("--fraud-rate", type=float, default=0.02, help="Target fraud rate")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--start-timestamp", default="2024-01-01T00:00:00", help="Start timestamp in ISO format")
    parser.add_argument("--span-days", type=int, default=30, help="Number of days covered by the stream")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_transactions(
        num_transactions=args.num_transactions,
        fraud_rate=args.fraud_rate,
        db_path=args.db_path,
        seed=args.seed,
        start_timestamp=args.start_timestamp,
        span_days=args.span_days,
    )


if __name__ == "__main__":
    main()
