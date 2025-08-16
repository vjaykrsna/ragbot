"""
Data source component for the processing pipeline.

This module provides a class for discovering and iterating through raw data files.
"""

import glob
import json
import logging
import os
from typing import Any, Dict, Generator, List

from src.config.paths import PathSettings


class DataSource:
    """
    Discovers and provides an iterator for raw JSONL data files.
    """

    def __init__(self, settings: PathSettings):
        """
        Initializes the DataSource with path settings.

        Args:
            settings: The path settings for the application.
        """
        self.settings = settings
        self.logger = logging.getLogger(__name__)

    def _find_files(self) -> List[str]:
        """Finds and sorts all .jsonl files in the raw data directory."""
        files = sorted(glob.glob(os.path.join(self.settings.raw_data_dir, "*.jsonl")))
        if not files:
            self.logger.warning(
                f"No .jsonl files found in '{self.settings.raw_data_dir}'. "
                "Run extraction first."
            )
        else:
            self.logger.info(f"Found {len(files)} raw files.")
        return files

    def __iter__(self) -> Generator[Dict[str, Any], None, None]:
        """Iterates through all messages in all found data files."""
        files = self._find_files()
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    try:
                        rec = json.loads(line)
                        if rec.get("date"):
                            yield rec
                    except json.JSONDecodeError:
                        self.logger.warning(
                            f"Skipping corrupted JSON on line {i} in {file_path}"
                        )
