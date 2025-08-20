import re
from typing import Any


def safe_filename(s: str) -> str:
    """
    Sanitizes a string into a valid filename.

    Args:
        s: The string to sanitize.

    Returns:
        The sanitized string.
    """
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)


def normalize_title(title: Any) -> str:
    """
    Converts a message title entity to a string.

    Args:
        title: The title entity to convert.

    Returns:
        The title as a string.
    """
    try:
        return title.text if hasattr(title, "text") else str(title)
    except Exception:
        return "UnknownTopic"
