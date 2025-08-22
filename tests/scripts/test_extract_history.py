import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from src.core.config import PathSettings
from src.scripts import extract_history


class TestExtractHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_path_settings = PathSettings()
        # Override paths to use the temp dir
        self.mock_path_settings.root_dir = self.temp_dir.name
        self.mock_path_settings.raw_data_dir = os.path.join(self.temp_dir.name, "raw")
        self.mock_path_settings.tracking_file = os.path.join(
            self.temp_dir.name, "tracking.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("src.history_extractor.storage.json.dump")
    @patch("src.scripts.extract_history.initialize_app")
    @patch("src.scripts.extract_history.Client")
    @patch("src.scripts.extract_history.Storage")
    @patch("src.scripts.extract_history.os.makedirs")
    @patch("src.scripts.extract_history.open", new_callable=mock_open, read_data="{}")
    def test_main_success_path(
        self,
        mock_file,
        mock_makedirs,
        mock_storage,
        mock_client,
        mock_init_app,
        mock_json_dump,
    ):
        """
        Test the main extraction script's successful execution path with mocked dependencies.
        """
        # --- Setup Mocks ---
        mock_app_context = MagicMock()
        mock_settings = MagicMock()
        mock_settings.telegram.group_ids = [12345]
        mock_settings.paths = self.mock_path_settings
        mock_app_context.settings = mock_settings
        mock_init_app.return_value = mock_app_context

        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance

        # Mock the async context manager for the client
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client_instance.get_me.return_value = MagicMock(
            first_name="Test", username="testuser"
        )

        # Mock entity and message fetching
        mock_entity = MagicMock(id=12345, is_forum=False, title="Test Group")
        mock_client_instance.get_chat.return_value = mock_entity

        mock_message = MagicMock()
        mock_message.id = 1
        mock_message.date = datetime.now(timezone.utc)
        mock_message.from_user = MagicMock()
        mock_message.from_user.id = 101
        mock_message.text = "Hello"
        mock_message.media = None
        mock_message.reply_to_message_id = None

        # Create a proper async iterator mock
        class MockAsyncIterator:
            def __init__(self, items):
                self._items = iter(items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._items)
                except StopIteration:
                    raise StopAsyncIteration

        # get_chat_history is a regular method that returns an async iterator
        mock_client_instance.get_chat_history = MagicMock(
            return_value=MockAsyncIterator([mock_message])
        )

        # --- Run the main function ---
        asyncio.run(extract_history.main())

        # --- Assertions ---
        mock_init_app.assert_called_once()
        mock_client.assert_called_once()
        mock_client_instance.get_me.assert_called_once()
        mock_client_instance.get_chat.assert_called_with(12345)
        mock_storage.assert_called_once_with(mock_app_context)
