import json
from unittest.mock import MagicMock, patch

import pytest
from pyrate_limiter import Limiter

from src.synthesis.nugget_generator import NuggetGenerator


@pytest.fixture
def nugget_generator_setup():
    """Set up common test fixtures for NuggetGenerator tests."""
    mock_settings = MagicMock()
    mock_limiter = MagicMock(spec=Limiter)
    nugget_generator = NuggetGenerator(mock_settings, mock_limiter)
    return {
        "nugget_generator": nugget_generator,
        "mock_settings": mock_settings,
        "mock_limiter": mock_limiter,
    }


@patch("src.synthesis.nugget_generator.litellm_client")
def test_generate_nuggets_happy_path(mock_litellm_client, nugget_generator_setup):
    """
    Test the happy path for generating knowledge nuggets from a conversation batch.
    """
    # Arrange
    nugget_generator_setup["nugget_generator"].limiter.as_decorator = MagicMock(
        return_value=lambda fn: fn
    )
    mock_nugget = {
        "topic": "Test",
        "timestamp": "2023-01-01T00:00:00Z",
        "topic_summary": "Summary",
        "detailed_analysis": "Analysis",
        "status": "Complete",
        "keywords": [],
        "source_message_ids": [1],
        "user_ids_involved": ["u1"],
    }
    mock_response = MagicMock()
    mock_response.choices[
        0
    ].message.content = f"```json\n[{json.dumps(mock_nugget)}]\n```"
    mock_litellm_client.complete.return_value = mock_response

    conv_batch = [{"conversation": [{"id": 1, "content": "Hello"}]}]
    prompt = "test prompt"

    # Act
    result = nugget_generator_setup["nugget_generator"].generate_nuggets_batch(
        conv_batch, prompt
    )

    # Assert
    assert len(result) == 1
    assert result[0]["topic"] == "Test"
    mock_litellm_client.complete.assert_called_once()
