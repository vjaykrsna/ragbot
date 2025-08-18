import json
import logging
from typing import Any, Dict, List, Optional

from src.core.config import AppSettings

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Handles loading of processed data and prompt templates.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def load_processed_data(self) -> List[Dict[str, Any]]:
        """Loads processed conversation data from the JSON file."""
        file_path = self.settings.paths.processed_conversations_file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                logger.info(f"Loading processed data from {file_path}")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load processed data from {file_path}: {e}")
            return []

    def load_prompt_template(self) -> Optional[str]:
        """Loads the prompt template from the markdown file."""
        try:
            with open(self.settings.paths.prompt_file, "r", encoding="utf-8") as f:
                logger.info(
                    f"Loading prompt template from {self.settings.paths.prompt_file}"
                )
                return f.read()
        except FileNotFoundError as e:
            logger.error(f"Could not load prompt template: {e}")
            return None
