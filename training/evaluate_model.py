"""Evaluate trained fraud models and select the production model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fraud_risk.config import MATURE_LABEL_AGE_DAYS
from training.common import (
    FEATURE_COLUMNS,
    MODEL_SPECS,
    build_dataset_summary,
    build_split_summary,
    deserialize_model,
    ensure_directories,
    evaluate_predictions,
    feature_frame,
    fit_model,
    load_training_frame,
    predict_proba,
    serialize_model,
    split_temporally,
    target_frame,
)


def evaluate_models(db_path: str = "data/fraud_risk.db", maturity_days: int = MATURE_LABEL_AGE_DAYS) -> dict:
    ensure_directories()
    frame = load_training_frame(db_path=db_path, maturity_days=maturity_days)
    train_frame, validation_frame, test_frame = split_temporally(frame)

    X_train = feature_frame(train_frame)
    y_train = target_frame(train_frame)
    X_validation = feature_frame(validation_frame)
    y_validation = target_frame(validation_frame)
    X_test = feature_frame(test_frame)
    y_test = target_frame(test_frame)

    model_reports = {}
    best_model_name = None
    best_validation_pr_auc = -1.0

    for model_name in MODEL_SPECS:
        model_path = Path("artifacts/models") / f"{model_name}.pkl"
        if not model_path.exists():
            model = fit_model(model_name, X_train, y_train)
            serialize_model(model_path, model)
        else:
            model = deserialize_model(model_path)

        validation_probabilities = predict_proba(model, X_validation)
        test_probabilities = predict_proba(model, X_test)
        validation_metrics = evaluate_predictions(y_validation, validation_probabilities)
        test_metrics = evaluate_predictions(y_test, test_probabilities)

        model_reports[model_name] = {
            "artifact_path": str(model_path),
            "validation": validation_metrics,
            "test": test_metrics,
        }

        if validation_metrics["pr_auc"] > best_validation_pr_auc:
            best_validation_pr_auc = validation_metrics["pr_auc"]
            best_model_name = model_name

    if best_model_name is None:
        raise ValueError("No model could be selected for production.")

    production_model = fit_model(best_model_name, pd.concat([X_train, X_validation]), pd.concat([y_train, y_validation]))
    production_model_path = Path("artifacts/models/production_model.pkl")
    alias_path = Path("artifacts/models/fraud_model_v1.pkl")
    serialize_model(production_model_path, production_model)
    serialize_model(alias_path, production_model)

    report = {
        "dataset": build_dataset_summary(frame, maturity_days),
        "splits": build_split_summary(train_frame, validation_frame, test_frame),
        "feature_columns": FEATURE_COLUMNS,
        "models": model_reports,
        "best_model": {
            "name": best_model_name,
            "validation_pr_auc": best_validation_pr_auc,
            "production_artifact": str(production_model_path),
            "compatibility_artifact": str(alias_path),
        },
        "status": "evaluated",
    }

    report_path = Path("artifacts/reports/evaluation.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Best model: {best_model_name}")
    print(f"Saved production model to {production_model_path}")
    print(f"Saved evaluation report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate fraud detection models.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    parser.add_argument("--maturity-days", type=int, default=MATURE_LABEL_AGE_DAYS, help="Minimum label maturity in days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluate_models(db_path=args.db_path, maturity_days=args.maturity_days)


if __name__ == "__main__":
    main()
