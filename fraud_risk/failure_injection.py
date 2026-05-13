"""Shared helpers for failure injection scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REPORT_DIR = Path("artifacts/reports")


def ensure_report_dir() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def write_report(filename: str, payload: Dict[str, Any]) -> Path:
    report_path = ensure_report_dir() / filename
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path