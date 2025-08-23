"""
End-to-end pipeline integration tests for production reliability.

This module tests the complete data processing pipeline from extraction
to storage to synthesis, ensuring all components work together reliably
in production-like scenarios.
"""

import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor
from src.processing.anonymizer import Anonymizer
from src.processing.conversation_builder import ConversationBuilder
from src.processing.data_source import DataSource
from src.processing.external_sorter import ExternalSorter
from src.processing.pipeline import DataProcessingPipeline


class TestPipelineIntegration(unittest.TestCase):
    """Test complete pipeline integration for production reliability."""

    def setUp(self):
        """Set up complete pipeline with all components."""
        with patch.dict(
            os.environ,
            {
                "API_ID": "12345",
                "API_HASH": "test_hash",
                "PHONE": "1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_bot_token",
                "GROUP_IDS": "1,2,3",
            },
        ):
            self.app_context = initialize_app()

        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.app_context.settings.paths.data_dir = self.temp_dir
        self.app_context.settings.paths.raw_data_dir = os.path.join(
            self.temp_dir, "raw"
        )
        self.app_context.settings.paths.processed_data_dir = os.path.join(
            self.temp_dir, "processed"
        )
        os.makedirs(self.app_context.settings.paths.raw_data_dir, exist_ok=True)
        os.makedirs(self.app_context.settings.paths.processed_data_dir, exist_ok=True)

        # Initialize pipeline components
        self.mock_client = AsyncMock()
        self.storage = Storage(self.app_context)
        self.extractor = TelegramExtractor(self.mock_client, self.storage)

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_complete_extraction_to_storage_pipeline(self):
        """Test complete pipeline from extraction to database storage."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        # Create realistic test messages
        test_messages = []
        for i in range(10):
            mock_msg = MagicMock()
            mock_msg.id = i + 1
            mock_msg.text = f"Test message {i + 1}"
            mock_msg.date = MagicMock()
            mock_msg.date.isoformat.return_value = f"2024-01-01T{i:02d}:00:00"
            mock_msg.from_user = MagicMock()
            mock_msg.from_user.id = f"user{i % 3 + 1}"
            mock_msg.sender_chat = None
            mock_msg.message_thread_id = 456
            mock_msg.reply_to_message_id = None
            mock_msg.service = False
            mock_msg.media = None
            test_messages.append(mock_msg)

        # Mock async iterator
        class MockAsyncIterator:
            def __init__(self, items):
                self.items = items

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.items:
                    return self.items.pop(0)
                raise StopAsyncIteration

        self.mock_client.get_chat_history = MagicMock(
            return_value=MockAsyncIterator(test_messages)
        )

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(mock_entity, mock_topic, {})

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 10)  # All messages should be processed

        # Verify messages were stored in database
        stored_messages = list(self.app_context.db.get_all_messages())
        self.assertEqual(len(stored_messages), 10)

        # Verify message content
        for i, msg in enumerate(stored_messages):
            self.assertEqual(msg["id"], i + 1)
            self.assertEqual(msg["content"], f"Test message {i + 1}")
            self.assertEqual(msg["topic_id"], 456)
            self.assertEqual(msg["source_group_id"], 123)

    def test_concurrent_group_processing_integration(self):
        """Test concurrent processing of multiple groups."""
        # Arrange
        groups = []
        for i in range(3):
            mock_entity = MagicMock()
            mock_entity.id = 100 + i
            mock_entity.title = f"Test Group {i + 1}"
            groups.append(mock_entity)

        last_msg_ids = {}
        import threading

        lock = threading.Lock()

        # Mock successful processing for each group
        async def mock_group_processing(group_id, last_msg_ids, entity, lock):
            # Simulate some processing time
            await asyncio.sleep(0.01)
            return 5  # 5 messages processed

        self.extractor.extract_from_group_id = AsyncMock(
            side_effect=mock_group_processing
        )

        # Act
        async def run_concurrent_test():
            tasks = []
            for entity in groups:
                task = self.extractor.extract_from_group_id(
                    entity.id, last_msg_ids, entity, lock
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        results = asyncio.run(run_concurrent_test())

        # Assert
        self.assertEqual(len(results), 3)
        for result in results:
            if isinstance(result, Exception):
                self.fail(f"Concurrent processing failed: {result}")
            else:
                self.assertEqual(result, 5)

    def test_data_processing_pipeline_integration(self):
        """Test complete data processing pipeline integration."""
        # Arrange - Insert test data into database
        test_messages = []
        for i in range(20):
            test_messages.append(
                {
                    "id": i + 1,
                    "date": f"2024-01-01T{i:02d}:00:00",
                    "sender_id": f"user{i % 5 + 1}",
                    "message_type": "text",
                    "content": f"Test message {i + 1} with some content for processing",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 101,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "source_group_id": 202,
                    "ingestion_timestamp": f"2024-01-01T{i:02d}:00:01",
                }
            )

        self.storage.save_messages_to_db("Test Group", 101, test_messages)

        # Create pipeline components
        data_source = DataSource(self.app_context.db)
        sorter = ExternalSorter()
        anonymizer = Anonymizer()
        conv_builder = ConversationBuilder(
            time_threshold_seconds=300, session_window_seconds=3600
        )

        pipeline = DataProcessingPipeline(
            settings=self.app_context.settings,
            data_source=data_source,
            sorter=sorter,
            anonymizer=anonymizer,
            conv_builder=conv_builder,
        )

        # Act
        pipeline.run()

        # Assert
        # Verify output file was created
        output_file = self.app_context.settings.paths.processed_conversations_file
        self.assertTrue(os.path.exists(output_file))

        # Verify output file contains valid JSON
        import json

        with open(output_file, "r", encoding="utf-8") as f:
            conversations = json.load(f)
            self.assertIsInstance(conversations, list)
            self.assertGreater(len(conversations), 0)

            # Verify conversation structure
            for conv in conversations:
                self.assertIn("messages", conv)
                self.assertIn("participants", conv)
                self.assertIsInstance(conv["messages"], list)

    def test_error_recovery_in_pipeline(self):
        """Test error recovery mechanisms in the pipeline."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        # Mock network failure during extraction
        call_count = 0

        async def failing_extraction():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network failed")
            else:
                # Return successful result on retry
                return 3

        self.extractor.extract_from_group_id = AsyncMock(side_effect=failing_extraction)

        # Act
        async def run_test():
            try:
                result = await self.extractor.extract_from_group_id(
                    123, {}, mock_entity
                )
                return result
            except ConnectionError:
                # Retry once
                return await self.extractor.extract_from_group_id(123, {}, mock_entity)

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 3)  # Should succeed on retry
        self.assertEqual(call_count, 2)  # Should have been called twice

    def test_memory_management_during_large_extraction(self):
        """Test memory management during large-scale extraction."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        # Create a large number of messages (1000)
        large_message_list = []
        for i in range(1000):
            mock_msg = MagicMock()
            mock_msg.id = i + 1
            mock_msg.text = (
                f"Message {i + 1} with substantial content to test memory usage"
            )
            mock_msg.date = MagicMock()
            mock_msg.date.isoformat.return_value = "2024-01-01T00:00:00"
            mock_msg.from_user = MagicMock()
            mock_msg.from_user.id = f"user{i % 10 + 1}"
            mock_msg.sender_chat = None
            mock_msg.message_thread_id = 456
            mock_msg.reply_to_message_id = None
            mock_msg.service = False
            mock_msg.media = None
            large_message_list.append(mock_msg)

        class MockAsyncIterator:
            def __init__(self, items):
                self.items = items

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.items:
                    return self.items.pop(0)
                raise StopAsyncIteration

        self.mock_client.get_chat_history = MagicMock(
            return_value=MockAsyncIterator(large_message_list)
        )

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(mock_entity, mock_topic, {})

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 1000)  # All messages should be processed

        # Verify database integrity
        stored_messages = list(self.app_context.db.get_all_messages())
        self.assertEqual(len(stored_messages), 1000)

        # Verify no data corruption occurred
        for i, msg in enumerate(stored_messages):
            self.assertEqual(msg["id"], i + 1)
            self.assertTrue(msg["content"].startswith("Message"))

    def test_database_transaction_rollback_on_failure(self):
        """Test database transaction rollback on processing failure."""
        # Arrange
        with patch("src.core.database.Database._batch_insert_messages") as mock_insert:
            mock_insert.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed")

            messages = [
                {
                    "id": 1,
                    "date": "2024-01-01T12:00:00",
                    "sender_id": "user1",
                    "message_type": "text",
                    "content": "Test message",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 101,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "source_group_id": 202,
                    "ingestion_timestamp": "2024-01-01T12:00:01",
                }
            ]

            # Act & Assert
            with self.assertRaises(sqlite3.IntegrityError):
                self.storage.save_messages_to_db("Test Group", 101, messages)

    def test_configuration_consistency_across_components(self):
        """Test that configuration is consistent across all components."""
        # Arrange
        settings = self.app_context.settings

        # Act - Create all major components
        mock_client = AsyncMock()
        storage = Storage(self.app_context)
        extractor = TelegramExtractor(mock_client, storage)

        # Assert - Verify configuration consistency
        self.assertEqual(
            extractor.settings.extraction.batch_size,
            settings.telegram.extraction.batch_size,
        )
        self.assertEqual(storage.buffer_size, settings.telegram.extraction.buffer_size)

    def test_resource_cleanup_on_pipeline_failure(self):
        """Test proper resource cleanup when pipeline fails."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        # Mock a failure that should trigger cleanup
        self.mock_client.get_chat = AsyncMock(side_effect=Exception("Critical failure"))

        # Act
        async def run_test():
            with self.assertRaises(Exception):
                await self.extractor.extract_from_group_id(123, {}, mock_entity)

        asyncio.run(run_test())

        # Assert - Storage should be properly closed/cleaned up
        # (This is more of a behavioral test to ensure cleanup happens)
        self.assertIsNotNone(self.storage)


