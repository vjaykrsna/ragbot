"""
Utility functions for configuration management.
"""

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_project_root() -> str:
    """Returns the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
