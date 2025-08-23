import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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
        """Set up test fixtures."""
        self.mock_client = AsyncMock()  # Changed to AsyncMock
        self.mock_storage = MagicMock()
        self.extractor = TelegramExtractor(self.mock_client, self.mock_storage)
        # Set up the settings with real values instead of MagicMock
        mock_extraction_settings = MagicMock()
        mock_extraction_settings.messages_per_request = 3000
        mock_extraction_settings.ui_update_interval = 5
        mock_extraction_settings.progress_update_messages = 100
        mock_extraction_settings.batch_size = 250
        self.extractor.settings = MagicMock()
        self.extractor.settings.extraction = mock_extraction_settings

    @patch("src.history_extractor.telegram_extractor.get_message_details")
    def test_extract_from_topic(self, mock_get_message_details):
        """Test extracting messages from a topic."""
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        last_msg_ids = {}

        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.text = "hello"
        mock_msg.date = MagicMock()
        mock_msg.date.isoformat.return_value = "2024-01-01T00:00:00"
        mock_msg.from_user = None
        mock_msg.sender_chat = None
        mock_msg.message_thread_id = 456  # Match the topic_id
        mock_msg.reply_to_message_id = None
        mock_msg.service = False  # Not a service message
        mock_msg.media = None  # Text message, so media is None but text is set

        # Mock the async generator properly
        async def async_generator(items):
            for item in items:
                yield item

        self.mock_client.get_chat_history = MagicMock(
            return_value=async_generator([mock_msg])
        )

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
        # Changed to use AsyncMock for get_chat
        self.mock_client.get_chat = AsyncMock(return_value=mock_entity)

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"
        mock_topics_result = MagicMock()
        mock_topics_result.topics = [mock_topic]
        # Changed to use AsyncMock for invoke
        self.mock_client.invoke = AsyncMock(return_value=mock_topics_result)

        # Changed to use AsyncMock
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
        # Changed to use AsyncMock for get_chat
        self.mock_client.get_chat = AsyncMock(return_value=mock_entity)

        # Mock the GetForumTopics call to raise an exception (simulating a regular group)
        # Changed to use AsyncMock for invoke
        self.mock_client.invoke = AsyncMock(side_effect=Exception("Not a forum group"))

        # Changed to use AsyncMock
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


if __name__ == "__main__":
    unittest.main()
