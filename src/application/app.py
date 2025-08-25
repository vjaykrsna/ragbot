"""
Unified application interface.

This module provides a single interface to initialize and run the application
regardless of the entry point (CLI, bot, script, etc.).
"""

from typing import Optional

import structlog

from src.core.app import AppContext, initialize_app
from src.core.config import AppSettings

_logger = structlog.get_logger(__name__)


class UnifiedApplication:
    """
    A unified interface to the application.

    This class provides a consistent way to access all application services
    regardless of how the application was started.
    """

    def __init__(self, context: Optional[AppContext] = None):
        """
        Initialize the unified application.

        Args:
            context: An existing AppContext instance, or None to create a new one
        """
        self.context = context or initialize_app()
        _logger.info("Unified application initialized.")

    @property
    def settings(self) -> AppSettings:
        """Get the application settings."""
        return self.context.settings

    @property
    def db(self):
        """Get the application database."""
        return self.context.db

    @property
    def db_client(self):
        """Get the application database client."""
        return self.context.db_client

    def get_logger(self, name: str):
        """
        Get a logger with the specified name.

        Args:
            name: The name for the logger

        Returns:
            A configured logger instance
        """
        return structlog.get_logger(name)


def create_application() -> UnifiedApplication:
    """
    Create a new unified application instance.

    This is the main entry point for creating an application instance.

    Returns:
        A configured UnifiedApplication instance
    """
    # Initialize the application context
    context = initialize_app()

    # Create and return the unified application
    return UnifiedApplication(context)
