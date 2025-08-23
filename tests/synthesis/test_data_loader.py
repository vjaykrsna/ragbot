import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.synthesis.data_loader import DataLoader


class TestDataLoader(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.prompt_file = "/fake/prompt.md"
        self.mock_db = MagicMock()
        self.data_loader = DataLoader(self.mock_settings, self.mock_db)

    def test_load_processed_data_success(self):
        """
        Test successfully loading conversation data from the database.
        """
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock database results in pages
        mock_cursor.description = [
            ("id", None, None, None, None, None, None),
            ("source_group_id", None, None, None, None, None, None),
            ("topic_id", None, None, None, None, None, None),
            ("date", None, None, None, None, None, None),
            ("sender_id", None, None, None, None, None, None),
            ("message_type", None, None, None, None, None, None),
            ("content", None, None, None, None, None, None),
            ("extra_data", None, None, None, None, None, None),
            ("reply_to_msg_id", None, None, None, None, None, None),
            ("topic_title", None, None, None, None, None, None),
            ("source_name", None, None, None, None, None, None),
            ("ingestion_timestamp", None, None, None, None, None, None),
        ]

        # Mock database rows in pages
        mock_rows_page1 = [
            (
                1,
                100,
                0,
                "2024-01-01T10:00:00",
                "user1",
                "text",
                "Hello",
                "{}",
                None,
                "General",
                "Test Group",
                "2024-01-01T10:00:00",
            ),
            (
                2,
                100,
                0,
                "2024-01-01T10:01:00",
                "user2",
                "text",
                "Hi there",
                "{}",
                1,
                "General",
                "Test Group",
                "2024-01-01T10:01:00",
            ),
        ]
        mock_rows_page2 = []  # Empty page to stop pagination

        mock_cursor.fetchall.side_effect = [mock_rows_page1, mock_rows_page2]

        # Expected result after grouping
        expected_result = [
            {
                "ingestion_timestamp": "2024-01-01T10:00:00",
                "ingestion_hash": "100_0",
                "source_files": ["Test Group"],
                "source_names": ["Test Group"],
                "conversation": [
                    {
                        "id": 1,
                        "date": "2024-01-01T10:00:00",
                        "sender_id": "user1",
                        "content": "Hello",
                        "normalized_values": [],
                    },
                    {
                        "id": 2,
                        "date": "2024-01-01T10:01:00",
                        "sender_id": "user2",
                        "content": "Hi there",
                        "normalized_values": [],
                    },
                ],
                "message_count": 2,
            }
        ]

        with patch.object(
            self.data_loader.db, "_get_connection"
        ) as mock_get_connection:
            mock_get_connection.return_value.__enter__.return_value = mock_conn
            result = self.data_loader.load_processed_data()
            self.assertEqual(result, expected_result)

    def test_load_processed_data_empty_database(self):
        """
        Test loading conversation data from an empty database.
        """
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock empty database results
        mock_cursor.description = [
            ("id", None, None, None, None, None, None),
            ("source_group_id", None, None, None, None, None, None),
            ("topic_id", None, None, None, None, None, None),
            ("date", None, None, None, None, None, None),
            ("sender_id", None, None, None, None, None, None),
            ("message_type", None, None, None, None, None, None),
            ("content", None, None, None, None, None, None),
            ("extra_data", None, None, None, None, None, None),
            ("reply_to_msg_id", None, None, None, None, None, None),
            ("topic_title", None, None, None, None, None, None),
            ("source_name", None, None, None, None, None, None),
            ("ingestion_timestamp", None, None, None, None, None, None),
        ]
        mock_cursor.fetchall.return_value = []

        with patch.object(
            self.data_loader.db, "_get_connection"
        ) as mock_get_connection:
            mock_get_connection.return_value.__enter__.return_value = mock_conn
            result = self.data_loader.load_processed_data()
            self.assertEqual(result, [])

    def test_load_prompt_template_success(self):
        """
        Test successfully loading the prompt template.
        """
        m_open = mock_open(read_data="# Test Prompt Template")
        with patch("builtins.open", m_open):
            result = self.data_loader.load_prompt_template()
            self.assertEqual(result, "# Test Prompt Template")

    def test_load_prompt_template_file_not_found(self):
        """
        Test loading the prompt template when the file is not found.
        """
        with patch("builtins.open", mock_open()) as m_open:
            m_open.side_effect = FileNotFoundError("File not found")
            result = self.data_loader.load_prompt_template()
            self.assertIsNone(result)
