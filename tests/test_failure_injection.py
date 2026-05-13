from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from features.check_leakage import check_leakage
from scripts.failure_injection.inject_distribution_shift import inject_distribution_shift
from scripts.failure_injection.inject_feature_lag import inject_feature_lag
from scripts.failure_injection.inject_label_delay import inject_label_delay_spike
from scripts.failure_injection.inject_leakage import inject_leakage_bug
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions


class FailureInjectionTests(TestCase):
    def test_failure_reports_and_incidents(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                db_path = Path(tmpdir) / "fraud_risk.db"
                generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=91)
                generate_labels(db_path=str(db_path), seed=91)
                build_features(db_path=str(db_path))

                label_delay = inject_label_delay_spike(db_path=str(db_path), seed=91)
                feature_lag = inject_feature_lag(db_path=str(db_path), lag_days=3)
                distribution_shift = inject_distribution_shift(db_path=str(db_path), amount_multiplier=10.0)
                leakage = inject_leakage_bug(db_path=str(db_path))

                self.assertEqual(label_delay["failure_type"], "label_delay_spike")
                self.assertEqual(feature_lag["failure_type"], "feature_lag")
                self.assertEqual(distribution_shift["failure_type"], "distribution_shift")
                self.assertEqual(leakage["failure_type"], "leakage_bug")

                self.assertTrue((Path("artifacts/reports/failure_label_delay.json")).exists())
                self.assertTrue((Path("artifacts/reports/failure_feature_lag.json")).exists())
                self.assertTrue((Path("artifacts/reports/failure_distribution_shift.json")).exists())
                self.assertTrue((Path("artifacts/reports/failure_leakage.json")).exists())

                incident_path = repo_root / "INCIDENTS.md"
                self.assertTrue(incident_path.exists())
                incident_text = incident_path.read_text(encoding="utf-8")
                self.assertIn("Incident 1: Label Delay Spike", incident_text)
                self.assertIn("Incident 2: Feature Lag", incident_text)
                self.assertIn("Incident 3: Distribution Shift", incident_text)
                self.assertIn("Incident 4: Label Leakage", incident_text)

                leakage_check = check_leakage(db_path=str(db_path))
                self.assertEqual(leakage_check["leakage_check"], "PASS")
            finally:
                os.chdir(original_cwd)