from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions


class LabelGenerationTests(TestCase):
    def test_generate_labels_populates_delayed_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            generate_transactions(num_transactions=1_000, fraud_rate=0.02, db_path=str(db_path), seed=11)

            report = generate_labels(db_path=str(db_path), seed=11)

            with sqlite3.connect(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
                min_delay, max_delay, avg_delay = connection.execute(
                    "SELECT MIN(delay_days), MAX(delay_days), AVG(delay_days) FROM labels"
                ).fetchone()
                violations = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM transactions t
                    JOIN labels l ON t.transaction_id = l.transaction_id
                    WHERE l.label_timestamp <= t.timestamp
                    """
                ).fetchone()[0]

            self.assertEqual(count, 1_000)
            self.assertGreaterEqual(min_delay, 3.0)
            self.assertLessEqual(max_delay, 7.0)
            self.assertGreaterEqual(avg_delay, 4.5)
            self.assertLessEqual(avg_delay, 5.5)
            self.assertEqual(violations, 0)
            self.assertEqual(report["n_labels"], 1_000)

    def test_analyze_maturity_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            generate_transactions(num_transactions=500, fraud_rate=0.02, db_path=str(db_path), seed=21)
            generate_labels(db_path=str(db_path), seed=21)

            from simulation.analyze_maturity import analyze_maturity

            report = analyze_maturity(db_path=str(db_path), maturity_days=7)

            self.assertIn("maturity_rate", report)
            self.assertEqual(report["total_transactions"], 500)
