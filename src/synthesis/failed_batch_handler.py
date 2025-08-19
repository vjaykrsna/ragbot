import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from src.core.config import AppSettings

logger = logging.getLogger(__name__)

# Thread-safe lock
fail_file_lock = threading.Lock()


class FailedBatchHandler:
    """
    Handles the saving of failed batches.

    Args:
        settings: The application settings.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings

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
        with fail_file_lock:
            os.makedirs(
                os.path.dirname(self.settings.paths.failed_batches_file), exist_ok=True
            )
            with open(
                self.settings.paths.failed_batches_file, "a", encoding="utf-8"
            ) as f:
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
