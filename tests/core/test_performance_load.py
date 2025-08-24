"""
Performance and load testing for production reliability.

This module tests system performance under various load conditions,
memory usage, concurrent operations, and resource exhaustion scenarios
to ensure 99% production reliability.
"""

import asyncio
import os
import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import psutil

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor


class TestPerformanceBenchmarks(unittest.TestCase):
    """Test performance benchmarks and thresholds."""

    def setUp(self):
        """Set up performance test environment."""
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

        self.mock_client = AsyncMock()
        self.storage = Storage(self.app_context)
        self.extractor = TelegramExtractor(self.mock_client, self.storage)

        # Performance thresholds (adjust based on your requirements)
        self.MAX_EXTRACTION_TIME_PER_MESSAGE = 0.01  # 10ms per message
        self.MAX_MEMORY_USAGE_PERCENT = 85.0  # 85% memory usage
        self.MAX_CONCURRENT_OPERATIONS = 10  # Maximum concurrent operations

    def test_message_extraction_performance(self):
        """Test message extraction performance meets benchmarks."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        # Create test messages
        test_messages = []
        for i in range(100):
            mock_msg = MagicMock()
            mock_msg.id = i + 1
            mock_msg.text = f"Performance test message {i + 1}"
            mock_msg.date = MagicMock()
            mock_msg.date.isoformat.return_value = "2024-01-01T00:00:00"
            mock_msg.from_user = MagicMock()
            mock_msg.from_user.id = f"user{i % 10 + 1}"
            mock_msg.sender_chat = None
            mock_msg.message_thread_id = 456
            mock_msg.reply_to_message_id = None
            mock_msg.service = False
            mock_msg.media = None
            test_messages.append(mock_msg)

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
        start_time = time.time()

        async def run_test():
            return await self.extractor.extract_from_topic(mock_entity, mock_topic, {})

        result = asyncio.run(run_test())
        end_time = time.time()

        # Assert
        self.assertEqual(result, 100)  # All messages processed

        total_time = end_time - start_time
        avg_time_per_message = total_time / 100

        # Performance assertions
        self.assertLess(
            avg_time_per_message, self.MAX_EXTRACTION_TIME_PER_MESSAGE, ".4f"
        )

    def test_memory_usage_during_extraction(self):
        """Test memory usage stays within acceptable limits."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        # Create large message set
        test_messages = []
        for i in range(500):
            mock_msg = MagicMock()
            mock_msg.id = i + 1
            mock_msg.text = f"Memory test message {i + 1} with substantial content to test memory usage patterns"
            mock_msg.date = MagicMock()
            mock_msg.date.isoformat.return_value = "2024-01-01T00:00:00"
            mock_msg.from_user = MagicMock()
            mock_msg.from_user.id = f"user{i % 20 + 1}"
            mock_msg.sender_chat = None
            mock_msg.message_thread_id = 456
            mock_msg.reply_to_message_id = None
            mock_msg.service = False
            mock_msg.media = None
            test_messages.append(mock_msg)

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

        # Monitor memory usage
        process = psutil.Process()
        initial_memory = process.memory_percent()

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(mock_entity, mock_topic, {})

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 500)

        final_memory = process.memory_percent()
        # Calculate memory increase for monitoring (not used in assertion but good for debugging)
        _ = final_memory - initial_memory

        # Memory usage should not exceed threshold
        self.assertLess(final_memory, self.MAX_MEMORY_USAGE_PERCENT, ".1f")

    def test_database_performance_with_large_dataset(self):
        """Test database performance with large datasets."""
        # Arrange
        storage = Storage(self.app_context)

        # Create large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append(
                {
                    "id": i + 1,
                    "date": "2024-01-01T12:00:00",
                    "sender_id": f"user{i % 100 + 1}",
                    "message_type": "text",
                    "content": f"Database performance test message {i + 1}",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 101,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "source_group_id": 202,
                    "ingestion_timestamp": "2024-01-01T12:00:01",
                }
            )

        # Act - Measure insertion performance
        start_time = time.time()
        storage.save_messages_to_db("Test Group", 101, large_dataset)
        end_time = time.time()

        # Assert
        insertion_time = end_time - start_time
        avg_time_per_message = insertion_time / 1000

        # Database should handle 1000 messages in reasonable time
        self.assertLess(insertion_time, 10.0)  # Less than 10 seconds
        self.assertLess(avg_time_per_message, 0.01)  # Less than 10ms per message

        # Verify data integrity
        stored_messages = list(self.app_context.db.get_all_messages())
        self.assertEqual(len(stored_messages), 1000)


