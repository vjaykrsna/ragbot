import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.synthesis.progress_tracker import ProgressTracker


class TestProgressTracker(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.synthesis_progress_file = "/fake/progress.json"
        self.mock_settings.paths.processed_hashes_file = "/fake/hashes.json"
        self.progress_tracker = ProgressTracker(self.mock_settings)

    def test_load_progress(self):
        """Test loading the progress file."""
        m_open = mock_open(read_data='{"last_processed_index": 123}')
        with patch("builtins.open", m_open):
            progress = self.progress_tracker.load_progress()
            self.assertEqual(progress, 123)

    def test_save_progress(self):
        """Test saving the progress file."""
        m_open = mock_open()
        with patch("builtins.open", m_open):
            self.progress_tracker.save_progress(456)
            handle = m_open()
            written_content = "".join(
                call.args[0] for call in handle.write.call_args_list
            )
            self.assertEqual(
                json.loads(written_content), {"last_processed_index": 456}
            )

    @patch("os.path.exists", return_value=True)
    def test_load_processed_hashes(self, mock_exists):
        """Test loading the processed hashes file."""
        m_open = mock_open(read_data='["hash1", "hash2"]')
        with patch("builtins.open", m_open):
            hashes = self.progress_tracker.load_processed_hashes()
            self.assertEqual(hashes, {"hash1", "hash2"})

    @patch("os.path.exists", return_value=True)
    def test_save_processed_hashes(self, mock_exists):
        """Test saving the processed hashes file."""
        m_open = mock_open()
        with patch("builtins.open", m_open):
            self.progress_tracker.save_processed_hashes({"hash1", "hash2"})
            handle = m_open()
            written_content = "".join(
                call.args[0] for call in handle.write.call_args_list
            )
            self.assertEqual(set(json.loads(written_content)), {"hash1", "hash2"})
