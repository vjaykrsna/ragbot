import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.processing.pipeline import DataProcessingPipeline


class TestDataProcessingPipeline(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.processed_data_dir = "/fake/processed"
        self.mock_settings.paths.processed_conversations_file = "conversations.json"

        self.mock_data_source = MagicMock()
        self.mock_sorter = MagicMock()
        self.mock_anonymizer = MagicMock()
        self.mock_conv_builder = MagicMock()

        self.pipeline = DataProcessingPipeline(
            settings=self.mock_settings,
            data_source=self.mock_data_source,
            sorter=self.mock_sorter,
            anonymizer=self.mock_anonymizer,
            conv_builder=self.mock_conv_builder,
        )

    def test_run_pipeline_orchestration(self):
        """
        Test that the run method correctly orchestrates the pipeline components.
        """
        # Arrange: Set up mock return values
        mock_records = [
            {"sender_id": "user1", "content": "Hello, price is 1,000 rs."},
            {"sender_id": "user2", "content": "Thanks!"},
        ]
        mock_conversations = [{"conversation_id": 1, "messages": mock_records}]

        self.mock_sorter.sort.return_value = iter(mock_records)

        # Define a side effect that consumes the input stream and returns the desired mock output
        def consume_and_return_conversations(stream):
            list(stream)  # Consume the generator to trigger upstream mocks
            return iter(mock_conversations)

        self.mock_conv_builder.process_stream.side_effect = (
            consume_and_return_conversations
        )
        self.mock_anonymizer.anonymize.side_effect = lambda x: f"anon_{x}"

        # Act: Run the pipeline
        with (
            patch("builtins.open", mock_open()) as mocked_file,
            patch("os.makedirs") as mock_makedirs,
        ):
            self.pipeline.run()

        # Assert: Verify that the components were called correctly
        self.mock_sorter.sort.assert_called_once_with(self.mock_data_source)
        self.mock_anonymizer.anonymize.assert_any_call("user1")
        self.mock_anonymizer.anonymize.assert_any_call("user2")
        self.mock_conv_builder.process_stream.assert_called_once()
        self.mock_anonymizer.persist.assert_called_once()

        # Assert: Verify file operations
        mock_makedirs.assert_called_once_with("/fake/processed", exist_ok=True)
        mocked_file.assert_called_once_with(
            "/fake/processed/conversations.json", "w", encoding="utf-8"
        )
        handle = mocked_file()

        # Check that the JSON output was written correctly
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        written_data = json.loads(written_content)
        self.assertEqual(written_data, mock_conversations)

    def test_normalize_numbers(self):
        """
        Test the internal number normalization logic.
        """
        test_text = "The price is 1,234.56 INR, which is about 15 million ₹ or 99% of the budget."
        expected = [
            {
                "span": "1,234.56 INR",
                "value": 1234.56,
                "unit": "inr",
                "confidence": "medium",
            },
            {
                "span": "15 million",
                "value": 15.0,
                "unit": "million",
                "confidence": "medium",
            },
            {"span": "99%", "value": 99.0, "unit": "%", "confidence": "medium"},
        ]
        result = self.pipeline._normalize_numbers(test_text)
        self.assertEqual(result, expected)

    def test_process_record(self):
        """
        Test the processing of a single record.
        """
        record = {"sender_id": "user_abc", "content": "Value is 500 kg."}
        self.mock_anonymizer.anonymize.return_value = "anon_user_abc"

        processed_record = self.pipeline._process_record(record, self.mock_anonymizer)

        self.mock_anonymizer.anonymize.assert_called_once_with("user_abc")
        self.assertEqual(processed_record["sender_id"], "anon_user_abc")
        self.assertEqual(len(processed_record["normalized_values"]), 1)
        self.assertEqual(processed_record["normalized_values"][0]["value"], 500.0)
        self.assertEqual(processed_record["normalized_values"][0]["unit"], "kg")
