"""Database utilities for the fraud-risk-streaming system."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from fraud_risk.config import DB_PATH


@contextmanager
def get_connection(db_path: str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with foreign keys enabled.
    
    Args:
        db_path: Path to the SQLite database file
        
    Yields:
        sqlite3.Connection with foreign keys enabled
    """
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    try:
        yield connection
    finally:
        connection.close()


def ensure_db_initialized(db_path: str = DB_PATH) -> None:
    """Ensure database file exists and is readable.
    
    Args:
        db_path: Path to the SQLite database file
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}. Run 'make init-db' first.")


def get_table_info(table_name: str, db_path: str = DB_PATH) -> dict:
    """Get schema information for a table.
    
    Args:
        table_name: Name of the table
        db_path: Path to the SQLite database file
        
    Returns:
        Dictionary with column information
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return {
            col[1]: {"type": col[2], "notnull": col[3], "default": col[4], "pk": col[5]}
            for col in columns
        }


def verify_schema(db_path: str = DB_PATH) -> dict:
    """Verify database schema is valid.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Dictionary with table verification results
    """
    ensure_db_initialized(db_path)
    
    required_tables = {
        "transactions": ["transaction_id", "user_id", "merchant_id", "device_id", "timestamp"],
        "labels": ["transaction_id", "is_fraud", "label_timestamp", "label_source", "is_mature"],
        "features": ["transaction_id", "feature_timestamp"],
        "scores": ["transaction_id", "fraud_score", "score_timestamp", "decision", "model_version"],
        "review_queue": ["transaction_id", "review_batch_id", "fraud_score", "review_rank", "capacity_limit"],
    }
    
    results = {}
    with get_connection(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table_name, required_columns in required_tables.items():
            if table_name not in existing_tables:
                results[table_name] = {"valid": False, "error": "Table does not exist"}
            else:
                table_info = get_table_info(table_name, db_path)
                missing_columns = [col for col in required_columns if col not in table_info]
                if missing_columns:
                    results[table_name] = {
                        "valid": False,
                        "error": f"Missing columns: {missing_columns}"
                    }
                else:
                    results[table_name] = {"valid": True}
    
    return results
