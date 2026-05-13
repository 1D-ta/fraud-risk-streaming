"""Compute Population Stability Index (PSI) for features and scores."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from training.common import FEATURE_COLUMNS


def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected)
    actual = np.asarray(actual)
    if expected.size == 0 or actual.size == 0:
        return 0.0

    # bin edges from expected percentiles
    try:
        breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    except Exception:
        return 0.0

    eps = 1e-6
    exp_perc = np.histogram(expected, bins=breakpoints)[0].astype(float)
    act_perc = np.histogram(actual, bins=breakpoints)[0].astype(float)

    # convert to proportions
    exp_perc = np.clip(exp_perc / exp_perc.sum(), eps, 1.0)
    act_perc = np.clip(act_perc / act_perc.sum(), eps, 1.0)

    psi_values = (exp_perc - act_perc) * np.log(exp_perc / act_perc)
    return float(np.sum(psi_values))


def drift_report(db_path: str = "data/fraud_risk.db") -> Dict[str, float]:
    with sqlite3.connect(db_path) as conn:
        features = pd.read_sql_query("SELECT * FROM features ORDER BY feature_timestamp, transaction_id", conn, parse_dates=["feature_timestamp"])  # type: ignore[arg-type]
        scores = pd.read_sql_query("SELECT * FROM scores ORDER BY score_timestamp, transaction_id", conn, parse_dates=["score_timestamp"])  # type: ignore[arg-type]

    if features.empty:
        raise ValueError("No features found. Run feature builder first.")

    # baseline: first 70% of feature rows
    n = len(features)
    split = max(1, int(n * 0.7))
    baseline = features.iloc[:split]
    recent = features.iloc[split:]

    report: Dict[str, float] = {}

    for col in FEATURE_COLUMNS:
        if col not in features.columns:
            report[col + "_psi"] = 0.0
            continue
        try:
            val = _psi(baseline[col].to_numpy(dtype=float), recent[col].to_numpy(dtype=float), bins=10)
        except Exception:
            val = 0.0
        report[col + "_psi"] = val

    # score drift if scores present
    if not scores.empty and "score" in scores.columns:
        # align scores by transaction order
        score_vals = scores["score"].to_numpy(dtype=float)
        mid = max(1, int(len(score_vals) * 0.7))
        report["score_psi"] = _psi(score_vals[:mid], score_vals[mid:], bins=10)
    else:
        report["score_psi"] = 0.0

    report_path = Path("artifacts/reports/drift_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main() -> None:
    report = drift_report()
    print("Drift report written to artifacts/reports/drift_report.json")
    print(report)


if __name__ == "__main__":
    main()
