from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.processing.pipeline import DataProcessingPipeline


@pytest.fixture
def pipeline_setup():
    """Set up common test fixtures for DataProcessingPipeline tests."""
    mock_settings = MagicMock()
    mock_settings.paths.processed_data_dir = "/fake/processed"
    mock_settings.paths.processed_conversations_file = "conversations.json"

    mock_data_source = MagicMock()
    mock_sorter = MagicMock()
    mock_anonymizer = MagicMock()
    mock_conv_builder = MagicMock()

    pipeline = DataProcessingPipeline(
        settings=mock_settings,
        data_source=mock_data_source,
        sorter=mock_sorter,
        anonymizer=mock_anonymizer,
        conv_builder=mock_conv_builder,
    )

    return {
        "pipeline": pipeline,
        "mock_settings": mock_settings,
        "mock_data_source": mock_data_source,
        "mock_sorter": mock_sorter,
        "mock_anonymizer": mock_anonymizer,
        "mock_conv_builder": mock_conv_builder,
    }


def test_run_pipeline_orchestration(pipeline_setup):
    """
    Test that the run method correctly orchestrates the pipeline components.
    """
    # Arrange: Set up mocks
    mock_sorted_stream = [MagicMock()]
    mock_processed_stream = [MagicMock()]
    mock_conversation_stream = [MagicMock()]

    pipeline_setup["mock_sorter"].sort.return_value = mock_sorted_stream
    pipeline_setup[
        "mock_anonymizer"
    ].process_stream.return_value = mock_processed_stream
    pipeline_setup[
        "mock_conv_builder"
    ].process_stream.return_value = mock_conversation_stream
    pipeline_setup["pipeline"]._write_conversations = MagicMock(return_value=1)

    with patch("os.makedirs") as mock_makedirs, patch("builtins.open", mock_open()):
        # Act: Run the pipeline
        pipeline_setup["pipeline"].run()

        # Assert: Verify component interactions
        pipeline_setup["mock_sorter"].sort.assert_called_once_with(
            pipeline_setup["mock_data_source"]
        )
        pipeline_setup["mock_conv_builder"].process_stream.assert_called_once()
        pipeline_setup["mock_anonymizer"].persist.assert_called_once()

        # Assert: Verify file operations
        mock_makedirs.assert_called_once_with("/fake/processed", exist_ok=True)

        # Assert: Verify _write_conversations was called
        pipeline_setup["pipeline"]._write_conversations.assert_called_once()


def test_normalize_numbers(pipeline_setup):
    """
    Test the internal number normalization logic.
    """
    test_text = (
        "The price is 1,234.56 INR, which is about 15 million ₹ or 99% of the budget."
    )
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
    result = pipeline_setup["pipeline"]._normalize_numbers(test_text)
    assert result == expected


def test_process_record(pipeline_setup):
    """
    Test the processing of a single record.
    """
    record = {"sender_id": "user_abc", "content": "Value is 500 kg."}
    pipeline_setup["mock_anonymizer"].anonymize.return_value = "anon_user_abc"

    processed_record = pipeline_setup["pipeline"]._process_record(
        record, pipeline_setup["mock_anonymizer"]
    )

    pipeline_setup["mock_anonymizer"].anonymize.assert_called_once_with("user_abc")
    assert processed_record["sender_id"] == "anon_user_abc"
    assert len(processed_record["normalized_values"]) == 1
    assert processed_record["normalized_values"][0]["value"] == 500.0
    assert processed_record["normalized_values"][0]["unit"] == "kg"
