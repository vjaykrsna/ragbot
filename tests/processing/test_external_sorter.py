import json
import unittest
from unittest.mock import MagicMock, call, mock_open, patch

from src.processing.external_sorter import ExternalSorter


class TestExternalSorter(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"id": 1, "date": "2023-01-01T12:05:00"},
            {"id": 2, "date": "2023-01-01T12:01:00"},
            {"id": 3, "date": "2023-01-01T12:03:00"},
            {"id": 4, "date": "2023-01-01T12:02:00"},
            {"id": 5, "date": "2023-01-01T12:04:00"},
            {"id": 6, "date": "invalid-date"},
        ]
        self.mock_data_source = MagicMock()
        self.mock_data_source.__iter__.return_value = iter(self.records)

    @patch("os.remove")
    @patch("tempfile.mkstemp")
    def test_write_sorted_chunks(self, mock_mkstemp, mock_os_remove):
        """
        Test the chunk writing and sorting logic.
        """
        # Arrange
        sorter = ExternalSorter(chunk_size=2, use_gzip=False)
        mock_mkstemp.side_effect = [
            (1, "/tmp/chunk1"),
            (2, "/tmp/chunk2"),
            (3, "/tmp/chunk3"),
        ]
        m_open = mock_open()

        with patch("builtins.open", m_open):
            # Act
            chunk_paths = sorter._write_sorted_chunks(self.mock_data_source)

        # Assert
        self.assertEqual(chunk_paths, ["/tmp/chunk1", "/tmp/chunk2", "/tmp/chunk3"])

        # Check the content written to the first file
        handle = m_open()
        write_calls = handle.write.call_args_list

        # Expected content for the first chunk (records 1 and 2, sorted by date)
        expected_line1 = json.dumps({"id": 2, "date": "2023-01-01T12:01:00"}) + "\n"
        expected_line2 = json.dumps({"id": 1, "date": "2023-01-01T12:05:00"}) + "\n"

        # This is tricky because all writes go to the same mock_open handle.
        # We just check that the sorted lines were written.
        written_content = "".join(c.args[0] for c in write_calls)
        self.assertIn(expected_line1, written_content)
        self.assertIn(expected_line2, written_content)

    @patch("os.remove")
    def test_merge_sorted_chunks(self, mock_os_remove):
        """
        Test the k-way merge logic.
        """
        # Arrange
        sorter = ExternalSorter(use_gzip=False)

        # Create mock file content
        chunk1_content = (
            json.dumps({"id": 2, "date": "2023-01-01T12:01:00"})
            + "\n"
            + json.dumps({"id": 5, "date": "2023-01-01T12:04:00"})
            + "\n"
        )
        chunk2_content = (
            json.dumps({"id": 3, "date": "2023-01-01T12:02:00"})
            + "\n"
            + json.dumps({"id": 4, "date": "2023-01-01T12:03:00"})
            + "\n"
        )

        mock_files = {
            "/tmp/chunk1": chunk1_content,
            "/tmp/chunk2": chunk2_content,
        }

        m_open = mock_open()
        m_open.side_effect = lambda path, mode, **kwargs: mock_open(
            read_data=mock_files[path]
        )().__enter__()

        with patch("builtins.open", m_open):
            # Act
            sorted_stream = sorter._merge_sorted_chunks(["/tmp/chunk1", "/tmp/chunk2"])
            sorted_records = list(sorted_stream)

        # Assert
        sorted_ids = [r["id"] for r in sorted_records]
        self.assertEqual(sorted_ids, [2, 3, 4, 5])
        mock_os_remove.assert_has_calls([call("/tmp/chunk1"), call("/tmp/chunk2")])

    @patch("os.remove")
    @patch("tempfile.mkstemp")
    @patch("gzip.open")
    def test_sort_with_gzip(self, mock_gzip_open, mock_mkstemp, mock_os_remove):
        """
        Test that gzip is used when enabled.
        """
        # Arrange
        sorter = ExternalSorter(chunk_size=10, use_gzip=True)
        mock_mkstemp.return_value = (1, "/tmp/chunk1.gz")  # Use a dummy file descriptor

        # Act
        m_open = mock_open()
        with patch("builtins.open", mock_open()), patch("gzip.open", m_open):
            # We only need to test the write phase
            sorter._write_sorted_chunks(self.mock_data_source)

        # Assert
        # Check that gzip.open was used for writing
        m_open.assert_called_once_with("/tmp/chunk1.gz", "wt", encoding="utf-8")

    def test_sort_empty_data_source(self):
        """
        Test that the sorter handles an empty data source gracefully.
        """
        # Arrange
        sorter = ExternalSorter()
        self.mock_data_source.__iter__.return_value = iter([])

        # Act
        sorted_records = list(sorter.sort(self.mock_data_source))

        # Assert
        self.assertEqual(sorted_records, [])
