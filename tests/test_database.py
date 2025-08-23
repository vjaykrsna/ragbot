import os
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from src.core.config import PathSettings
from src.core.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up a temporary database for testing."""
        self.test_dir = "temp_test_db_dir"
        os.makedirs(self.test_dir, exist_ok=True)

        # Patch get_project_root to use the temporary test directory
        self.mock_get_root = patch(
            "src.core.config.get_project_root", return_value=self.test_dir
        )
        self.mock_get_root.start()

        self.settings = PathSettings()
        self.db = Database(self.settings)
        # Use a single in-memory connection for the duration of the test
        self.connection = sqlite3.connect(":memory:")
        # We need to create the tables manually for the in-memory connection
        self.db._create_tables(self.connection)

        # Patch the _get_connection method to always return our single connection
        self.managed_connection_mock = MagicMock()
        self.managed_connection_mock.__enter__.return_value = self.connection
        self.managed_connection_mock.__exit__.return_value = None
        self.db._get_connection = MagicMock(return_value=self.managed_connection_mock)

    def tearDown(self):
        """Close the connection and remove the temporary directory."""
        # Close all connections properly
        if hasattr(self, "connection") and self.connection:
            self.connection.close()
        if hasattr(self, "managed_connection_mock"):
            # Ensure any mock connections are properly handled
            pass
        self.mock_get_root.stop()
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization_creates_directory(self):
        """Test that the __init__ method creates the database directory."""
        self.assertTrue(os.path.exists(self.settings.db_dir))

    def test_insert_and_get_text_message(self):
        """Test inserting and retrieving a simple text message."""
        message = {
            "id": 1,
            "date": "2024-01-01T12:00:00",
            "sender_id": "user1",
            "message_type": "text",
            "content": "Hello, world!",
            "extra_data": {},
            "reply_to_msg_id": None,
            "topic_id": 101,
            "topic_title": "General",
            "source_name": "Test Group",
            "source_group_id": 202,
            "ingestion_timestamp": "2024-01-01T12:00:01",
        }
        self.db.insert_messages([message])

        messages = list(self.db.get_all_messages())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], 1)
        self.assertEqual(messages[0]["content"], "Hello, world!")

    def test_insert_and_get_poll_message(self):
        """Test inserting and retrieving a poll message."""
        poll_message = {
            "id": 2,
            "date": "2024-01-01T13:00:00",
            "sender_id": "user456",
            "message_type": "poll",
            "content": "What is your favorite color?",
            "extra_data": "{}",  # Convert to string as expected by the database
            "reply_to_msg_id": None,
            "topic_id": 101,
            "topic_title": "General",
            "source_name": "Test Group",
            "source_group_id": 202,
            "ingestion_timestamp": "2024-01-01T13:00:01",
        }
        self.db.insert_messages([poll_message])

        # Check the messages table for the poll question
        messages = list(self.db.get_all_messages())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], 2)
        self.assertEqual(messages[0]["content"], "What is your favorite color?")
        self.assertEqual(messages[0]["message_type"], "poll")

        # Since we've unified storage, we don't have separate polls and poll_options tables
        # The poll data is now stored in the content and extra_data fields


if __name__ == "__main__":
    unittest.main()
