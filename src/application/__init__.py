"""Initialization module for the unified application.

This module provides functions to create and configure the unified application.
"""

from src.application.app import UnifiedApplication, create_application
from src.core.config import AppSettings

__all__ = ["UnifiedApplication", "create_application", "AppSettings"]