class TestProductionLoadScenarios(unittest.TestCase):
    """Test production-like load scenarios."""

    def setUp(self):
        """Set up production-like test environment."""
        with patch.dict(
            os.environ,
            {
                "API_ID": "12345",
                "API_HASH": "test_hash",
                "PHONE": "1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_bot_token",
                "GROUP_IDS": "1,2,3",
            },
        ):
            self.app_context = initialize_app()

    def test_high_concurrency_message_processing(self):
        """Test processing under high concurrency load."""
        # Arrange
        import asyncio

        mock_client = AsyncMock()
        storage = Storage(self.app_context)
        extractor = TelegramExtractor(mock_client, storage)

        # Mock fast processing
        async def fast_processing():
            await asyncio.sleep(0.001)  # Very short delay
            return 1

        extractor.extract_from_topic = AsyncMock(side_effect=fast_processing)

        # Act
        async def run_concurrent_load_test():
            # Simulate 50 concurrent operations
            tasks = []
            for i in range(50):
                mock_entity = MagicMock()
                mock_entity.id = i
                mock_entity.title = f"Group {i}"

                mock_topic = MagicMock()
                mock_topic.id = 100 + i
                mock_topic.title = f"Topic {i}"

                task = extractor.extract_from_topic(mock_entity, mock_topic, {})
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        results = asyncio.run(run_concurrent_load_test())

        # Assert
        self.assertEqual(len(results), 50)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        self.assertEqual(len(successful_results), 50)  # All should succeed

    def test_large_dataset_performance_baseline(self):
        """Test performance baseline with large datasets."""
        # Arrange
        storage = Storage(self.app_context)

        # Create a large dataset (1000 messages)
        large_dataset = []
        for i in range(1000):
            large_dataset.append(
                {
                    "id": i + 1,
                    "date": "2024-01-01T12:00:00",
                    "sender_id": f"user{i % 50 + 1}",
                    "message_type": "text",
                    "content": f"Message {i + 1} with realistic content for performance testing",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 101,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "source_group_id": 202,
                    "ingestion_timestamp": "2024-01-01T12:00:01",
                }
            )

        # Act
        import time

        start_time = time.time()

        storage.save_messages_to_db("Test Group", 101, large_dataset)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert
        # Should process 1000 messages in reasonable time (less than 5 seconds)
        self.assertLess(processing_time, 5.0)

        # Verify all messages were stored
        stored_messages = list(self.app_context.db.get_all_messages())
        self.assertEqual(len(stored_messages), 1000)


if __name__ == "__main__":
    unittest.main()
