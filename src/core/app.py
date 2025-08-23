"""
Centralized application initialization.

This module provides a single point of entry for initializing the application's
core services, such as configuration and logging. Entrypoint scripts (e.g.,
main.py, process_data.py) should call `initialize_app` to get a fully
configured application environment.
"""

import os

import chromadb
import structlog

from src.core.config import AppSettings, get_settings
from src.core.database import Database
from src.core.logger import setup_logging

_logger = structlog.get_logger(__name__)


class AppContext:
    """
    Centralized application context.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings
        setup_logging(self.settings)
        self.db = Database(self.settings.paths)
        # Use separate directory for ChromaDB to avoid conflicts with SQLite
        chroma_db_path = os.path.join(self.settings.paths.data_dir, "chroma_db")
        os.makedirs(chroma_db_path, exist_ok=True)
        self.db_client = chromadb.PersistentClient(path=chroma_db_path)
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
