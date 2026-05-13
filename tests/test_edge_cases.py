"""Edge case tests for fraud detection pipeline.

Tests boundary conditions, extreme values, and error handling scenarios
to ensure robustness of the fraud detection system.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from features.build_features import build_features
from simulation.generate_labels import generate_labels
from simulation.generate_transactions import generate_transactions
from simulation.init_db import init_database


class EdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions in the fraud detection pipeline."""

    def test_zero_transactions_in_window(self) -> None:
        """Test feature calculation when no historical transactions exist.
        
        Validates that the first transaction for a user/merchant has zero
        historical features (counts, averages) and doesn't cause errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Generate minimal transactions (just 1 per user)
            generate_transactions(
                num_transactions=10,
                fraud_rate=0.0,
                db_path=str(db_path),
                seed=100,
            )
            
            report = build_features(db_path=str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                # Check that features were built
                count = connection.execute("SELECT COUNT(*) FROM features").fetchone()[0]
                self.assertEqual(count, 10)
                
                # Verify first transactions have zero historical counts
                first_features = connection.execute(
                    """
                    SELECT user_txn_count_1h, user_txn_count_24h, 
                           user_avg_amount_7d, merchant_txn_count_1h
                    FROM features
                    ORDER BY feature_timestamp
                    LIMIT 5
                    """
                ).fetchall()
                
                # At least some early transactions should have zero history
                zero_history_count = sum(
                    1 for f in first_features 
                    if f[0] == 0 and f[1] == 0 and f[2] == 0.0 and f[3] == 0
                )
                self.assertGreater(zero_history_count, 0, "Expected some transactions with zero history")

    def test_extreme_amounts(self) -> None:
        """Test handling of very high amounts (e.g., $1M+) and very low amounts (e.g., $0.01).
        
        Ensures the system can handle edge cases in transaction amounts without
        overflow, underflow, or division by zero errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                
                # Insert transactions with extreme amounts
                extreme_transactions = [
                    ("txn_tiny", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:00:00", 0.01, "USD", "retail", "mobile", 
                     "New York", 0, None),
                    ("txn_huge", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:01:00", 1500000.00, "USD", "retail", "mobile", 
                     "New York", 0, None),
                    ("txn_normal", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:02:00", 50.00, "USD", "retail", "mobile", 
                     "New York", 0, None),
                ]
                
                connection.executemany(
                    """
                    INSERT INTO transactions 
                    (transaction_id, user_id, merchant_id, device_id, timestamp, 
                     amount, currency, merchant_category, channel, location_city, 
                     is_international, fraud_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    extreme_transactions,
                )
                connection.commit()
            
            # Build features - should not crash
            report = build_features(db_path=str(db_path))
            self.assertEqual(report["n_features"], 3)
            
            with sqlite3.connect(db_path) as connection:
                # Verify z-score calculation handles extreme values
                features = connection.execute(
                    """
                    SELECT transaction_id, amount, user_amount_zscore_7d, 
                           user_avg_amount_7d
                    FROM features
                    ORDER BY feature_timestamp
                    """
                ).fetchall()
                
                # Check that amounts are preserved correctly
                self.assertAlmostEqual(features[0][1], 0.01, places=2)
                self.assertAlmostEqual(features[1][1], 1500000.00, places=2)
                self.assertAlmostEqual(features[2][1], 50.00, places=2)
                
                # Z-scores should be finite (not NaN or Inf)
                for f in features:
                    self.assertTrue(abs(f[2]) < 1e10, f"Z-score too large: {f[2]}")

    def test_missing_values(self) -> None:
        """Test handling of NULL/missing values in optional fields.
        
        Validates that the system properly handles missing fraud_pattern
        (which is optional) without errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                
                # Insert transaction with NULL fraud_pattern
                connection.execute(
                    """
                    INSERT INTO transactions 
                    (transaction_id, user_id, merchant_id, device_id, timestamp, 
                     amount, currency, merchant_category, channel, location_city, 
                     is_international, fraud_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("txn_001", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:00:00", 100.00, "USD", "retail", "mobile", 
                     "New York", 0, None),
                )
                connection.commit()
            
            # Should build features without error
            report = build_features(db_path=str(db_path))
            self.assertEqual(report["n_features"], 1)

    def test_duplicate_transaction_ids(self) -> None:
        """Test that duplicate transaction IDs are properly handled/rejected.
        
        Ensures database constraints prevent duplicate transaction IDs,
        maintaining data integrity.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                
                # Insert first transaction
                connection.execute(
                    """
                    INSERT INTO transactions 
                    (transaction_id, user_id, merchant_id, device_id, timestamp, 
                     amount, currency, merchant_category, channel, location_city, 
                     is_international, fraud_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("txn_duplicate", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:00:00", 100.00, "USD", "retail", "mobile", 
                     "New York", 0, None),
                )
                connection.commit()
                
                # Attempt to insert duplicate transaction_id - should fail
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO transactions 
                        (transaction_id, user_id, merchant_id, device_id, timestamp, 
                         amount, currency, merchant_category, channel, location_city, 
                         is_international, fraud_pattern)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("txn_duplicate", "user_002", "merch_002", "dev_002", 
                         "2024-01-01T11:00:00", 200.00, "USD", "food", "web", 
                         "Los Angeles", 0, None),
                    )

    def test_future_timestamps(self) -> None:
        """Test that future-dated transactions are handled appropriately.
        
        While the system doesn't explicitly reject future timestamps,
        this test validates that they don't break feature calculation.
        Uses generate_transactions with a future start time.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            
            # Generate transactions with future timestamp
            future_time = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")
            
            generate_transactions(
                num_transactions=10,
                fraud_rate=0.0,
                db_path=str(db_path),
                seed=800,
                start_timestamp=future_time,
            )
            
            # Should build features without error
            report = build_features(db_path=str(db_path))
            self.assertEqual(report["n_features"], 10)
            
            with sqlite3.connect(db_path) as connection:
                # Verify timestamps are in the future
                timestamps = connection.execute(
                    "SELECT feature_timestamp FROM features ORDER BY feature_timestamp LIMIT 1"
                ).fetchone()[0]
                self.assertIsNotNone(timestamps)

    def test_negative_amounts(self) -> None:
        """Test that negative amounts are rejected by database constraints.
        
        Validates that the CHECK constraint on amount > 0 is enforced,
        preventing invalid transaction amounts.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                
                # Attempt to insert transaction with negative amount - should fail
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO transactions 
                        (transaction_id, user_id, merchant_id, device_id, timestamp, 
                         amount, currency, merchant_category, channel, location_city, 
                         is_international, fraud_pattern)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("txn_negative", "user_001", "merch_001", "dev_001", 
                         "2024-01-01T10:00:00", -50.00, "USD", "retail", "mobile", 
                         "New York", 0, None),
                    )

    def test_empty_database(self) -> None:
        """Test pipeline behavior with empty database.
        
        Ensures that attempting to build features on an empty database
        raises an appropriate error rather than crashing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            # Attempt to build features on empty database - should raise ValueError
            with self.assertRaises(ValueError) as context:
                build_features(db_path=str(db_path))
            
            self.assertIn("No transactions found", str(context.exception))

    def test_single_transaction(self) -> None:
        """Test feature calculation with only one transaction.
        
        Validates that the system handles the minimal case of a single
        transaction without errors, with all historical features being zero.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fraud_risk.db"
            init_database(str(db_path))
            
            with sqlite3.connect(db_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON;")
                
                # Insert single transaction
                connection.execute(
                    """
                    INSERT INTO transactions 
                    (transaction_id, user_id, merchant_id, device_id, timestamp, 
                     amount, currency, merchant_category, channel, location_city, 
                     is_international, fraud_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("txn_single", "user_001", "merch_001", "dev_001", 
                     "2024-01-01T10:00:00", 100.00, "USD", "retail", "mobile", 
                     "New York", 0, None),
                )
                connection.commit()
            
            # Build features
            report = build_features(db_path=str(db_path))
            self.assertEqual(report["n_features"], 1)
            
            with sqlite3.connect(db_path) as connection:
                # Verify all historical features are zero
                features = connection.execute(
                    """
                    SELECT user_txn_count_1h, user_txn_count_24h, 
                           user_avg_amount_7d, user_amount_zscore_7d,
                           user_unique_merchants_24h, merchant_txn_count_1h,
                           device_user_count_24h, is_new_device_for_user,
                           city_change_flag_24h
                    FROM features
                    WHERE transaction_id = ?
                    """,
                    ("txn_single",),
                ).fetchone()
                
                # All historical counts should be zero
                self.assertEqual(features[0], 0)  # user_txn_count_1h
                self.assertEqual(features[1], 0)  # user_txn_count_24h
                self.assertEqual(features[2], 0.0)  # user_avg_amount_7d
                self.assertEqual(features[3], 0.0)  # user_amount_zscore_7d
                self.assertEqual(features[4], 0)  # user_unique_merchants_24h
                self.assertEqual(features[5], 0)  # merchant_txn_count_1h
                self.assertEqual(features[6], 0)  # device_user_count_24h
                self.assertEqual(features[7], 1)  # is_new_device_for_user (should be 1)
                self.assertEqual(features[8], 0)  # city_change_flag_24h

# Made with Bob
