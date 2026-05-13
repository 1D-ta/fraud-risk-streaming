"""Structured logging configuration for the fraud-risk-streaming system."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional


def configure_logging(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    json_format: bool = False,
) -> logging.Logger:
    """Configure a logger with file and console handlers.
    
    Args:
        name: Logger name (typically __name__)
        log_file: Optional path to log file
        level: Logging level (default: INFO)
        json_format: If True, output JSON format (for artifacts)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if json_format:
        console_formatter = logging.Formatter('%(message)s')
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_structured(data: dict, logger: logging.Logger) -> None:
    """Log structured data as JSON.
    
    Args:
        data: Dictionary to log as JSON
        logger: Logger instance
    """
    logger.info(json.dumps(data))


def create_artifact_logger(artifact_name: str, output_path: Path) -> logging.Logger:
    """Create a logger for writing artifact data.
    
    Args:
        artifact_name: Name of the artifact (e.g., 'transaction_stats')
        output_path: Path to the output file
        
    Returns:
        Configured logger instance
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"artifact.{artifact_name}")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    handler = logging.FileHandler(output_path)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    
    return logger
