"""Run the full fraud-risk-streaming pipeline as a reproducible demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from features.build_features import build_features
from features.check_leakage import check_leakage
from monitoring.drift_detection import drift_report
from monitoring.performance_tracker import performance_report
from review.build_queue import build_review_queue
from scoring.score_transactions import score_transactions
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from simulation.init_db import init_database
from training.evaluate_model import evaluate_models
from training.train_model import train_models


def run_demo(
    db_path: str = "data/fraud_risk.db",
    num_transactions: int = 2_000,
    fraud_rate: float = 0.02,
    seed: int = 42,
    capacity: int = 100,
    top_k: int = 100,
    reset: bool = False,
) -> dict:
    """Execute the end-to-end pipeline and collect a compact summary."""

    db_file = Path(db_path)
    if reset and db_file.exists():
        db_file.unlink()

    init_database(db_path)

    transaction_report = generate_transactions(
        num_transactions=num_transactions,
        fraud_rate=fraud_rate,
        db_path=db_path,
        seed=seed,
    )
    label_report = generate_labels(db_path=db_path, seed=seed)
    feature_report = build_features(db_path=db_path)
    leakage_report = check_leakage(db_path=db_path)
    training_report = train_models(db_path=db_path)
    evaluation_report = evaluate_models(db_path=db_path)
    scoring_report = score_transactions(db_path=db_path)
    review_report = build_review_queue(db_path=db_path, capacity=capacity)
    drift = drift_report(db_path=db_path)
    performance = performance_report(db_path=db_path, top_k=top_k)

    summary = {
        "database": str(db_file),
        "transaction_report": transaction_report,
        "label_report": label_report,
        "feature_report": feature_report,
        "leakage_report": leakage_report,
        "training_report": training_report,
        "evaluation_report": evaluation_report,
        "scoring_report": scoring_report,
        "review_report": review_report,
        "drift_report": drift,
        "performance_report": performance,
        "status": "demo_complete",
    }

    report_path = Path("artifacts/reports/demo_summary.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fraud-risk-streaming demo pipeline.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--num-transactions", type=int, default=2_000, help="Number of synthetic transactions")
    parser.add_argument("--fraud-rate", type=float, default=0.02, help="Target fraud rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--capacity", type=int, default=100, help="Manual review capacity")
    parser.add_argument("--top-k", type=int, default=100, help="Top-k metric cutoff")
    parser.add_argument("--reset", action="store_true", help="Delete the existing database before running")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_demo(
        db_path=args.db_path,
        num_transactions=args.num_transactions,
        fraud_rate=args.fraud_rate,
        seed=args.seed,
        capacity=args.capacity,
        top_k=args.top_k,
        reset=args.reset,
    )

    print("Demo pipeline complete")
    print(f"Database: {summary['database']}")
    print(f"Scored transactions: {summary['scoring_report']['n_scored']}")
    print(f"Review queue size: {summary['review_report']['queue_size']}")
    print(f"Performance PR-AUC: {summary['performance_report']['pr_auc']:.4f}")


if __name__ == "__main__":
    main()