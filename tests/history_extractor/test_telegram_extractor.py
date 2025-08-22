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
        mock_msg.date = MagicMock()
        mock_msg.date.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_msg.from_user = MagicMock()
        mock_msg.from_user.id = 789
        mock_msg.reply_to_message_id = None
        mock_msg.message_thread_id = 456  # Match the topic_id in the test
        mock_msg.service = False  # Explicitly set service to False

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

        # Make get_chat_history return the async iterator directly
        self.mock_client.get_chat_history = MagicMock(
            return_value=MockAsyncIterator([mock_msg])
        )

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
        self.mock_client.get_chat.return_value = mock_entity

        mock_topic = MagicMock()
        mock_topic.id = 456
        mock_topic.title = "Test Topic"
        mock_topics_result = MagicMock()
        mock_topics_result.topics = [mock_topic]
        self.mock_client.invoke.return_value = mock_topics_result

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
        mock_entity.is_forum = False
        self.mock_client.get_chat.return_value = mock_entity

        # Mock the GetForumTopics call to raise an exception (simulating a regular group)
        self.mock_client.invoke.side_effect = Exception("Not a forum group")

        self.extractor.extract_from_topic = AsyncMock()

        # Act
        await self.extractor.extract_from_group_id(123, {})

        # Assert
        self.extractor.extract_from_topic.assert_awaited_once()
