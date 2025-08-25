"""
Unified state management for long-running processes.

This module provides a single StateManager class that consolidates:
1. Checkpoint-based recovery
2. Progress tracking
3. Failed batch handling
4. Processed hash tracking
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Set

import structlog

from src.core.config import AppSettings

logger = structlog.get_logger(__name__)

# Thread-safe lock for file operations
state_file_lock = threading.Lock()


class StateManager:
    """
    Manages all state for long-running processes including checkpoints, progress, and failures.
    """

    def __init__(self, settings: AppSettings):
        """
        Initialize the StateManager with application settings.

        Args:
            settings: The application settings containing file paths for state management.
        """
        self.settings = settings
        self.checkpoint_file = settings.paths.synthesis_checkpoint_file
        self.progress_file = settings.paths.synthesis_progress_file
        self.processed_hashes_file = settings.paths.processed_hashes_file
        self.failed_batches_file = settings.paths.failed_batches_file
        self.last_checkpoint = {}

    # Checkpoint Management
    def save_checkpoint(self, **kwargs) -> None:
        """
        Save a checkpoint with the provided state information.

        Args:
            **kwargs: State information to save
        """
        self.last_checkpoint = kwargs
        try:
            os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
            with state_file_lock:
                with open(self.checkpoint_file, "w") as f:
                    json.dump(kwargs, f)
            logger.debug(f"Checkpoint saved to {self.checkpoint_file}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self) -> Dict[str, Any]:
        """
        Load the last saved checkpoint.

        Returns:
            Dictionary containing checkpoint data or empty dict if no checkpoint exists
        """
        try:
            with state_file_lock:
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
            self.last_checkpoint = data
            logger.debug(f"Checkpoint loaded from {self.checkpoint_file}")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"No checkpoint found or invalid checkpoint: {e}")
            return {}

    def clear_checkpoint(self) -> None:
        """Clear the current checkpoint."""
        self.last_checkpoint = {}
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            logger.debug("Checkpoint cleared")
        except Exception as e:
            logger.warning(f"Failed to clear checkpoint: {e}")

    # Progress Tracking
    def save_progress(self, last_processed_index: int) -> None:
        """
        Saves the last processed index to a file.

        Args:
            last_processed_index: The index of the last processed item.
        """
        try:
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            with state_file_lock:
                with open(self.progress_file, "w") as f:
                    json.dump({"last_processed_index": last_processed_index}, f)
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")

    def load_progress(self) -> int:
        """
        Loads the last processed index from a file.

        Returns:
            The last processed index, or -1 if the file is not found.
        """
        try:
            with state_file_lock:
                with open(self.progress_file, "r") as f:
                    return json.load(f).get("last_processed_index", -1)
        except (FileNotFoundError, json.JSONDecodeError):
            return -1

    # Processed Hashes Management
    def load_processed_hashes(self) -> Set[str]:
        """
        Loads the set of processed hashes from a file.

        Returns:
            A set of processed hashes.
        """
        if os.path.exists(self.processed_hashes_file):
            try:
                with state_file_lock:
                    with open(self.processed_hashes_file, "r", encoding="utf-8") as f:
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
        try:
            os.makedirs(os.path.dirname(self.processed_hashes_file), exist_ok=True)
            with state_file_lock:
                with open(self.processed_hashes_file, "w", encoding="utf-8") as f:
                    json.dump(list(hashes), f)
        except IOError:
            logger.error(
                f"Failed to save processed hashes to {self.processed_hashes_file}"
            )

    # Failed Batch Handling
    def save_failed_batch(
        self, conv_batch: List[Dict[str, Any]], error: str, response_text: str = ""
    ) -> None:
        """
        Saves a failed batch to a file.

        Args:
            conv_batch: The batch of conversations that failed.
            error: The error message.
            response_text: The response text from the LLM.
        """
        try:
            os.makedirs(os.path.dirname(self.failed_batches_file), exist_ok=True)
            with state_file_lock:
                with open(self.failed_batches_file, "a", encoding="utf-8") as f:
                    json.dump(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "error": error,
                            "response_text": response_text,
                            "batch": conv_batch,
                        },
                        f,
                    )
                    f.write("\n")
        except IOError as e:
            logger.error(f"Failed to save failed batch: {e}")
