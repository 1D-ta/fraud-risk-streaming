"""Train fraud detection models from mature, event-time-safe data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.common import (
    FEATURE_COLUMNS,
    MODEL_SPECS,
    MATURE_LABEL_DAYS,
    build_dataset_summary,
    build_split_summary,
    ensure_directories,
    feature_frame,
    fit_model,
    load_training_frame,
    serialize_model,
    split_temporally,
    target_frame,
)


def train_models(db_path: str = "data/fraud_risk.db", maturity_days: int = MATURE_LABEL_DAYS) -> dict:
    ensure_directories()
    frame = load_training_frame(db_path=db_path, maturity_days=maturity_days)
    train_frame, validation_frame, test_frame = split_temporally(frame)

    X_train = feature_frame(train_frame)
    y_train = target_frame(train_frame)

    candidate_metrics = {}
    model_paths = {}

    for model_name in MODEL_SPECS:
        model = fit_model(model_name, X_train, y_train)
        model_path = Path("artifacts/models") / f"{model_name}.pkl"
        serialize_model(model_path, model)
        model_paths[model_name] = str(model_path)
        candidate_metrics[model_name] = {
            "artifact_path": str(model_path),
        }

    report = {
        "dataset": build_dataset_summary(frame, maturity_days),
        "splits": build_split_summary(train_frame, validation_frame, test_frame),
        "feature_columns": FEATURE_COLUMNS,
        "candidate_models": candidate_metrics,
        "status": "trained",
    }

    report_path = Path("artifacts/reports/training_report_v1.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trained {len(MODEL_SPECS)} models on {len(train_frame):,} rows")
    print(f"Saved training report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train fraud detection models.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--maturity-days", type=int, default=MATURE_LABEL_DAYS, help="Minimum label maturity in days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_models(db_path=args.db_path, maturity_days=args.maturity_days)


if __name__ == "__main__":
    main()
