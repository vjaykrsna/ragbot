"""
Centralized application initialization.

This module provides a single point of entry for initializing the application's
core services, such as configuration and logging. Entrypoint scripts (e.g.,
main.py, process_data.py) should call `initialize_app` to get a fully
configured application environment.
"""

import os

import structlog

from src.core.config import AppSettings, get_settings
from src.core.logger import setup_logging
from src.database import Database

_logger = structlog.get_logger(__name__)


class AppContext:
    """
    Centralized application context.
    """

    def __init__(self, settings: AppSettings):
        import chromadb

        self.settings = settings
        setup_logging(self.settings)
        self.db = Database(self.settings.paths)
        if not os.path.exists(self.db.db_path):
            self.db_client = chromadb.PersistentClient(path=self.db.db_path)
        else:
            self.db_client = chromadb.PersistentClient(
                path=os.path.dirname(self.db.db_path)
            )
        _logger.info("Application context initialized.")

    @classmethod
    def create(cls) -> "AppContext":
        """
        Creates a new instance of the application context.
        """
        settings = get_settings()
        return cls(settings)


def initialize_app() -> AppContext:
    """
    Initializes the application by creating the application context.
    """
    return AppContext.create()
