import unittest
from unittest.mock import MagicMock, patch

from pyrate_limiter import Limiter

from src.synthesis.nugget_embedder import NuggetEmbedder


class TestNuggetEmbedder(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_limiter = MagicMock(spec=Limiter)
        self.nugget_embedder = NuggetEmbedder(self.mock_settings, self.mock_limiter)

    @patch("src.synthesis.nugget_embedder.litellm_client")
    def test_embed_nuggets_happy_path(self, mock_litellm_client):
        """
        Test the happy path for embedding a batch of nuggets.
        """
        # Arrange
        self.nugget_embedder.limiter.as_decorator = MagicMock(
            return_value=lambda fn: fn
        )
        nuggets = [
            {"detailed_analysis": "analysis 1"},
            {"detailed_analysis": "analysis 2"},
        ]
        mock_embeddings = [[0.1], [0.2]]
        mock_litellm_client.embed.return_value = mock_embeddings

        # Act
        result = self.nugget_embedder.embed_nuggets_batch(nuggets)

        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["embedding"], [0.1])
        self.assertEqual(result[1]["embedding"], [0.2])
        mock_litellm_client.embed.assert_called_once_with(
            ["analysis 1", "analysis 2"], max_retries=1
        )
