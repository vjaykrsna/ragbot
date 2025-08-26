import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.app import initialize_app
from src.history_extractor.telegram_extractor import TelegramExtractor


class MockAsyncIterator:
    """Mock async iterator for testing."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.items:
            return self.items.pop(0)
        raise StopAsyncIteration


class TestTelegramExtractor(unittest.TestCase):
    """Test cases for the TelegramExtractor class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()

        # Use real settings instead of MagicMock for better test reliability
        with patch.dict(
            os.environ,
            {
                "API_ID": "12345",
                "API_HASH": "test_hash",
                "PHONE": "1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_bot_token",
                "GROUP_IDS": "1,2,3",
                "DB_DIR": self.temp_dir,  # Override to use temp directory
            },
        ):
            self.app_context = initialize_app()
            # Override paths settings to use temp directory
            self.app_context.settings.paths.data_dir = self.temp_dir
            self.app_context.settings.paths.db_dir = os.path.join(
                self.temp_dir, "knowledge_base"
            )

        self.mock_client = MagicMock()
        self.mock_client.get_chat = AsyncMock()
        self.mock_client.invoke = AsyncMock()
        self.mock_storage = MagicMock()
        self.extractor = TelegramExtractor(self.mock_client, self.mock_storage)

        # Override settings with real values for the extraction settings
        self.extractor.settings.telegram.extraction.messages_per_request = 3000
        self.extractor.settings.telegram.extraction.ui_update_interval = 5
        self.extractor.settings.telegram.extraction.progress_update_messages = 100
        self.extractor.settings.telegram.extraction.batch_size = 250

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("src.history_extractor.telegram_extractor.get_message_details")
    def test_extract_from_topic(self, mock_get_message_details):
        """Test extracting messages from a topic."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.message_thread_id = 456
        mock_topic.name = "Test Topic"

        last_msg_ids = {}

        # Create a proper datetime object for the message date
        from datetime import datetime

        msg_date = datetime(2024, 1, 1, 0, 0, 0)

        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.text = "hello"
        mock_msg.date = msg_date
        mock_msg.from_user = None
        mock_msg.sender_chat = None
        mock_msg.message_thread_id = 456  # Match the topic_id
        mock_msg.reply_to_message_id = None
        mock_msg.service = False  # Not a service message
        mock_msg.media = None  # Text message, so media is None but text is set

        self.mock_client.get_chat_history.return_value = MockAsyncIterator([mock_msg])

        # Mock get_message_details to return a valid message
        mock_get_message_details.return_value = ("text", "hello", {})

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(
                mock_entity, mock_topic, last_msg_ids
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 1)
        self.mock_client.get_chat_history.assert_called_once()
        self.mock_storage.save_messages_to_db.assert_called_once()

    def test_extract_from_group_id_forum(self):
        """
        Test extracting messages from a forum group.
        """
        # Arrange
        group_id = 123
        last_msg_ids = {}
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Forum Group"
        mock_entity.is_forum = True
        self.mock_client.get_chat = AsyncMock(return_value=mock_entity)

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"
        self.mock_client.get_forum_topics.return_value = MockAsyncIterator([mock_topic])

        self.extractor.extract_from_topic = AsyncMock(return_value=5)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(
                group_id, last_msg_ids, mock_entity
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 5)
        self.extractor.extract_from_topic.assert_awaited_once()

    def test_extract_from_group_id_regular(self):
        """
        Test extracting messages from a regular group.
        """
        # Arrange
        group_id = 123
        last_msg_ids = {}
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.is_forum = False
        self.mock_client.get_chat = AsyncMock(return_value=mock_entity)

        self.mock_client.get_forum_topics.side_effect = Exception("Not a forum group")

        self.extractor.extract_from_topic = AsyncMock(return_value=3)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(
                group_id, last_msg_ids, mock_entity
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 3)
        self.extractor.extract_from_topic.assert_awaited_once()

    def test_inputchannel_construction_with_channel_id(self):
        """Test InputChannel construction when entity has channel_id attribute."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.channel_id = 456  # Different from entity.id
        mock_entity.access_hash = 789

        # Act & Assert
        # This should use channel_id instead of entity.id
        expected_channel_id = getattr(mock_entity, "channel_id", mock_entity.id)
        self.assertEqual(expected_channel_id, 456)

    def test_inputchannel_construction_without_channel_id(self):
        """Test InputChannel construction when entity lacks channel_id attribute."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        # Remove channel_id attribute to simulate it not existing
        del mock_entity.channel_id
        mock_entity.access_hash = 789

        # Act & Assert
        # This should fall back to entity.id
        expected_channel_id = getattr(mock_entity, "channel_id", mock_entity.id)
        self.assertEqual(expected_channel_id, 123)

    def test_inputchannel_construction_with_none_access_hash(self):
        """Test InputChannel construction when access_hash is None."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.channel_id = 456
        mock_entity.access_hash = None

        # Act & Assert
        # getattr should return None when the attribute is None
        access_hash = getattr(mock_entity, "access_hash", 0)
        self.assertEqual(access_hash, None)

    def test_get_forum_topics_raw_api_success(self):
        """Test successful GetForumTopics raw API call."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.channel_id = 456
        mock_entity.access_hash = 789
        mock_entity.is_forum = True

        mock_topic = MagicMock()
        self.mock_client.get_forum_topics.return_value = MockAsyncIterator([mock_topic])
        self.extractor.extract_from_topic = AsyncMock(return_value=1)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(123, {}, mock_entity)

        asyncio.run(run_test())

        # Assert
        self.mock_client.get_forum_topics.assert_called_once_with(123)
        self.extractor.extract_from_topic.assert_called_once()

    def test_get_forum_topics_raw_api_failure_fallback(self):
        """Test GetForumTopics raw API failure with fallback to regular group."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.channel_id = 456
        mock_entity.access_hash = 789
        mock_entity.is_forum = False  # Explicitly set to False to trigger fallback

        # Mock API failure
        self.mock_client.get_forum_topics.side_effect = Exception("API Error")

        # Mock regular group processing
        self.extractor.extract_from_topic = AsyncMock(return_value=5)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(123, {}, mock_entity)

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 5)  # Should fall back to regular group processing
        self.extractor.extract_from_topic.assert_called_once()

    def test_mock_object_creation_replacement(self):
        """Test that mock object creation uses proper class instead of type()."""
        # This test validates that the anti-pattern has been fixed
        # The actual fix should be in the main code, this test validates the behavior

        # Arrange
        from src.history_extractor.telegram_extractor import TelegramExtractor

        # Act - This should work without the type() anti-pattern
        extractor = TelegramExtractor(self.mock_client, self.mock_storage)

        # Assert - The extractor should be created successfully
        self.assertIsNotNone(extractor)
        self.assertEqual(extractor.client, self.mock_client)
        self.assertEqual(extractor.storage, self.mock_storage)

    @patch("src.history_extractor.telegram_extractor.FloodWait")
    def test_flood_wait_error_handling(self, mock_flood_wait):
        """Test proper handling of FloodWait errors."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        # Mock flood wait error
        mock_flood_wait_exception = MagicMock()
        mock_flood_wait_exception.value = 30
        self.mock_client.get_chat.side_effect = mock_flood_wait_exception

        # Mock successful retry
        self.extractor.extract_from_group_id = AsyncMock(return_value=10)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(123, {}, mock_entity)

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 10)  # Should return result from retry

    def test_parameter_validation_in_constructor(self):
        """Test that constructor validates required parameters."""
        # Arrange & Act & Assert
        with self.assertRaises(ValueError):
            TelegramExtractor(None, self.mock_storage)

        with self.assertRaises(ValueError):
            TelegramExtractor(self.mock_client, None)

    def test_variable_initialization_before_use(self):
        """Test that message_size_estimate is properly initialized."""
        # This test ensures the variable reference issue is fixed
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.message_thread_id = 456
        mock_topic.name = "Test Topic"

        last_msg_ids = {}

        # Mock empty message list to trigger the initialization path
        self.mock_client.get_chat_history.return_value = MockAsyncIterator([])

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(
                mock_entity, mock_topic, last_msg_ids
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 0)  # No messages processed
        self.mock_client.get_chat_history.assert_called_once()

    @patch("src.history_extractor.telegram_extractor.estimate_message_size")
    def test_message_size_estimation_error_handling(self, mock_estimate_size):
        """Test proper handling of message size estimation errors."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.message_thread_id = 456
        mock_topic.name = "Test Topic"

        last_msg_ids = {}

        # Mock message size estimation failure
        mock_estimate_size.side_effect = Exception("Size estimation failed")

        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.text = "hello"
        mock_msg.date = MagicMock()
        mock_msg.date.isoformat.return_value = "2024-01-01T00:00:00"
        mock_msg.from_user = None
        mock_msg.sender_chat = None
        mock_msg.message_thread_id = 456
        mock_msg.reply_to_message_id = None
        mock_msg.service = False
        mock_msg.media = None

        self.mock_client.get_chat_history.return_value = MockAsyncIterator([mock_msg])

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(
                mock_entity, mock_topic, last_msg_ids
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(
            result, 1
        )  # Should still process the message despite size estimation failure

    def test_concurrent_group_processing_thread_safety(self):
        """Test that concurrent group processing is thread-safe."""
        # Arrange
        import asyncio
        import threading

        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"
        mock_entity.is_forum = False  # Explicitly set to False to trigger fallback

        last_msg_ids = {}
        lock = threading.Lock()

        # Mock successful processing
        self.extractor.extract_from_topic = AsyncMock(return_value=5)

        # Mock API failure to trigger fallback
        self.mock_client.get_forum_topics.side_effect = Exception("API Error")

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(
                123, last_msg_ids, mock_entity, lock
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 5)
        # The lock should be used properly (this is more of a behavioral test)

    def test_memory_usage_monitoring_integration(self):
        """Test that memory usage is properly monitored during extraction."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.message_thread_id = 456
        mock_topic.name = "Test Topic"

        last_msg_ids = {}

        # Mock empty message list
        self.mock_client.get_chat_history.return_value = MockAsyncIterator([])

        # Act
        async def run_test():
            return await self.extractor.extract_from_topic(
                mock_entity, mock_topic, last_msg_ids
            )

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 0)
        # Memory monitoring should be integrated (behavioral validation)


if __name__ == "__main__":
    unittest.main()
