"""
Shared text utilities for the RAG Telegram Bot.

This module contains utility functions that are used across multiple modules
to avoid code duplication and ensure consistency.
"""

import re
from typing import Any, Dict, List

# Compile the regex pattern for number normalization
NUMBER_RE = re.compile(
    r"(?P<number>\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\b)\s*(?P<unit>%|percent\b|rs\b|inr\b|₹|km\b|m\b|kg\b|k\b|lakh\b|crore\b|million\b|billion\b)?",
    re.IGNORECASE,
)


def normalize_numbers(text: str) -> List[Dict[str, Any]]:
    """
    Extracts simple numeric facts from text.

    Args:
        text: The input text to process

    Returns:
        List of dictionaries containing extracted numeric information
    """
    results = []
    for m in NUMBER_RE.finditer(text):
        num_str = m.group("number").replace(",", "")
        try:
            val = float(num_str)
        except ValueError:
            val = None
        results.append(
            {
                "span": m.group(0),
                "value": val,
                "unit": (m.group("unit") or "").lower(),
                "confidence": "medium" if val is not None else "low",
            }
        )
    return results
