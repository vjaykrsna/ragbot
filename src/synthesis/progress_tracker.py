import json
import logging
import os
from typing import Set

from src.core.config import AppSettings

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Manages the state of the synthesis process, including progress and processed hashes.

    Args:
        settings: The application settings.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def save_progress(self, last_processed_index: int) -> None:
        """
        Saves the last processed index to a file.

        Args:
            last_processed_index: The index of the last processed item.
        """
        path = self.settings.paths.synthesis_progress_file
        with open(path, "w") as f:
            json.dump({"last_processed_index": last_processed_index}, f)

    def load_progress(self) -> int:
        """
        Loads the last processed index from a file.

        Returns:
            The last processed index, or -1 if the file is not found.
        """
        path = self.settings.paths.synthesis_progress_file
        try:
            with open(path, "r") as f:
                return json.load(f).get("last_processed_index", -1)
        except (FileNotFoundError, json.JSONDecodeError):
            return -1

    def load_processed_hashes(self) -> Set[str]:
        """
        Loads the set of processed hashes from a file.

        Returns:
            A set of processed hashes.
        """
        path = self.settings.paths.processed_hashes_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def save_processed_hashes(self, hashes: Set[str]) -> None:
        """
        Saves the set of processed hashes to a file.

        Args:
            hashes: A set of processed hashes.
        """
        path = self.settings.paths.processed_hashes_file
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(hashes), f)
        except IOError:
            logger.error(f"Failed to save processed hashes to {path}")
