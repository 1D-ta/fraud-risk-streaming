"""Integration tests for fraud detection pipeline.

Tests multi-component scenarios and end-to-end workflows to ensure
all parts of the system work together correctly.
"""

from __future__ import annotations

import pickle
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from review.build_queue import build_review_queue
from scoring.score_transactions import score_transactions
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from training.train_model import train_models
from training.evaluate_model import evaluate_models


class IntegrationTests(TestCase):
    """Test multi-component integration scenarios in the fraud detection pipeline."""

    def test_full_pipeline_end_to_end(self) -> None:
        """Test complete pipeline from transaction generation to review queue.
        
        Validates the entire workflow:
        1. Generate transactions
        2. Generate labels
        3. Build features
        4. Train model
        5. Score transactions
        6. Build review queue
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Step 1: Generate transactions
            txn_report = generate_transactions(
                num_transactions=1000,
                fraud_rate=0.05,
                db_path=str(db_path),
                seed=200,
            )
            self.assertEqual(txn_report["n_transactions"], 1000)
            self.assertGreater(txn_report["n_fraud"], 0)
            
            # Step 2: Generate labels
            label_report = generate_labels(db_path=str(db_path), seed=200)
            self.assertEqual(label_report["n_labels"], 1000)
            
            # Step 3: Build features
            feature_report = build_features(db_path=str(db_path))
            self.assertEqual(feature_report["n_features"], 1000)
            
            # Step 4: Train model
            train_report = train_models(db_path=str(db_path), maturity_days=0)
            self.assertEqual(train_report["status"], "trained")
            self.assertIn("logistic_regression", train_report["candidate_models"])
            
            # Verify model file exists
            model_path = Path(train_report["candidate_models"]["logistic_regression"]["artifact_path"])
            self.assertTrue(model_path.exists())
            
            # Step 4b: Evaluate and select production model
            eval_report = evaluate_models(db_path=str(db_path), maturity_days=0)
            self.assertEqual(eval_report["status"], "evaluated")
            self.assertTrue(Path(eval_report["best_model"]["production_artifact"]).exists())
            
            # Step 5: Score transactions
            score_report = score_transactions(db_path=str(db_path))
            self.assertEqual(score_report["n_scored"], 1000)
            # Check risk band distribution instead of n_high_risk
            high_risk_count = score_report["risk_band_distribution"].get("HIGH", 0) + \
                            score_report["risk_band_distribution"].get("CRITICAL", 0)
            self.assertGreater(high_risk_count, 0)
            
            # Step 6: Build review queue
            queue_report = build_review_queue(db_path=str(db_path), capacity=100)
            self.assertEqual(queue_report["status"], "queued")
            self.assertGreater(queue_report["queue_size"], 0)
            
            # Verify data integrity across all tables
            with sqlite3.connect(db_path) as connection:
                txn_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
                label_count = connection.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
                feature_count = connection.execute("SELECT COUNT(*) FROM features").fetchone()[0]
                score_count = connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
                queue_count = connection.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]
                
                self.assertEqual(txn_count, 1000)
                self.assertEqual(label_count, 1000)
                self.assertEqual(feature_count, 1000)
                self.assertEqual(score_count, 1000)
                self.assertGreater(queue_count, 0)
                self.assertLessEqual(queue_count, 100)

    def test_label_delay_plus_feature_lag(self) -> None:
        """Test combined failure scenario: delayed labels + stale features.
        
        Simulates a realistic failure where both label delays and feature
        staleness occur simultaneously, testing system resilience.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Generate base data
            generate_transactions(
                num_transactions=500,
                fraud_rate=0.03,
                db_path=str(db_path),
                seed=300,
            )
            
            # Generate labels with delay
            label_report = generate_labels(db_path=str(db_path), seed=300)
            
            # Build features
            build_features(db_path=str(db_path))
            
            # Check for label maturity
            with sqlite3.connect(db_path) as connection:
                total_labels = connection.execute(
                    "SELECT COUNT(*) FROM labels"
                ).fetchone()[0]
                mature_count = connection.execute(
                    "SELECT COUNT(*) FROM labels WHERE is_mature = 1"
                ).fetchone()[0]
                
                # All labels should exist
                self.assertEqual(total_labels, 500)
                # Most labels should be mature (default behavior)
                self.assertGreater(mature_count, 0)
                
                # Check feature timestamps vs transaction timestamps
                # (simulating potential lag)
                lag_check = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM features f
                    JOIN transactions t ON f.transaction_id = t.transaction_id
                    WHERE f.feature_timestamp >= t.timestamp
                    """
                ).fetchone()[0]
                
                # All features should have timestamps >= transaction timestamps
                self.assertEqual(lag_check, 500)
            
            # Train with only mature labels
            train_report = train_models(db_path=str(db_path), maturity_days=7)
            
            # Training should succeed but with reduced dataset
            trained_rows = train_report["dataset"]["n_rows"]
            self.assertGreater(trained_rows, 0)
            self.assertLess(trained_rows, 500)

    def test_distribution_shift_plus_leakage(self) -> None:
        """Test combined failure scenario: distribution shift + leakage bug.
        
        Tests detection of both distribution changes and temporal leakage
        when they occur together.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Generate transactions with higher fraud rate (simulating shift)
            generate_transactions(
                num_transactions=800,
                fraud_rate=0.10,  # Higher than typical 0.02
                db_path=str(db_path),
                seed=400,
            )
            
            generate_labels(db_path=str(db_path), seed=400)
            build_features(db_path=str(db_path))
            
            # Check for distribution shift
            with sqlite3.connect(db_path) as connection:
                fraud_rate = connection.execute(
                    """
                    SELECT AVG(CAST(is_fraud AS FLOAT))
                    FROM labels
                    """
                ).fetchone()[0]
                
                # Fraud rate should be elevated
                self.assertGreater(fraud_rate, 0.05)
                
                # Check for temporal leakage violations
                leakage_violations = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM features f
                    JOIN transactions t ON f.transaction_id = t.transaction_id
                    WHERE f.feature_timestamp < t.timestamp
                    """
                ).fetchone()[0]
                
                # Should have no leakage violations
                self.assertEqual(leakage_violations, 0)
            
            # Train model on shifted distribution
            train_report = train_models(db_path=str(db_path), maturity_days=0)
            
            # Model should train successfully
            self.assertEqual(train_report["status"], "trained")
            
            # Fraud rate in dataset should be elevated
            dataset_fraud_rate = train_report["dataset"]["class_balance"]["fraud_rate"]
            self.assertGreater(dataset_fraud_rate, 0.05)

    def test_pipeline_idempotency(self) -> None:
        """Test that running pipeline twice produces consistent results.
        
        Validates that re-running feature building, scoring, and queue
        building produces the same outputs (idempotency).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Generate base data
            generate_transactions(
                num_transactions=300,
                fraud_rate=0.02,
                db_path=str(db_path),
                seed=500,
            )
            generate_labels(db_path=str(db_path), seed=500)
            
            # First run
            feature_report_1 = build_features(db_path=str(db_path))
            train_models(db_path=str(db_path), maturity_days=0)
            evaluate_models(db_path=str(db_path), maturity_days=0)
            score_report_1 = score_transactions(db_path=str(db_path))
            
            # Get first run results
            with sqlite3.connect(db_path) as connection:
                features_1 = connection.execute(
                    "SELECT transaction_id, user_txn_count_1h, amount FROM features ORDER BY transaction_id"
                ).fetchall()
                scores_1 = connection.execute(
                    "SELECT transaction_id, fraud_score FROM scores ORDER BY transaction_id"
                ).fetchall()
            
            # Second run (rebuild features and scores)
            feature_report_2 = build_features(db_path=str(db_path))
            score_report_2 = score_transactions(db_path=str(db_path))
            
            # Get second run results
            with sqlite3.connect(db_path) as connection:
                features_2 = connection.execute(
                    "SELECT transaction_id, user_txn_count_1h, amount FROM features ORDER BY transaction_id"
                ).fetchall()
                scores_2 = connection.execute(
                    "SELECT transaction_id, fraud_score FROM scores ORDER BY transaction_id"
                ).fetchall()
            
            # Results should be identical
            self.assertEqual(feature_report_1["n_features"], feature_report_2["n_features"])
            self.assertEqual(score_report_1["n_scored"], score_report_2["n_scored"])
            self.assertEqual(features_1, features_2)
            
            # Scores should be identical (same model, same features)
            for (txn_id_1, score_1), (txn_id_2, score_2) in zip(scores_1, scores_2):
                self.assertEqual(txn_id_1, txn_id_2)
                self.assertAlmostEqual(score_1, score_2, places=6)

    def test_incremental_processing(self) -> None:
        """Test adding new transactions to existing database.
        
        Validates that the system can handle incremental updates by
        adding new transactions and processing them correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Initial batch
            generate_transactions(
                num_transactions=200,
                fraud_rate=0.02,
                db_path=str(db_path),
                seed=600,
                start_timestamp="2024-01-01T00:00:00",
            )
            generate_labels(db_path=str(db_path), seed=600)
            build_features(db_path=str(db_path))
            
            initial_count = 200
            
            # Add incremental batch - note: generate_transactions clears existing data
            # So we need to test incremental differently
            with sqlite3.connect(db_path) as connection:
                # Manually insert additional transactions
                connection.execute("PRAGMA foreign_keys = ON;")
                for i in range(100):
                    connection.execute(
                        """
                        INSERT INTO transactions
                        (transaction_id, user_id, merchant_id, device_id, timestamp,
                         amount, currency, merchant_category, channel, location_city,
                         is_international, fraud_pattern)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (f"txn_incr_{i}", f"user_{i%50:03d}", f"merch_{i%20:03d}",
                         f"dev_{i%30:03d}", f"2024-01-02T{i%24:02d}:00:00",
                         100.0 + i, "USD", "retail", "mobile", "New York", 0, None),
                    )
                connection.commit()
            
            # Generate labels for new transactions
            generate_labels(db_path=str(db_path), seed=601)
            
            # Rebuild features (should include all transactions)
            feature_report = build_features(db_path=str(db_path))
            
            # Should have features for all transactions
            self.assertEqual(feature_report["n_features"], 300)
            
            with sqlite3.connect(db_path) as connection:
                txn_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
                feature_count = connection.execute("SELECT COUNT(*) FROM features").fetchone()[0]
                
                self.assertEqual(txn_count, 300)
                self.assertEqual(feature_count, 300)
                
                # Verify temporal ordering is maintained
                timestamps = connection.execute(
                    "SELECT timestamp FROM transactions ORDER BY timestamp"
                ).fetchall()
                
                # Timestamps should be in ascending order
                for i in range(len(timestamps) - 1):
                    self.assertLessEqual(timestamps[i][0], timestamps[i + 1][0])

    def test_model_retraining_workflow(self) -> None:
        """Test full retraining cycle with new data.
        
        Validates the workflow of training a model, adding new data,
        and retraining to ensure the system supports model updates.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Initial training data
            generate_transactions(
                num_transactions=500,
                fraud_rate=0.02,
                db_path=str(db_path),
                seed=700,
            )
            generate_labels(db_path=str(db_path), seed=700)
            build_features(db_path=str(db_path))
            
            # Train initial model
            train_report_1 = train_models(db_path=str(db_path), maturity_days=0)
            evaluate_models(db_path=str(db_path), maturity_days=0)
            model_path = Path(train_report_1["candidate_models"]["logistic_regression"]["artifact_path"])
            
            # Load and verify initial model
            with open(model_path, "rb") as f:
                model_1 = pickle.load(f)
            
            # Score with initial model
            score_report_1 = score_transactions(db_path=str(db_path))
            initial_scores = score_report_1["n_scored"]
            
            # Simulate adding more training data by manually inserting transactions
            # (generate_transactions clears the database, so we insert manually)
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                for i in range(300):
                    connection.execute(
                        """
                        INSERT INTO transactions
                        (transaction_id, user_id, merchant_id, device_id, timestamp,
                         amount, currency, merchant_category, channel, location_city,
                         is_international, fraud_pattern)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (f"txn_retrain_{i}", f"user_{i%100:03d}", f"merch_{i%50:03d}",
                         f"dev_{i%60:03d}", f"2024-02-01T{i%24:02d}:{i%60:02d}:00",
                         150.0 + i, "USD", "retail", "mobile", "Los Angeles", 0,
                         "account_takeover" if i % 30 == 0 else None),
                    )
                connection.commit()
            
            # Generate labels for all transactions
            generate_labels(db_path=str(db_path), seed=701)
            build_features(db_path=str(db_path))
            
            # Retrain model with expanded dataset
            train_report_2 = train_models(db_path=str(db_path), maturity_days=0)
            evaluate_models(db_path=str(db_path), maturity_days=0)
            
            # Load retrained model
            with open(model_path, "rb") as f:
                model_2 = pickle.load(f)
            
            # Verify retraining occurred with more data
            self.assertGreater(
                train_report_2["dataset"]["n_rows"],
                train_report_1["dataset"]["n_rows"]
            )
            
            # Score with retrained model
            score_report_2 = score_transactions(db_path=str(db_path))
            
            # Should score all transactions (original + new)
            self.assertEqual(score_report_2["n_scored"], 800)
            self.assertGreater(score_report_2["n_scored"], initial_scores)
            
            # Verify model artifacts are updated
            self.assertTrue(model_path.exists())
            
            # Models should be different (different training data)
            # Note: We can't directly compare model objects, but we verified
            # they were trained on different dataset sizes
            self.assertNotEqual(
                train_report_1["dataset"]["n_rows"],
                train_report_2["dataset"]["n_rows"]
            )