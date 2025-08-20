import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.history_extractor.storage import Storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.mock_app_context = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_app_context.settings = self.mock_settings
        self.storage = Storage(self.mock_app_context)

    def test_save_messages_to_db(self):
        """
        Test saving messages to the database.
        """
        # Arrange
        mock_db = MagicMock()
        self.mock_app_context.db = mock_db
        self.mock_settings.get.return_value = "2023-01-01T00:00:00Z"
        messages = [{"id": 1, "content": "hello"}]

        # Act
        self.storage.save_messages_to_db("chat_title", 123, messages)

        # Assert
        mock_db.insert_messages.assert_called_once()

    def test_load_last_msg_ids(self):
        """
        Test loading the last message IDs from a file.
        """
        # Arrange
        self.mock_settings.paths.tracking_file = "/fake/tracking.json"
        m_open = mock_open(read_data='{"key": 123}')
        with patch("builtins.open", m_open), patch("os.path.exists", return_value=True):
            # Act
            result = self.storage.load_last_msg_ids()

            # Assert
            self.assertEqual(result, {"key": 123})

    def test_save_last_msg_ids(self):
        """
        Test saving the last message IDs to a file.
        """
        # Arrange
        self.mock_settings.paths.tracking_file = "/fake/tracking.json"
        m_open = mock_open()
        with patch("builtins.open", m_open):
            # Act
            self.storage.save_last_msg_ids({"key": 456})

            # Assert
            handle = m_open()
            written_content = "".join(
                call.args[0] for call in handle.write.call_args_list
            )
            self.assertEqual(json.loads(written_content), {"key": 456})