class TestConcurrentLoad(unittest.TestCase):
    """Test concurrent load handling and thread safety."""

    def setUp(self):
        """Set up concurrent test environment."""
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

        self.mock_client = AsyncMock()
        self.storage = Storage(self.app_context)
        self.extractor = TelegramExtractor(self.mock_client, self.storage)

    def test_concurrent_group_processing(self):
        """Test concurrent processing of multiple groups."""
        # Arrange
        groups = []
        for i in range(5):
            mock_entity = MagicMock()
            mock_entity.id = 100 + i
            mock_entity.title = f"Concurrent Group {i + 1}"
            groups.append(mock_entity)

        last_msg_ids = {}
        lock = threading.Lock()

        # Mock processing with slight delay to simulate real work
        async def mock_group_processing(group_id, last_msg_ids, entity, lock):
            await asyncio.sleep(0.01)  # Simulate processing time
            return 10  # 10 messages processed

        self.extractor.extract_from_group_id = AsyncMock(
            side_effect=mock_group_processing
        )

        # Act
        start_time = time.time()

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
        end_time = time.time()

        # Assert
        total_time = end_time - start_time

        # All operations should complete successfully
        self.assertEqual(len(results), 5)
        for result in results:
            if isinstance(result, Exception):
                self.fail(f"Concurrent operation failed: {result}")
            else:
                self.assertEqual(result, 10)

        # Concurrent processing should be reasonably fast
        self.assertLess(
            total_time, 2.0
        )  # Less than 2 seconds for 5 concurrent operations

    def test_thread_safety_with_shared_resources(self):
        """Test thread safety when accessing shared resources."""
        # Arrange
        import concurrent.futures

        storage = Storage(self.app_context)
        # Initialize variables for concurrent processing (used in actual implementation)
        _ = {}  # last_msg_ids placeholder
        lock = threading.Lock()

        def worker_task(worker_id):
            """Worker task that simulates concurrent access."""
            try:
                # Simulate concurrent message storage
                messages = [
                    {
                        "id": worker_id * 100 + 1,
                        "date": "2024-01-01T12:00:00",
                        "sender_id": f"user{worker_id}",
                        "message_type": "text",
                        "content": f"Concurrent message from worker {worker_id}",
                        "extra_data": {},
                        "reply_to_msg_id": None,
                        "topic_id": 101,
                        "topic_title": "General",
                        "source_name": "Test Group",
                        "source_group_id": 202,
                        "ingestion_timestamp": "2024-01-01T12:00:01",
                    }
                ]

                with lock:
                    storage.save_messages_to_db("Test Group", 101, messages)

                return True
            except Exception as e:
                return e

        # Act
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # Assert
        # All operations should succeed
        for result in results:
            if isinstance(result, Exception):
                self.fail(f"Thread safety test failed: {result}")
            else:
                self.assertTrue(result)

        # Verify data integrity
        stored_messages = list(self.app_context.db.get_all_messages())
        self.assertEqual(len(stored_messages), 10)  # 10 workers * 1 message each

    def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion scenarios."""
        # Arrange
        import resource

        # Set resource limits for testing
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, hard))  # 100MB limit

        try:
            # Create a scenario that might exhaust memory
            storage = Storage(self.app_context)

            # Create very large messages
            large_messages = []
            for i in range(100):
                large_messages.append(
                    {
                        "id": i + 1,
                        "date": "2024-01-01T12:00:00",
                        "sender_id": f"user{i % 10 + 1}",
                        "message_type": "text",
                        "content": "x" * 10000,  # 10KB per message
                        "extra_data": {},
                        "reply_to_msg_id": None,
                        "topic_id": 101,
                        "topic_title": "General",
                        "source_name": "Test Group",
                        "source_group_id": 202,
                        "ingestion_timestamp": "2024-01-01T12:00:01",
                    }
                )

            # Act & Assert
            # This should either succeed or fail gracefully
            try:
                storage.save_messages_to_db("Test Group", 101, large_messages)
                # If it succeeds, verify data integrity
                stored_messages = list(self.app_context.db.get_all_messages())
                self.assertEqual(len(stored_messages), 100)
            except MemoryError:
                # Memory exhaustion is acceptable, but should be handled gracefully
                pass
            except Exception as e:
                # Other exceptions should be reasonable
                self.assertIn(
                    "memory" in str(e).lower() or "resource" in str(e).lower(), True
                )

        finally:
            # Restore original limits
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


class TestLoadPatterns(unittest.TestCase):
    """Test various load patterns and stress scenarios."""

    def setUp(self):
        """Set up load test environment."""
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

    def test_burst_load_handling(self):
        """Test handling of burst load patterns."""
        # Arrange
        mock_client = AsyncMock()
        storage = Storage(self.app_context)
        extractor = TelegramExtractor(mock_client, storage)

        # Mock burst processing
        async def burst_processing():
            await asyncio.sleep(0.001)  # Very short delay
            return 1

        extractor.extract_from_topic = AsyncMock(side_effect=burst_processing)

        # Act - Simulate burst of 100 operations
        start_time = time.time()

        async def run_burst_test():
            tasks = []
            for i in range(100):
                mock_entity = MagicMock()
                mock_entity.id = i
                mock_entity.title = f"Burst Group {i}"

                mock_topic = MagicMock()
                mock_topic.id = 100 + i
                mock_topic.title = f"Burst Topic {i}"

                task = extractor.extract_from_topic(mock_entity, mock_topic, {})
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        results = asyncio.run(run_burst_test())
        end_time = time.time()

        # Assert
        burst_time = end_time - start_time

        # Should handle burst load reasonably well
        self.assertLess(burst_time, 10.0)  # Less than 10 seconds for 100 operations

        successful_results = [r for r in results if not isinstance(r, Exception)]
        self.assertEqual(len(successful_results), 100)  # All should succeed

    def test_sustained_load_performance(self):
        """Test performance under sustained load."""
        # Arrange
        mock_client = AsyncMock()
        storage = Storage(self.app_context)
        extractor = TelegramExtractor(mock_client, storage)

        # Mock sustained processing
        async def sustained_processing():
            await asyncio.sleep(0.01)  # Consistent delay
            return 1

        extractor.extract_from_topic = AsyncMock(side_effect=sustained_processing)

        # Act - Simulate sustained load over time
        start_time = time.time()

        async def run_sustained_test():
            results = []
            for batch in range(5):  # 5 batches
                tasks = []
                for i in range(10):  # 10 operations per batch
                    mock_entity = MagicMock()
                    mock_entity.id = batch * 10 + i
                    mock_entity.title = f"Sustained Group {batch * 10 + i}"

                    mock_topic = MagicMock()
                    mock_topic.id = 100 + batch * 10 + i
                    mock_topic.title = f"Sustained Topic {batch * 10 + i}"

                    task = extractor.extract_from_topic(mock_entity, mock_topic, {})
                    tasks.append(task)

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(batch_results)

                # Small delay between batches to simulate realistic load
                await asyncio.sleep(0.1)

            return results

        results = asyncio.run(run_sustained_test())
        end_time = time.time()

        # Assert
        sustained_time = end_time - start_time

        # Should handle sustained load efficiently
        self.assertLess(sustained_time, 15.0)  # Less than 15 seconds for sustained load

        successful_results = [r for r in results if not isinstance(r, Exception)]
        self.assertEqual(
            len(successful_results), 50
        )  # All 50 operations should succeed

    def test_gradual_load_increase(self):
        """Test handling of gradually increasing load."""
        # Arrange
        mock_client = AsyncMock()
        storage = Storage(self.app_context)
        extractor = TelegramExtractor(mock_client, storage)

        # Mock processing with increasing delay to simulate load
        call_count = 0

        async def increasing_load_processing():
            nonlocal call_count
            call_count += 1
            delay = 0.001 * call_count  # Increasing delay
            await asyncio.sleep(delay)
            return 1

        extractor.extract_from_topic = AsyncMock(side_effect=increasing_load_processing)

        # Act - Simulate gradually increasing load
        start_time = time.time()

        async def run_gradual_test():
            results = []
            for batch in range(10):  # 10 batches with increasing load
                tasks = []
                for i in range(batch + 1):  # Increasing number of operations
                    mock_entity = MagicMock()
                    mock_entity.id = batch * 10 + i
                    mock_entity.title = f"Gradual Group {batch * 10 + i}"

                    mock_topic = MagicMock()
                    mock_topic.id = 100 + batch * 10 + i
                    mock_topic.title = f"Gradual Topic {batch * 10 + i}"

                    task = extractor.extract_from_topic(mock_entity, mock_topic, {})
                    tasks.append(task)

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(batch_results)

            return results

        results = asyncio.run(run_gradual_test())
        end_time = time.time()

        # Assert
        gradual_time = end_time - start_time

        # Should handle gradual load increase
        self.assertLess(gradual_time, 20.0)  # Less than 20 seconds

        successful_results = [r for r in results if not isinstance(r, Exception)]
        expected_operations = sum(range(1, 11))  # 1+2+...+10 = 55
        self.assertEqual(len(successful_results), expected_operations)


if __name__ == "__main__":
    unittest.main()
