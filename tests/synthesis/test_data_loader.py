import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.synthesis.data_loader import DataLoader


class TestDataLoader(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.processed_conversations_file = "/fake/convos.json"
        self.mock_settings.paths.prompt_file = "/fake/prompt.md"
        self.data_loader = DataLoader(self.mock_settings)

    def test_load_processed_data_success(self):
        """
        Test successfully loading conversation data from a JSON file.
        """
        mock_data = [{"id": 1, "conversation": "hello"}]
        m_open = mock_open(read_data=json.dumps(mock_data))
        with patch("builtins.open", m_open):
            result = self.data_loader.load_processed_data()
            self.assertEqual(result, mock_data)
            m_open.assert_called_once_with(
                "/fake/convos.json", "r", encoding="utf-8"
            )

    def test_load_processed_data_file_not_found(self):
        """
        Test handling of a missing conversation file.
        """
        m_open = mock_open()
        m_open.side_effect = FileNotFoundError
        with patch("builtins.open", m_open):
            result = self.data_loader.load_processed_data()
            self.assertEqual(result, [])

    def test_load_processed_data_json_decode_error(self):
        """
        Test handling of a corrupted/empty conversation file.
        """
        m_open = mock_open(read_data="not json")
        with patch("builtins.open", m_open):
            result = self.data_loader.load_processed_data()
            self.assertEqual(result, [])

    def test_load_prompt_template_success(self):
        """
        Test successfully loading the prompt template.
        """
        prompt_content = "This is the prompt."
        m_open = mock_open(read_data=prompt_content)
        with patch("builtins.open", m_open):
            result = self.data_loader.load_prompt_template()
            self.assertEqual(result, prompt_content)
            m_open.assert_called_once_with("/fake/prompt.md", "r", encoding="utf-8")

    def test_load_prompt_template_file_not_found(self):
        """
        Test handling of a missing prompt file.
        """
        m_open = mock_open()
        m_open.side_effect = FileNotFoundError
        with patch("builtins.open", m_open):
            result = self.data_loader.load_prompt_template()
            self.assertIsNone(result)
