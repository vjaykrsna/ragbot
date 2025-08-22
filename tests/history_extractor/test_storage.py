import unittest
from unittest.mock import MagicMock, patch

from src.history_extractor.storage import Storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_app_context = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_app_context.settings = self.mock_settings
        self.storage = Storage(self.mock_app_context)

    def tearDown(self):
        # Clear the message buffer to prevent resource warnings
        if hasattr(self, "storage") and self.storage.message_buffer:
            self.storage.message_buffer.clear()

    def test_save_messages_to_db(self):
        """
        Test saving messages to the database.
        """
        # Arrange
        mock_db = MagicMock()
        self.mock_app_context.db = mock_db
        # Set the buffer size to a real value instead of MagicMock
        self.storage.buffer_size = 1000
        messages = [{"id": 1, "content": "hello"}]

        # Act
        self.storage.save_messages_to_db("chat_title", 123, messages)

        # Assert - with buffering, insert_messages is not called immediately
        # but the messages should be stored in the buffer
        self.assertEqual(len(self.storage.message_buffer), 1)
        mock_db.insert_messages.assert_not_called()

    def test_save_messages_to_db_flushes_buffer(self):
        """
        Test that saving enough messages flushes the buffer.
        """
        # Arrange
        mock_db = MagicMock()
        self.mock_app_context.db = mock_db
        # Set the buffer size to a real value instead of MagicMock
        self.storage.buffer_size = 1000
        messages = [{"id": i, "content": f"message {i}"} for i in range(1000)]

        # Act
        self.storage.save_messages_to_db("chat_title", 123, messages)

        # Assert - with 1000 messages, buffer should be flushed
        mock_db.insert_messages.assert_called_once()

    def test_load_last_msg_ids(self):
        """
        Test loading the last processed message ID for each topic.
        """
        # Arrange
        with patch("src.history_extractor.storage.os.path.exists") as mock_exists:
            mock_exists.return_value = False

            # Act
            result = self.storage.load_last_msg_ids()

            # Assert
            self.assertEqual(result, {})

    def test_save_last_msg_ids(self):
        """
        Test saving the last processed message ID for each topic.
        """
        # Arrange
        with patch(
            "src.history_extractor.storage.open", unittest.mock.mock_open()
        ) as mock_open:
            data = {"key": 123}

            # Act
            self.storage.save_last_msg_ids(data)

            # Assert
            mock_open.assert_called_once_with(
                self.mock_settings.paths.tracking_file, "w"
            )
