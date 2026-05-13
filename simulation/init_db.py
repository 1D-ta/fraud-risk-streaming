"""Initialize the fraud-risk SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def init_database(db_path: str = "data/fraud_risk.db") -> str:
    """Initialize the SQLite database using the project schema."""

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).resolve().parent.parent / "data" / "schemas" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(schema_sql)

    return str(db_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the fraud-risk SQLite database.")
    parser.add_argument("--db-path", default="data/fraud_risk.db", help="Path to the SQLite database file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = init_database(args.db_path)
    print(f"Initialized SQLite database at {db_path}")


if __name__ == "__main__":
    main()
