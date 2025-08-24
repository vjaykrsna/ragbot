#!/usr/bin/env python3
"""
Retry Failed Batches Script

This script processes failed batches that were saved during the main synthesis process.
It attempts to reprocess them with enhanced error handling and different parameters.
"""

import json
import os
import time
from typing import Dict

import structlog
from dotenv import load_dotenv

from src.core.app import initialize_app
from src.rag.rag_pipeline import RAGPipeline
from src.synthesis.data_loader import DataLoader
from src.synthesis.nugget_generator import NuggetGenerator
from src.synthesis.nugget_store import NuggetStore

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)


class FailedBatchRetrier:
    """Handles retrying of failed batches with enhanced error handling."""

    def __init__(self):
        self.app_context = initialize_app()
        self.settings = self.app_context.settings
        self.nugget_generator = NuggetGenerator(
            settings=self.settings,
            limiter=None,  # No rate limiting for retries
        )
        self.data_loader = DataLoader(self.settings, self.app_context.db)
        self.nugget_store = NuggetStore()
        self.rag_pipeline = RAGPipeline(self.settings, self.app_context.db_client)

    def retry_failed_batches(self, failed_file_path: str = None) -> Dict[str, int]:
        """
        Retry processing of failed batches.

        Args:
            failed_file_path: Path to the failed batches file

        Returns:
            Dictionary with retry statistics
        """
        if failed_file_path is None:
            failed_file_path = self.settings.paths.failed_batches_file

        if not os.path.exists(failed_file_path):
            logger.info("No failed batches file found")
            return {"total": 0, "successful": 0, "failed": 0}

        logger.info(f"Starting retry of failed batches from {failed_file_path}")

        stats = {"total": 0, "successful": 0, "failed": 0}
        prompt_template = self.data_loader.load_prompt_template()

        if not prompt_template:
            logger.error("Could not load prompt template")
            return stats

        with open(failed_file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    batch_data = json.loads(line.strip())
                    conv_batch = batch_data["batch"]

                    logger.info(
                        f"Retrying batch {line_num}: {batch_data.get('error', 'Unknown error')}"
                    )

                    # Attempt to reprocess the batch
                    nuggets = self.nugget_generator.generate_nuggets(
                        conv_batch, prompt_template
                    )

                    if nuggets:
                        # Success! Store the nuggets
                        try:
                            collection = (
                                self.app_context.db_client.get_or_create_collection(
                                    name=self.settings.rag.collection_name
                                )
                            )
                            self.nugget_store.store_nuggets_batch(collection, nuggets)
                            stats["successful"] += 1
                            logger.info(
                                f"Successfully retried batch {line_num}, generated {len(nuggets)} nuggets"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to store successful retry for batch {line_num}: {e}"
                            )
                            stats["failed"] += 1
                    else:
                        stats["failed"] += 1
                        logger.warning(f"Batch {line_num} still failed after retry")

                    stats["total"] += 1

                    # Small delay between retries to be respectful to the API
                    time.sleep(1)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse line {line_num}: {e}")
                    stats["failed"] += 1
                    stats["total"] += 1
                except Exception as e:
                    logger.error(f"Unexpected error processing batch {line_num}: {e}")
                    stats["failed"] += 1
                    stats["total"] += 1

        logger.info(f"Retry completed. Stats: {stats}")
        return stats

    def cleanup_successful_retries(self, failed_file_path: str = None) -> None:
        """
        Remove successfully retried batches from the failed batches file.
        This is optional - you might want to keep the history.
        """
        if failed_file_path is None:
            failed_file_path = self.settings.paths.failed_batches_file

        if not os.path.exists(failed_file_path):
            return

        # For now, just log that this could be implemented
        logger.info("Cleanup of successful retries could be implemented here")
        logger.info(f"Failed batches file: {failed_file_path}")


def main():
    """Main entry point for the retry script."""
    retrier = FailedBatchRetrier()
    stats = retrier.retry_failed_batches()

    print("\n=== Failed Batch Retry Results ===")
    print(f"Total batches processed: {stats['total']}")
    print(f"Successfully retried: {stats['successful']}")
    print(f"Still failed: {stats['failed']}")

    if stats["total"] > 0:
        success_rate = (stats["successful"] / stats["total"]) * 100
        print(f"Success rate: {success_rate:.1f}%")

    if stats["failed"] > 0:
        print(
            f"\nRemaining failed batches are still in: {retrier.settings.paths.failed_batches_file}"
        )
        print("You can run this script again later when API conditions improve.")


if __name__ == "__main__":
    main()
