"""
Data source component for the processing pipeline.

This module provides a class for discovering and iterating through raw data files.
"""

from typing import Any, Dict, Generator

import structlog

from src.core.database import Database

logger = structlog.get_logger(__name__)


class DataSource:
    """
    Provides an iterator for messages stored in the database.
    """

    def __init__(self, db: Database):
        """
        Initializes the DataSource with a database instance.

        Args:
            db: The database to read from.
        """
        self.db = db
        self.logger = structlog.get_logger(__name__)

    def __iter__(self) -> Generator[Dict[str, Any], None, None]:
        """Iterates through all messages in the database."""
        self.logger.info("Reading messages from the database.")
        yield from self.db.get_all_messages()
