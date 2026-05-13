from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from features.build_features import build_features
from training.evaluate_model import evaluate_models
from training.train_model import train_models


class TrainingTests(TestCase):
    def test_training_pipeline_creates_model_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                db_path = Path(tmpdir) / "fraud_risk.db"
                generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=51)
                generate_labels(db_path=str(db_path), seed=51)
                build_features(db_path=str(db_path))

                train_report = train_models(db_path=str(db_path))
                evaluation_report = evaluate_models(db_path=str(db_path))

                self.assertEqual(train_report["status"], "trained")
                self.assertEqual(evaluation_report["status"], "evaluated")
                self.assertIn("best_model", evaluation_report)
                self.assertTrue((Path("artifacts/models/logistic_regression.pkl")).exists())
                self.assertTrue((Path("artifacts/models/gradient_boosting.pkl")).exists())
                self.assertTrue((Path("artifacts/models/production_model.pkl")).exists())
                self.assertTrue((Path("artifacts/models/fraud_model_v1.pkl")).exists())
                self.assertTrue((Path("artifacts/reports/training_report_v1.json")).exists())
                self.assertTrue((Path("artifacts/reports/evaluation.json")).exists())
                self.assertGreaterEqual(evaluation_report["models"][evaluation_report["best_model"]["name"]]["validation"]["pr_auc"], 0.0)
            finally:
                os.chdir(original_cwd)
