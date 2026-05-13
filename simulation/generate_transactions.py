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

from fraud_risk.config import (
    DEFAULT_CHANNELS,
    DEFAULT_CITIES,
    DEFAULT_FRAUD_RATE,
    DEFAULT_NUM_DEVICES,
    DEFAULT_NUM_MERCHANTS,
    DEFAULT_NUM_TRANSACTIONS,
    DEFAULT_NUM_USERS,
    DEFAULT_CATEGORIES,
)
from simulation.init_db import init_database


CATEGORY_WEIGHTS = (0.42, 0.24, 0.14, 0.12, 0.08)
CATEGORY_RISK = {
    "retail": 0.55,
    "food": 0.20,
    "travel": 0.45,
    "entertainment": 0.65,
    "other": 0.30,
}
CURRENCIES = ("USD", "EUR", "GBP", "CAD")


@dataclass(frozen=True)
class TransactionRow:
    transaction_id: str
    user_id: str
    merchant_id: str
    device_id: str
    timestamp: str
    amount: float
    currency: str
    merchant_category: str
    channel: str
    location_city: str
    is_international: int
    fraud_pattern: str | None


def _make_profiles(rng: random.Random, count: int, prefix: str) -> List[Dict[str, object]]:
    """Generate user/merchant profiles with behavioral characteristics."""
    profiles: List[Dict[str, object]] = []
    for index in range(count):
        profiles.append(
            {
                "id": f"{prefix}_{index:05d}",
                "spend_scale": rng.uniform(0.75, 1.45),
                "night_owl": 1.0 if rng.random() < 0.18 else 0.0,
                "merchant_risk": rng.uniform(0.0, 1.0),
                "preferred_city": rng.choice(DEFAULT_CITIES),
                "preferred_channel": rng.choice(DEFAULT_CHANNELS),
                "international_rate": rng.uniform(0.0, 0.3),
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
    """Generate synthetic transaction rows with fraud labels."""
    rng = random.Random(seed)
    user_profiles = _make_profiles(rng, DEFAULT_NUM_USERS, "user")
    merchant_profiles = _make_profiles(rng, DEFAULT_NUM_MERCHANTS, "merchant")
    device_ids = [f"device_{i:05d}" for i in range(DEFAULT_NUM_DEVICES)]

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
        category = rng.choices(DEFAULT_CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
        device_id = rng.choice(device_ids)
        channel = user_profile["preferred_channel"]
        is_international = 1 if rng.random() < user_profile["international_rate"] else 0
        location_city = DEFAULT_CITIES[rng.randint(0, len(DEFAULT_CITIES) - 1)]
        currency = rng.choice(CURRENCIES)

        history = user_histories.setdefault(
            user_id,
            {
                "recent_24h": deque(),
                "recent_7d": deque(),
                "recent_1h": deque(),
                "seen_merchants": set(),
                "seen_devices": set(),
                "seen_cities": set(),
                "last_city": None,
                "count": 0,
                "sum": 0.0,
                "sum_sq": 0.0,
            },
        )

        recent_24h: Deque[Tuple[datetime, float]] = history["recent_24h"]  # type: ignore[assignment]
        recent_7d: Deque[Tuple[datetime, float]] = history["recent_7d"]  # type: ignore[assignment]
        recent_1h: Deque[Tuple[datetime, float]] = history["recent_1h"]  # type: ignore[assignment]
        seen_merchants = history["seen_merchants"]  # type: ignore[assignment]
        seen_devices = history["seen_devices"]  # type: ignore[assignment]
        seen_cities = history["seen_cities"]  # type: ignore[assignment]

        _trim_window(recent_24h, timestamp - timedelta(hours=24))
        _trim_window(recent_7d, timestamp - timedelta(days=7))
        _trim_window(recent_1h, timestamp - timedelta(hours=1))

        user_txn_count_1h = len(recent_1h)
        user_txn_count_24h = len(recent_24h)
        is_first_merchant = 1 if merchant_id not in seen_merchants else 0
        is_new_device = 1 if device_id not in seen_devices else 0
        city_change = 1 if location_city != history.get("last_city") and history.get("last_city") is not None else 0
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
        night_flag = 1.0 if 1 <= hour_of_day <= 5 else 0.0
        amount_risk = min(amount / 220.0, 1.0)
        merchant_risk = merchant_profile["merchant_risk"]
        category_risk = CATEGORY_RISK[category]
        suspiciousness = (
            0.25 * amount_risk
            + 0.20 * burstiness
            + 0.15 * night_flag
            + 0.12 * is_first_merchant
            + 0.12 * category_risk
            + 0.08 * merchant_risk
            + 0.05 * is_new_device
            + 0.03 * city_change
            + rng.random() * 0.05
        )

        # Determine fraud pattern (if flagged as fraud, what pattern triggered it)
        fraud_pattern: str | None = None
        if user_txn_count_1h > 5:
            fraud_pattern = "high_velocity"
        elif is_new_device and amount > 250:
            fraud_pattern = "new_device_high_amount"
        elif city_change and is_international:
            fraud_pattern = "unusual_location"
        elif is_first_merchant and amount > 300:
            fraud_pattern = "new_merchant_large_amount"
        elif amount > 450:
            fraud_pattern = "large_amount"

        rows.append(
            TransactionRow(
                transaction_id=f"txn_{index:08d}",
                user_id=str(user_id),
                merchant_id=str(merchant_id),
                device_id=str(device_id),
                timestamp=timestamp.replace(microsecond=0).isoformat(),
                amount=amount,
                currency=currency,
                merchant_category=category,
                channel=channel,
                location_city=location_city,
                is_international=is_international,
                fraud_pattern=fraud_pattern,
            )
        )
        suspicion_scores.append(suspiciousness)

        recent_24h.append((timestamp, amount))
        recent_7d.append((timestamp, amount))
        recent_1h.append((timestamp, amount))
        seen_merchants.add(merchant_id)
        seen_devices.add(device_id)
        seen_cities.add(location_city)
        history["last_city"] = location_city
        history["count"] = int(history["count"]) + 1
        history["sum"] = float(history["sum"]) + amount
        history["sum_sq"] = float(history["sum_sq"]) + (amount * amount)

    # Mark top suspicion scores as fraud
    fraud_count = max(1, int(round(num_transactions * fraud_rate)))
    ranking = sorted(range(len(suspicion_scores)), key=suspicion_scores.__getitem__, reverse=True)
    fraud_indices = {position + 1 for position in ranking[:fraud_count]}

    return [
        TransactionRow(
            transaction_id=row.transaction_id,
            user_id=row.user_id,
            merchant_id=row.merchant_id,
            device_id=row.device_id,
            timestamp=row.timestamp,
            amount=row.amount,
            currency=row.currency,
            merchant_category=row.merchant_category,
            channel=row.channel,
            location_city=row.location_city,
            is_international=row.is_international,
            fraud_pattern=(row.fraud_pattern or "synthetic_fraud") if index in fraud_indices else None,
        )
        for index, row in enumerate(rows, start=1)
    ]


def generate_transactions(
    num_transactions: int = DEFAULT_NUM_TRANSACTIONS,
    fraud_rate: float = DEFAULT_FRAUD_RATE,
    db_path: str = "data/fraud_risk.db",
    seed: int = 42,
    start_timestamp: str = "2024-01-01T00:00:00",
    span_days: int = 30,
) -> dict:
    """Generate synthetic transactions and persist them to SQLite."""

    db_file = init_database(db_path)
    rows = _generate_rows(num_transactions, fraud_rate, seed, start_timestamp, span_days)

    amounts = [row.amount for row in rows]
    fraud_count = sum(1 for row in rows if row.fraud_pattern is not None)

    with sqlite3.connect(db_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        _clear_tables(connection)
        connection.executemany(
            """
            INSERT INTO transactions (
                transaction_id,
                user_id,
                merchant_id,
                device_id,
                timestamp,
                amount,
                currency,
                merchant_category,
                channel,
                location_city,
                is_international,
                fraud_pattern
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.transaction_id,
                    row.user_id,
                    row.merchant_id,
                    row.device_id,
                    row.timestamp,
                    row.amount,
                    row.currency,
                    row.merchant_category,
                    row.channel,
                    row.location_city,
                    row.is_international,
                    row.fraud_pattern,
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
        "channels": list(set(row.channel for row in rows)),
        "cities": list(set(row.location_city for row in rows)),
        "currencies": list(set(row.currency for row in rows)),
    }

    report_path = Path("artifacts/reports/transaction_stats.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Generated {num_transactions:,} transactions with {fraud_count:,} fraud patterns")
    print(f"Saved report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud transactions.")
    parser.add_argument(
        "--num-transactions",
        type=int,
        default=DEFAULT_NUM_TRANSACTIONS,
        help="Number of transactions to generate",
    )
    parser.add_argument(
        "--fraud-rate",
        type=float,
        default=DEFAULT_FRAUD_RATE,
        help="Target fraud rate",
    )
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--start-timestamp",
        default="2024-01-01T00:00:00",
        help="Start timestamp in ISO format",
    )
    parser.add_argument(
        "--span-days",
        type=int,
        default=30,
        help="Number of days covered by the stream",
    )
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
