"""Score transactions with the production fraud model."""

from __future__ import annotations

import argparse
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from fraud_risk.config import MODEL_VERSION, RISK_THRESHOLDS, SCORE_DECISIONS
from training.common import FEATURE_COLUMNS, ensure_directories


MODEL_PATH = Path("artifacts/models/production_model.pkl")


def get_risk_band(score: float) -> str:
    if score >= RISK_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _extract_classifier(model):
    if hasattr(model, "named_steps"):
        return model.named_steps["classifier"]
    return model


def get_reason_codes(model, feature_values: np.ndarray) -> list[str]:
    classifier = _extract_classifier(model)
    feature_values = np.asarray(feature_values, dtype=float)

    if hasattr(classifier, "coef_"):
        weights = np.abs(np.asarray(classifier.coef_)[0] * feature_values)
    elif hasattr(classifier, "feature_importances_"):
        weights = np.asarray(classifier.feature_importances_) * np.abs(feature_values)
    else:
        weights = np.abs(feature_values)

    top_indices = np.argsort(weights)[-3:][::-1]
    reasons = [FEATURE_COLUMNS[index] for index in top_indices]
    while len(reasons) < 3:
        reasons.append(reasons[-1] if reasons else FEATURE_COLUMNS[0])
    return reasons


def _load_scoring_frame(connection: sqlite3.Connection) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT
            f.transaction_id,
            f.user_txn_count_1h,
            f.user_txn_count_24h,
            f.user_avg_amount_7d,
            f.user_amount_zscore_7d,
            f.user_unique_merchants_24h,
            f.merchant_txn_count_1h,
            f.device_user_count_24h,
            f.is_new_device_for_user,
            f.city_change_flag_24h,
            f.amount,
            f.hour_of_day,
            f.is_weekend,
            f.is_international
        FROM features f
        ORDER BY f.feature_timestamp, f.transaction_id
        """,
        connection,
        parse_dates=[],
    )

    if frame.empty:
        raise ValueError("No scored transactions available. Run the feature pipeline first.")

    return frame


def score_transactions(db_path: str = "data/fraud_risk.db") -> dict:
    ensure_directories()

    if not MODEL_PATH.exists():
        raise FileNotFoundError("Production model not found. Run training evaluation first.")

    with MODEL_PATH.open("rb") as handle:
        model = pickle.load(handle)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        frame = _load_scoring_frame(connection)

        X = frame[FEATURE_COLUMNS]
        scores = np.asarray(model.predict_proba(X))[:, 1]

        scored_rows = []
        score_timestamp = pd.Timestamp.utcnow().isoformat()
        for index, row in enumerate(frame.itertuples(index=False)):
            feature_values = np.array([getattr(row, column) for column in FEATURE_COLUMNS], dtype=float)
            score = float(scores[index])
            risk_band = get_risk_band(score)
            scored_rows.append(
                {
                    "transaction_id": row.transaction_id,
                    "fraud_score": score,
                    "risk_band": risk_band,
                    "decision": SCORE_DECISIONS[risk_band],
                    "reason_codes": None,
                    "model_version": MODEL_VERSION,
                    "score_timestamp": score_timestamp,
                }
            )

        for row, feature_values in zip(scored_rows, frame[FEATURE_COLUMNS].to_numpy(dtype=float)):
            row["reason_codes"] = json.dumps(get_reason_codes(model, feature_values))

        scores_df = pd.DataFrame(scored_rows)

        connection.execute("DELETE FROM scores")
        scores_df.to_sql("scores", connection, if_exists="append", index=False)

    report = {
        "n_scored": int(len(scores_df)),
        "risk_band_distribution": {key: int(value) for key, value in scores_df["risk_band"].value_counts().to_dict().items()},
        "decision_distribution": {key: int(value) for key, value in scores_df["decision"].value_counts().to_dict().items()},
        "score_stats": {
            "mean": float(scores_df["fraud_score"].mean()),
            "std": float(scores_df["fraud_score"].std(ddof=0)),
            "min": float(scores_df["fraud_score"].min()),
            "max": float(scores_df["fraud_score"].max()),
            "p95": float(np.percentile(scores_df["fraud_score"], 95)),
        },
        "status": "scored",
    }

    report_path = Path("artifacts/reports/scoring_stats.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Scored {len(scores_df):,} transactions")
    print(f"Saved scoring report to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score fraud transactions.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    score_transactions(db_path=args.db_path)


if __name__ == "__main__":
    main()
