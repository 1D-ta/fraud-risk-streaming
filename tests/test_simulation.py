from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from simulation.generate_transactions import generate_transactions
from simulation.init_db import init_database


class SimulationTests(TestCase):
    def test_init_database_creates_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))

            with sqlite3.connect(db_path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }

            self.assertTrue({"transactions", "labels", "features", "scores", "review_queue"}.issubset(tables))

    def test_generate_transactions_populates_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            report = generate_transactions(
                num_transactions=500,
                fraud_rate=0.02,
                db_path=str(db_path),
                seed=7,
            )

            with sqlite3.connect(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
                fraud_count = connection.execute("SELECT COUNT(*) FROM transactions WHERE fraud_pattern IS NOT NULL").fetchone()[0]

            self.assertEqual(report["n_transactions"], 500)
            self.assertEqual(report["n_fraud"], 10)
            self.assertEqual(count, 500)
            self.assertEqual(fraud_count, 10)
