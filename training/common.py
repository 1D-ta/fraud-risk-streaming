"""Shared helpers for fraud model training and evaluation."""

from __future__ import annotations

import pickle
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight


FEATURE_COLUMNS = [
    "user_txn_count_24h",
    "user_amount_sum_7d",
    "merchant_fraud_rate_30d",
    "amount_zscore",
    "hour_of_day",
    "is_first_merchant",
]

MATURE_LABEL_DAYS = 7
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
TOP_K_REVIEW = 100


@dataclass(frozen=True)
class ModelSpec:
    name: str
    factory: Callable[[], object]
    uses_sample_weight: bool = False


MODEL_SPECS: Dict[str, ModelSpec] = {
    "logistic_regression": ModelSpec(
        name="logistic_regression",
        factory=lambda: Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
                ),
            ]
        ),
    ),
    "gradient_boosting": ModelSpec(
        name="gradient_boosting",
        factory=lambda: GradientBoostingClassifier(random_state=42),
        uses_sample_weight=True,
    ),
}


def ensure_directories() -> None:
    Path("artifacts/models").mkdir(parents=True, exist_ok=True)
    Path("artifacts/reports").mkdir(parents=True, exist_ok=True)


def load_training_frame(db_path: str, maturity_days: int = MATURE_LABEL_DAYS) -> pd.DataFrame:
    with sqlite3.connect(db_path) as connection:
        frame = pd.read_sql_query(
            """
            WITH latest AS (
                SELECT MAX(timestamp) AS max_timestamp
                FROM transactions
            )
            SELECT
                t.transaction_id,
                t.timestamp,
                l.is_fraud,
                f.user_txn_count_24h,
                f.user_amount_sum_7d,
                f.merchant_fraud_rate_30d,
                f.amount_zscore,
                f.hour_of_day,
                f.is_first_merchant
            FROM transactions t
            JOIN labels l ON t.transaction_id = l.transaction_id
            JOIN features f ON t.transaction_id = f.transaction_id
            CROSS JOIN latest
            WHERE julianday(latest.max_timestamp) - julianday(t.timestamp) >= :maturity_days
            ORDER BY t.timestamp, t.transaction_id
            """,
            connection,
            params={"maturity_days": maturity_days},
            parse_dates=["timestamp"],
        )

    if frame.empty:
        raise ValueError("No mature labeled rows available. Run the data generation and feature steps first.")

    return frame


