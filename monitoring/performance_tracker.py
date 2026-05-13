"""Compute performance metrics and monitor model performance over time."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict
from html import escape

import numpy as np
import pandas as pd
from sklearn.metrics import auc, precision_recall_curve


def performance_report(db_path: str = "data/fraud_risk.db", top_k: int = 100) -> Dict[str, float]:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT t.transaction_id, t.timestamp, l.is_fraud, s.fraud_score
            FROM transactions t
            JOIN labels l ON t.transaction_id = l.transaction_id
            JOIN scores s ON t.transaction_id = s.transaction_id
            ORDER BY t.timestamp, t.transaction_id
            """,
            conn,
            parse_dates=["timestamp"],
        )

    if df.empty:
        raise ValueError("No labeled scored transactions available. Run scoring and label backfill first.")

    y_true = df["is_fraud"].astype(int)
    y_score = df["fraud_score"].astype(float)

    results: Dict[str, float] = {}

    if len(np.unique(y_true)) > 1:
        precision, recall, _ = precision_recall_curve(y_true, y_score)
        pr_auc = float(auc(recall, precision))
    else:
        pr_auc = 0.0

    results["pr_auc"] = pr_auc

    # Precision@top_k
    top_k = min(top_k, len(df))
    top_indices = np.argsort(y_score.values)[-top_k:]
    precision_at_k = float(y_true.iloc[top_indices].mean()) if top_k > 0 else 0.0
    results["precision_at_{}".format(top_k)] = precision_at_k

    # Basic score stats
    results["score_mean"] = float(y_score.mean())
    results["score_std"] = float(y_score.std(ddof=0))
    results["n_scored_labeled"] = int(len(df))

    report_path = Path("artifacts/reports/performance_metrics.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    _write_dashboard(report_path=report_path, performance=results)

    return results


def _format_metric_rows(metrics: Dict[str, float]) -> str:
    rows = []
    for key, value in metrics.items():
        rows.append(f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>")
    return "\n".join(rows)


def _write_dashboard(report_path: Path, performance: Dict[str, float]) -> None:
        drift_path = report_path.with_name("drift_report.json")
        drift_metrics: Dict[str, float] = {}
        if drift_path.exists():
                drift_metrics = json.loads(drift_path.read_text(encoding="utf-8"))

        dashboard_path = report_path.with_name("monitoring_dashboard.html")
        dashboard_html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Fraud Risk Streaming Monitoring Dashboard</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f7f5ef;
            --panel: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --accent: #0f766e;
            --border: #d9d4c7;
        }}
        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(180deg, #fbfaf7 0%, var(--bg) 100%);
            color: var(--text);
        }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 48px; }}
        h1 {{ margin: 0 0 8px; font-size: 2rem; }}
        p {{ color: var(--muted); line-height: 1.5; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin-top: 24px; }}
        .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 18px; box-shadow: 0 10px 24px rgba(17, 24, 39, 0.06); }}
        .card h2 {{ margin: 0 0 12px; font-size: 1.05rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px 0; border-bottom: 1px solid #ece8df; vertical-align: top; }}
        td:first-child {{ color: var(--muted); width: 65%; }}
        .status {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(15, 118, 110, 0.12); color: var(--accent); font-weight: 600; }}
    </style>
</head>
<body>
    <div class="wrap">
        <h1>Fraud Risk Streaming Monitoring Dashboard</h1>
        <p>Combined drift and performance snapshot generated from the latest scoring run.</p>
        <span class="status">Updated from artifacts/reports</span>
        <div class="grid">
            <section class="card">
                <h2>Performance</h2>
                <table>
                    <tbody>
                        {_format_metric_rows(performance)}
                    </tbody>
                </table>
            </section>
            <section class="card">
                <h2>Drift</h2>
                <table>
                    <tbody>
                        {_format_metric_rows(drift_metrics or {"status": "drift report not available"})}
                    </tbody>
                </table>
            </section>
        </div>
    </div>
</body>
</html>
"""

        dashboard_path.write_text(dashboard_html, encoding="utf-8")


def main() -> None:
    report = performance_report()
    print("Performance report written to artifacts/reports/performance_metrics.json")
    print(report)


if __name__ == "__main__":
    main()
