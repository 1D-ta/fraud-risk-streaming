"""Time utilities for the fraud-risk-streaming system."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Union


def parse_timestamp(timestamp: Union[str, datetime]) -> datetime:
    """Parse a timestamp string or return datetime as-is.
    
    Args:
        timestamp: ISO format string or datetime object
        
    Returns:
        datetime object
    """
    if isinstance(timestamp, datetime):
        return timestamp
    if isinstance(timestamp, str):
        return datetime.fromisoformat(timestamp)
    raise TypeError(f"Expected str or datetime, got {type(timestamp)}")


def format_timestamp(dt: Union[str, datetime]) -> str:
    """Format datetime to ISO format string.
    
    Args:
        dt: datetime object or ISO string
        
    Returns:
        ISO format string (YYYY-MM-DDTHH:MM:SS)
    """
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.isoformat()
    raise TypeError(f"Expected str or datetime, got {type(dt)}")


def get_window_boundary(reference_time: Union[str, datetime], window_seconds: int) -> datetime:
    """Calculate the start time for a time window.
    
    Args:
        reference_time: Reference time (e.g., transaction timestamp)
        window_seconds: Window size in seconds
        
    Returns:
        Datetime representing the window start
    """
    ref_dt = parse_timestamp(reference_time)
    return ref_dt - timedelta(seconds=window_seconds)


def hours_between(start: Union[str, datetime], end: Union[str, datetime]) -> float:
    """Calculate hours between two timestamps.
    
    Args:
        start: Start timestamp
        end: End timestamp
        
    Returns:
        Number of hours between start and end
    """
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)
    return (end_dt - start_dt).total_seconds() / 3600.0


def days_between(start: Union[str, datetime], end: Union[str, datetime]) -> float:
    """Calculate days between two timestamps.
    
    Args:
        start: Start timestamp
        end: End timestamp
        
    Returns:
        Number of days between start and end
    """
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)
    return (end_dt - start_dt).total_seconds() / 86400.0


def is_weekend(dt: Union[str, datetime]) -> int:
    """Check if datetime is on a weekend (Saturday=5, Sunday=6 in Python's weekday).
    
    Args:
        dt: datetime object or ISO string
        
    Returns:
        1 if weekend, 0 otherwise
    """
    dt_obj = parse_timestamp(dt)
    return 1 if dt_obj.weekday() >= 5 else 0


def get_hour_of_day(dt: Union[str, datetime]) -> int:
    """Get hour of day (0-23).
    
    Args:
        dt: datetime object or ISO string
        
    Returns:
        Hour of day (0-23)
    """
    dt_obj = parse_timestamp(dt)
    return dt_obj.hour