def split_temporally(frame: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(frame) < 3:
        raise ValueError("Need at least three rows to create train, validation, and test splits.")

    positive_positions = np.flatnonzero(frame["is_fraud"].to_numpy(dtype=int) == 1)
    if len(positive_positions) >= 3:
        train_positive_index = max(0, int(len(positive_positions) * 0.60) - 1)
        validation_positive_index = max(train_positive_index + 1, int(len(positive_positions) * 0.80) - 1)

        if validation_positive_index >= len(positive_positions):
            validation_positive_index = len(positive_positions) - 1
        if train_positive_index >= validation_positive_index:
            train_positive_index = max(0, validation_positive_index - 1)

        train_end = int(positive_positions[train_positive_index]) + 1
        validation_end = int(positive_positions[validation_positive_index]) + 1
    else:
        train_end = max(1, int(len(frame) * TRAIN_FRACTION))
        validation_end = max(train_end + 1, int(len(frame) * (TRAIN_FRACTION + VALIDATION_FRACTION)))

    train_end = min(train_end, len(frame) - 2)
    validation_end = min(max(validation_end, train_end + 1), len(frame) - 1)

    train_frame = frame.iloc[:train_end].copy()
    validation_frame = frame.iloc[train_end:validation_end].copy()
    test_frame = frame.iloc[validation_end:].copy()

    if train_frame.empty or validation_frame.empty or test_frame.empty:
        raise ValueError("Temporal split produced an empty partition.")

    return train_frame, validation_frame, test_frame


def _feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[FEATURE_COLUMNS].copy()


def _target_vector(frame: pd.DataFrame) -> pd.Series:
    return frame["is_fraud"].astype(int).copy()


def fit_model(model_name: str, X_train: pd.DataFrame, y_train: pd.Series):
    spec = MODEL_SPECS[model_name]
    model = spec.factory()

    if spec.uses_sample_weight:
        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
        model.fit(X_train, y_train, sample_weight=sample_weight)
    else:
        model.fit(X_train, y_train)

    return model


def predict_proba(model, X: pd.DataFrame) -> np.ndarray:
    probabilities = model.predict_proba(X)
    return np.asarray(probabilities)[:, 1]


def evaluate_predictions(y_true: pd.Series, y_prob: np.ndarray) -> dict:
    y_true_array = y_true.to_numpy(dtype=int)
    y_prob_array = np.asarray(y_prob, dtype=float)
    y_pred_array = (y_prob_array >= 0.5).astype(int)

    if len(np.unique(y_true_array)) > 1:
        precision, recall, _ = precision_recall_curve(y_true_array, y_prob_array)
        pr_auc = float(auc(recall, precision))
        roc_auc = float(roc_auc_score(y_true_array, y_prob_array))
        brier = float(brier_score_loss(y_true_array, y_prob_array))
    else:
        pr_auc = 0.0
        roc_auc = 0.0
        brier = 0.0

    top_k = min(TOP_K_REVIEW, len(y_true_array))
    top_indices = np.argsort(y_prob_array)[-top_k:]
    positives = int(y_true_array.sum())
    tn, fp, fn, tp = confusion_matrix(y_true_array, y_pred_array, labels=[0, 1]).ravel()

    return {
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "precision_at_100": float(y_true_array[top_indices].mean()) if top_k else 0.0,
        "recall_at_100": float(y_true_array[top_indices].sum() / positives) if positives else 0.0,
        "f1_score": float(f1_score(y_true_array, y_pred_array, zero_division=0)),
        "brier_score": brier,
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "threshold": 0.5,
        "support": {
            "positives": positives,
            "negatives": int(len(y_true_array) - positives),
            "n_rows": int(len(y_true_array)),
        },
    }


def feature_importance(model) -> List[dict]:
    estimator = model
    if hasattr(model, "named_steps"):
        estimator = model.named_steps["classifier"]

    if hasattr(estimator, "coef_"):
        weights = np.abs(np.asarray(estimator.coef_)[0])
    elif hasattr(estimator, "feature_importances_"):
        weights = np.asarray(estimator.feature_importances_)
    else:
        weights = np.zeros(len(FEATURE_COLUMNS), dtype=float)

    ranking = sorted(zip(FEATURE_COLUMNS, weights), key=lambda item: item[1], reverse=True)
    return [{"feature": feature, "importance": float(value)} for feature, value in ranking]


def serialize_model(path: Path, model) -> None:
    with path.open("wb") as handle:
        pickle.dump(model, handle)


def deserialize_model(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def build_dataset_summary(frame: pd.DataFrame, maturity_days: int) -> dict:
    timestamp_min = frame["timestamp"].min().isoformat()
    timestamp_max = frame["timestamp"].max().isoformat()
    class_counts = frame["is_fraud"].value_counts().to_dict()

    return {
        "maturity_days": maturity_days,
        "n_rows": int(len(frame)),
        "timestamp_range": {
            "start": timestamp_min,
            "end": timestamp_max,
        },
        "class_balance": {
            "fraud": int(class_counts.get(1, 0)),
            "non_fraud": int(class_counts.get(0, 0)),
            "fraud_rate": float(frame["is_fraud"].mean()),
        },
    }


def build_split_summary(train_frame: pd.DataFrame, validation_frame: pd.DataFrame, test_frame: pd.DataFrame) -> dict:
    return {
        "train_rows": int(len(train_frame)),
        "validation_rows": int(len(validation_frame)),
        "test_rows": int(len(test_frame)),
        "train_end_timestamp": train_frame["timestamp"].max().isoformat(),
        "validation_end_timestamp": validation_frame["timestamp"].max().isoformat(),
        "test_end_timestamp": test_frame["timestamp"].max().isoformat(),
    }


def create_model_artifact_report(model_name: str, model, validation_metrics: dict, test_metrics: dict) -> dict:
    return {
        "model_name": model_name,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "feature_importance": feature_importance(model),
    }


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return _feature_matrix(frame)


def target_frame(frame: pd.DataFrame) -> pd.Series:
    return _target_vector(frame)
