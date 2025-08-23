"""
User anonymization component for the data processing pipeline.

This module provides a class for managing a persistent map of user IDs to
anonymized identifiers.
"""

import json
import os
from typing import Dict, Tuple

import structlog

from src.core.config import PathSettings


class Anonymizer:
    """
    Manages the loading, updating, and persisting of a user anonymization map.
    """

    def __init__(self, settings: PathSettings):
        """
        Initializes the Anonymizer.

        Args:
            settings: The path settings for the application.
        """
        self.user_map_file = settings.user_map_file
        self.logger = structlog.get_logger(__name__)
        self.user_map, self.next_user_num = self._load_user_map()

    def _load_user_map(self) -> Tuple[Dict[str, str], int]:
        """Loads the user map from disk if it exists."""
        if os.path.exists(self.user_map_file):
            try:
                with open(self.user_map_file, "r", encoding="utf-8") as f:
                    m = json.load(f)
                max_n = 0
                for v in m.values():
                    if isinstance(v, str) and v.startswith("User_"):
                        try:
                            n = int(v.split("_", 1)[1])
                            if n > max_n:
                                max_n = n
                        except (ValueError, IndexError):
                            pass
                return m, max_n + 1
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(
                    f"User map file corrupted or unreadable ({e}); starting fresh."
                )
        return {}, 1

    def anonymize(self, sender_id: str) -> str:
        """
        Returns an anonymized user ID for the given sender ID, creating a new
        one if necessary.
        """
        sid = str(sender_id)
        if sid not in self.user_map:
            self.user_map[sid] = f"User_{self.next_user_num}"
            self.next_user_num += 1
        return self.user_map[sid]

    def persist(self) -> None:
        """Saves the user map to disk."""
        try:
            with open(self.user_map_file, "w", encoding="utf-8") as f:
                json.dump(self.user_map, f, ensure_ascii=False, indent=2)
            self.logger.info(f"User map saved to {self.user_map_file}")
        except IOError as e:
            self.logger.error(f"Failed to save user map: {e}")
