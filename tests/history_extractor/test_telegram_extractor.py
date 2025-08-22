import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.history_extractor.telegram_extractor import TelegramExtractor


class TestTelegramExtractor(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_client = MagicMock()
        self.mock_storage = MagicMock()
        self.extractor = TelegramExtractor(self.mock_client, self.mock_storage)
        # Set up the settings with real values instead of MagicMock
        self.extractor.settings = MagicMock()
        self.extractor.settings.messages_per_request = 3000
        self.extractor.settings.ui_update_interval = 5

    def test_extract_from_topic(self):
        """
        Test extracting messages from a single topic.
        """
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Group"
        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"
        last_msg_ids = {"123_456": 0}

        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.text = "hello"
        mock_msg.media = None
        mock_msg.entities = None
        mock_msg.date = MagicMock()
        mock_msg.date.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_msg.sender_id = 789
        mock_msg.reply_to_msg_id = None

        # Create proper async iterator
        class MockAsyncIterator:
            def __init__(self, items):
                self.items = items
                self.iter = iter(self.items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.iter)
                except StopIteration:
                    raise StopAsyncIteration

        # Make iter_messages return the async iterator directly
        self.mock_client.iter_messages = MagicMock(
            return_value=MockAsyncIterator([mock_msg])
        )

        # Mock tqdm context manager
        mock_pbar = MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mock_pbar.__exit__.return_value = None

        with patch(
            "src.history_extractor.telegram_extractor.get_message_details"
        ) as mock_get_details:
            mock_get_details.return_value = ("text", "hello", {})

            # Run the async method using asyncio.run
            async def run_test():
                return await self.extractor.extract_from_topic(
                    mock_entity, mock_topic, last_msg_ids
                )

            result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 1)
        self.mock_client.iter_messages.assert_called_once()

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
        mock_entity.forum = True

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"

        # Mock client methods
        self.mock_client.get_entity = AsyncMock(return_value=mock_entity)

        # Mock the GetForumTopicsRequest
        with patch(
            "src.history_extractor.telegram_extractor.GetForumTopicsRequest"
        ) as mock_request:
            mock_request.return_value = MagicMock()

            # Mock the client call - this needs to be an awaitable
            mock_topics_result = MagicMock()
            mock_topics_result.topics = [mock_topic]

            # Fix: Create a proper async function for the client call
            async def mock_client_call(request):
                return mock_topics_result

            self.mock_client.side_effect = mock_client_call

            # Mock extract_from_topic
            self.extractor.extract_from_topic = AsyncMock(return_value=5)

            # Act
            async def run_test():
                return await self.extractor.extract_from_group_id(
                    group_id, last_msg_ids
                )

            result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 5)

    def test_extract_from_group_id_regular(self):
        """
        Test extracting messages from a regular group.
        """
        # Arrange
        group_id = 123
        last_msg_ids = {}
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.title = "Test Regular Group"
        mock_entity.forum = False

        # Mock client methods
        self.mock_client.get_entity = AsyncMock(return_value=mock_entity)
        self.extractor.extract_from_topic = AsyncMock(return_value=3)

        # Act
        async def run_test():
            return await self.extractor.extract_from_group_id(group_id, last_msg_ids)

        result = asyncio.run(run_test())

        # Assert
        self.assertEqual(result, 3)
