import json
import unittest
from unittest.mock import MagicMock, patch

from pyrate_limiter import Limiter

from src.synthesis.nugget_generator import NuggetGenerator


class TestNuggetGenerator(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_limiter = MagicMock(spec=Limiter)
        self.nugget_generator = NuggetGenerator(
            self.mock_settings, self.mock_limiter
        )

    @patch("src.synthesis.nugget_generator.litellm_client")
    def test_generate_nuggets_happy_path(self, mock_litellm_client):
        """
        Test the happy path for generating knowledge nuggets from a conversation batch.
        """
        # Arrange
        self.nugget_generator.limiter.as_decorator = MagicMock(
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
        result = self.nugget_generator.generate_nuggets_batch(conv_batch, prompt)

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topic"], "Test")
        mock_litellm_client.complete.assert_called_once()
