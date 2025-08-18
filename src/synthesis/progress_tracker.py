import json
import logging
import os
from typing import Set

from src.core.config import AppSettings

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Manages the state of the synthesis process, including progress and processed hashes.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def save_progress(self, last_processed_index: int) -> None:
        path = self.settings.paths.synthesis_progress_file
        with open(path, "w") as f:
            json.dump({"last_processed_index": last_processed_index}, f)

    def load_progress(self) -> int:
        path = self.settings.paths.synthesis_progress_file
        try:
            with open(path, "r") as f:
                return json.load(f).get("last_processed_index", -1)
        except (FileNotFoundError, json.JSONDecodeError):
            return -1

    def load_processed_hashes(self) -> Set[str]:
        path = self.settings.paths.processed_hashes_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def save_processed_hashes(self, hashes: Set[str]) -> None:
        path = self.settings.paths.processed_hashes_file
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(hashes), f)
        except IOError:
            logger.error(f"Failed to save processed hashes to {path}")
