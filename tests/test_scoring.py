from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from review.build_queue import build_review_queue
from scoring.score_transactions import score_transactions
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from training.evaluate_model import evaluate_models
from training.train_model import train_models


class ScoringTests(TestCase):
    def test_scoring_and_review_queue_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                db_path = Path(tmpdir) / "fraud_risk.db"
                generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=61)
                generate_labels(db_path=str(db_path), seed=61)
                build_features(db_path=str(db_path))
                train_models(db_path=str(db_path))
                evaluate_models(db_path=str(db_path))

                scoring_report = score_transactions(db_path=str(db_path))
                queue_report = build_review_queue(db_path=str(db_path), capacity=100)

                self.assertEqual(scoring_report["status"], "scored")
                self.assertEqual(queue_report["status"], "queued")
                self.assertEqual(scoring_report["n_scored"], 1_000)
                self.assertLessEqual(queue_report["queue_size"], 100)
                self.assertGreaterEqual(queue_report["total_high_risk"], queue_report["queue_size"])
                self.assertTrue((Path("artifacts/reports/scoring_stats.json")).exists())
                self.assertTrue((Path("artifacts/reports/review_queue_stats.json")).exists())
            finally:
                os.chdir(original_cwd)
