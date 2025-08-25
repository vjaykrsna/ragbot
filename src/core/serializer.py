"""
Data serialization utilities for the application.

This module handles serialization and deserialization of data to/from
database storage formats.
"""

import json
from datetime import datetime
from typing import Any, Dict


def serialize_extra_data(extra_data: Dict[str, Any]) -> str:
    """Serialize extra_data dictionary to JSON string, handling datetime objects."""
    # Handle None case
    if extra_data is None:
        return "{}"

    # Handle non-dict cases
    if not isinstance(extra_data, dict):
        # Try to convert to dict if it's a string representation of a dict
        if isinstance(extra_data, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(extra_data)
                if isinstance(parsed, dict):
                    extra_data = parsed
                else:
                    # If it's not a dict after parsing, convert to string
                    return json.dumps({"value": extra_data})
            except json.JSONDecodeError:
                # If it's not valid JSON, convert to string
                return json.dumps({"value": extra_data})
        else:
            # If it's not a dict and not a string, convert to string
            return json.dumps({"value": str(extra_data)})

    # At this point, extra_data should be a dict
    # Create a copy of the dictionary to avoid modifying the original
    serializable_data = {}
    for key, value in extra_data.items():
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        else:
            # Handle non-serializable objects
            try:
                json.dumps(value)  # Test if value is JSON serializable
                serializable_data[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string
                serializable_data[key] = str(value)

    return json.dumps(serializable_data)


def deserialize_extra_data(extra_data_str: str) -> Dict[str, Any]:
    """Deserialize extra_data from JSON string back to dict."""
    if extra_data_str:
        try:
            return json.loads(extra_data_str)
        except (json.JSONDecodeError, TypeError):
            # If deserialization fails, return as is or empty dict
            pass
    return {}


def serialize_content(content: Any) -> str:
    """Serialize content to string for database storage."""
    if isinstance(content, str):
        return content

    try:
        return json.dumps(content)
    except (TypeError, ValueError):
        # If content is not JSON serializable, convert to string
        return str(content)


def serialize_date(date_value: Any) -> str:
    """Serialize date field to string for database storage."""
    if isinstance(date_value, str):
        return date_value

    # Handle datetime objects
    if hasattr(date_value, "isoformat"):
        return date_value.isoformat()

    # Handle timestamp objects
    if hasattr(date_value, "timestamp"):
        return datetime.fromtimestamp(date_value.timestamp()).isoformat()

    # Handle other non-serializable objects
    try:
        json.dumps(date_value)  # Test if value is JSON serializable
        # If it is, convert to string
        return str(date_value)
    except (TypeError, ValueError):
        # If not serializable, convert to string
        return str(date_value)
