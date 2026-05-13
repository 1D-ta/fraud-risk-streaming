from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from monitoring.drift_detection import drift_report
from monitoring.performance_tracker import performance_report
from review.build_queue import build_review_queue
from scoring.score_transactions import score_transactions
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from training.evaluate_model import evaluate_models
from training.train_model import train_models


class MonitoringTests(TestCase):
    def test_monitoring_reports_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                db_path = Path(tmpdir) / "fraud_risk.db"
                generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=71)
                generate_labels(db_path=str(db_path), seed=71)
                build_features(db_path=str(db_path))
                train_models(db_path=str(db_path))
                evaluate_models(db_path=str(db_path))
                score_transactions(db_path=str(db_path))
                build_review_queue(db_path=str(db_path), capacity=100)

                drift = drift_report(db_path=str(db_path))
                perf = performance_report(db_path=str(db_path), top_k=100)

                self.assertIn("score_psi", drift)
                self.assertIn("pr_auc", perf)
                self.assertTrue((Path("artifacts/reports/drift_report.json")).exists())
                self.assertTrue((Path("artifacts/reports/performance_metrics.json")).exists())
                self.assertTrue((Path("artifacts/reports/monitoring_dashboard.html")).exists())
            finally:
                os.chdir(original_cwd)
