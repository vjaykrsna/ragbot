import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.synthesis.failed_batch_handler import FailedBatchHandler


class TestFailedBatchHandler(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.failed_batches_file = "/fake/failed_batches.jsonl"
        self.failed_batch_handler = FailedBatchHandler(self.mock_settings)

    def test_save_failed_batch(self):
        """Test saving a failed batch."""
        m_open = mock_open()
        with (
            patch("builtins.open", m_open),
            patch("src.synthesis.failed_batch_handler.os.makedirs"),
        ):
            self.failed_batch_handler.save_failed_batch(["conv1"], "error", "response")
            handle = m_open()
            handle.write.assert_called()
