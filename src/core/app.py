"""
Centralized application initialization.

This module provides a single point of entry for initializing the application's
core services, such as configuration and logging. Entrypoint scripts (e.g.,
main.py, process_data.py) should call `initialize_app` to get a fully
configured application environment.
"""

import structlog

from src.config.settings import load_settings
from src.core.container import create_container
from src.core.logger import setup_logging

_logger = structlog.get_logger(__name__)


class AppContext:
    """
    Centralized application context.
    """

    def __init__(self):
        self.settings = load_settings()
        setup_logging(self.settings)
        self.container = create_container(self.settings)
        _logger.info("Application context initialized.")

    @classmethod
    def create(cls) -> "AppContext":
        """
        Creates a new instance of the application context.
        """
        return cls()


def initialize_app() -> AppContext:
    """
    Initializes the application by creating the application context.
    """
    return AppContext.create()
