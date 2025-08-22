import unittest
from unittest.mock import AsyncMock, MagicMock

from src.history_extractor.telegram_extractor import TelegramExtractor


class TestTelegramExtractor(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = AsyncMock()
        self.mock_storage = MagicMock()
        self.extractor = TelegramExtractor(self.mock_client, self.mock_storage)

    async def test_extract_from_topic(self):
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

        await self.extractor.extract_from_topic(mock_entity, mock_topic, last_msg_ids)

        # Assert
        self.mock_storage.save_messages_to_db.assert_called_once()

    async def test_extract_from_group_id_forum(self):
        """
        Test extracting messages from a forum group.
        """
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.forum = True
        self.mock_client.get_entity.return_value = mock_entity

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"
        mock_topics_result = MagicMock()
        mock_topics_result.topics = [mock_topic]
        self.mock_client.return_value = mock_topics_result

        self.extractor.extract_from_topic = AsyncMock()

        # Act
        await self.extractor.extract_from_group_id(123, {})

        # Assert
        self.extractor.extract_from_topic.assert_awaited_once()

    async def test_extract_from_group_id_regular(self):
        """
        Test extracting messages from a regular group.
        """
        # Arrange
        mock_entity = MagicMock()
        mock_entity.id = 123
        mock_entity.forum = False
        self.mock_client.get_entity.return_value = mock_entity

        self.extractor.extract_from_topic = AsyncMock()

        # Act
        await self.extractor.extract_from_group_id(123, {})

        # Assert
        self.extractor.extract_from_topic.assert_awaited_once()
