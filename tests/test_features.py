from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from features.check_leakage import check_leakage
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions


class FeatureEngineeringTests(TestCase):
    def test_build_features_populates_feature_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=31)
            generate_labels(db_path=str(db_path), seed=31)

            report = build_features(db_path=str(db_path))

            with sqlite3.connect(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM features").fetchone()[0]
                leakage_violations = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM features f
                    JOIN transactions t ON f.transaction_id = t.transaction_id
                    WHERE f.feature_timestamp > t.timestamp
                    """
                ).fetchone()[0]
                feature_frame = connection.execute(
                    "SELECT user_txn_count_24h, user_amount_sum_7d, merchant_fraud_rate_30d, amount_zscore, hour_of_day, is_first_merchant FROM features"
                ).fetchall()

            self.assertEqual(count, 1_000)
            self.assertEqual(report["n_features"], 1_000)
            self.assertEqual(leakage_violations, 0)
            self.assertTrue(all(0 <= row[4] <= 23 for row in feature_frame))
            self.assertTrue(all(row[5] in (0, 1) for row in feature_frame))
            self.assertTrue(all(row[0] >= 0 for row in feature_frame))
            self.assertTrue(all(row[1] >= 0 for row in feature_frame))
            self.assertTrue(all(0.0 <= row[2] <= 1.0 for row in feature_frame))

    def test_check_leakage_writes_pass_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            generate_transactions(num_transactions=500, fraud_rate=0.02, db_path=str(db_path), seed=41)
            generate_labels(db_path=str(db_path), seed=41)
            build_features(db_path=str(db_path))

            report = check_leakage(db_path=str(db_path))

            self.assertEqual(report["leakage_check"], "PASS")
            self.assertEqual(report["violations"], 0)
