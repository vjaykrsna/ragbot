from typing import Any, Dict, List, Optional

import structlog

from src.core.config import AppSettings
from src.core.database import Database
from src.synthesis.data_transformer import DataTransformer

logger = structlog.get_logger(__name__)


class DataLoader:
    """
    Handles loading of processed data and prompt templates.

    Args:
        settings: The application settings.
        db: Optional database instance to use. If not provided, a new one will be created.
    """

    def __init__(self, settings: AppSettings, db: Database = None):
        self.settings = settings
        self.db = db or Database(settings.paths)
        self.transformer = DataTransformer()

    def load_processed_data(self) -> List[Dict[str, Any]]:
        """
        Loads processed conversation data from the database.

        Returns:
            A list of conversations.
        """
        try:
            logger.info("Loading processed data from database")

            # Get all messages from the database using pagination to avoid memory issues
            all_messages = []
            page_size = self.settings.synthesis.page_size  # Configurable page size
            offset = 0

            while True:
                messages_chunk = self._load_messages_page(page_size, offset)
                if not messages_chunk:
                    break
                all_messages.extend(messages_chunk)
                offset += page_size
                logger.info(f"Loaded {len(all_messages)} messages so far...")

            # Transform database messages into conversation envelopes
            conversations = self.transformer.transform_database_messages(all_messages)

            logger.info(f"Loaded {len(conversations)} conversations from database")
            return conversations

        except Exception as e:
            logger.error(f"Could not load processed data from database: {e}")
            return []

    def _load_messages_page(self, page_size: int, offset: int) -> List[Dict[str, Any]]:
        """
        Load a page of messages from the database.

        Args:
            page_size: Number of messages to load
            offset: Offset to start loading from

        Returns:
            List of message dictionaries
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages ORDER BY source_group_id, topic_id, date LIMIT ? OFFSET ?",
                (page_size, offset),
            )
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def load_prompt_template(self) -> Optional[str]:
        """
        Loads the prompt template from the markdown file.

        Returns:
            The prompt template as a string, or None if the file is not found or corrupted.
        """
        try:
            with open(self.settings.paths.prompt_file, "r", encoding="utf-8") as f:
                logger.info(
                    f"Loading prompt template from {self.settings.paths.prompt_file}"
                )
                content = f.read()
                if not content.strip():
                    logger.error("Prompt template file is empty")
                    return None
                return content
        except FileNotFoundError as e:
            logger.error(f"Could not load prompt template: {e}")
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error while reading prompt template: {e}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied while reading prompt template: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while loading prompt template: {e}")
            return None
