"""Score transactions with the production fraud model."""

from __future__ import annotations

import argparse
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from training.common import FEATURE_COLUMNS, ensure_directories


MODEL_PATH = Path("artifacts/models/production_model.pkl")


def get_risk_band(score: float) -> str:
    if score >= 0.9:
        return "CRITICAL"
    if score >= 0.7:
        return "HIGH"
    if score >= 0.3:
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
            t.transaction_id,
            t.timestamp,
            t.user_id,
            t.merchant_id,
            t.amount,
            f.user_txn_count_24h,
            f.user_amount_sum_7d,
            f.merchant_fraud_rate_30d,
            f.amount_zscore,
            f.hour_of_day,
            f.is_first_merchant
        FROM transactions t
        JOIN features f ON t.transaction_id = f.transaction_id
        ORDER BY t.timestamp, t.transaction_id
        """,
        connection,
        parse_dates=["timestamp"],
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
            scored_rows.append(
                {
                    "transaction_id": row.transaction_id,
                    "score": score,
                    "risk_band": get_risk_band(score),
                    "reason_code_1": None,
                    "reason_code_2": None,
                    "reason_code_3": None,
                    "score_timestamp": score_timestamp,
                }
            )

        for row, feature_values in zip(scored_rows, frame[FEATURE_COLUMNS].to_numpy(dtype=float)):
            reason_codes = get_reason_codes(model, feature_values)
            row["reason_code_1"], row["reason_code_2"], row["reason_code_3"] = reason_codes

        scores_df = pd.DataFrame(scored_rows)

        connection.execute("DELETE FROM scores")
        scores_df.to_sql("scores", connection, if_exists="append", index=False)

    report = {
        "n_scored": int(len(scores_df)),
        "risk_band_distribution": {key: int(value) for key, value in scores_df["risk_band"].value_counts().to_dict().items()},
        "score_stats": {
            "mean": float(scores_df["score"].mean()),
            "std": float(scores_df["score"].std(ddof=0)),
            "min": float(scores_df["score"].min()),
            "max": float(scores_df["score"].max()),
            "p95": float(np.percentile(scores_df["score"], 95)),
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
