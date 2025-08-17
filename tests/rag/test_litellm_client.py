import unittest
from unittest.mock import MagicMock, patch

from src.core.config import LiteLLMModelInfo, LiteLLMModelParams, LiteLLMSettings
from src.rag import litellm_client


class TestLiteLLMClient(unittest.TestCase):
    def setUp(self):
        """Reset the singleton router before each test."""
        litellm_client._router = None

    @patch("src.rag.litellm_client.get_settings")
    @patch("src.rag.litellm_client.litellm.Router")
    def test_get_router_initialization_and_singleton(
        self, mock_router_class, mock_get_settings
    ):
        """
        Test that _get_router initializes the router correctly on the first call
        and returns the same instance on subsequent calls.
        """
        # --- Setup Mock Settings ---
        mock_model_info = LiteLLMModelInfo(
            model_name="test-model",
            litellm_params=LiteLLMModelParams(
                model="some/test-model", api_key="test-key"
            ),
        )
        mock_litellm_settings = LiteLLMSettings(model_list=[mock_model_info])
        mock_settings = MagicMock()
        mock_settings.litellm = mock_litellm_settings
        mock_get_settings.return_value = mock_settings

        # --- First Call: Initialization ---
        router_instance1 = litellm_client._get_router()

        # Assertions for initialization
        mock_get_settings.assert_called_once()
        mock_router_class.assert_called_once()

        # Check that the router was called with the correct model list
        call_args, call_kwargs = mock_router_class.call_args
        self.assertEqual(len(call_kwargs["model_list"]), 1)
        self.assertEqual(call_kwargs["model_list"][0]["model_name"], "test-model")

        # --- Second Call: Singleton Check ---
        router_instance2 = litellm_client._get_router()

        # Assertions for singleton behavior
        mock_get_settings.assert_called_once()  # Should not be called again
        mock_router_class.assert_called_once()  # Should not be called again
        self.assertIs(router_instance1, router_instance2)
        self.assertIs(router_instance1, mock_router_class.return_value)

    @patch("src.rag.litellm_client._get_router")
    def test_complete_success(self, mock_get_router):
        """Test the complete function on a successful API call."""
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router
        prompt = [{"role": "user", "content": "Hello"}]

        litellm_client.complete(prompt)

        mock_router.completion.assert_called_once_with(
            model="gemini-synthesis-model", messages=prompt
        )

    @patch("time.sleep", return_value=None)
    @patch("src.rag.litellm_client._get_router")
    def test_complete_retry_and_fail(self, mock_get_router, mock_sleep):
        """Test that complete retries on failure and returns None after max retries."""
        mock_router = MagicMock()
        mock_router.completion.side_effect = Exception("API Error")
        mock_get_router.return_value = mock_router
        prompt = [{"role": "user", "content": "Hello"}]

        result = litellm_client.complete(prompt, max_retries=3)

        self.assertIsNone(result)
        self.assertEqual(mock_router.completion.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 3)

    @patch("src.rag.litellm_client._get_router")
    def test_embed_success(self, mock_get_router):
        """Test the embed function on a successful API call."""
        mock_router = MagicMock()
        mock_response = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }
        mock_router.embedding.return_value = mock_response
        mock_get_router.return_value = mock_router
        texts = ["text 1", "text 2"]

        result = litellm_client.embed(texts)

        mock_router.embedding.assert_called_once_with(
            model="gemini-embedding-model", input=texts
        )
        self.assertEqual(result, [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    @patch("time.sleep", return_value=None)
    @patch("src.rag.litellm_client._get_router")
    def test_embed_retry_and_succeed(self, mock_get_router, mock_sleep):
        """Test that embed retries on failure and succeeds on the second attempt."""
        mock_router = MagicMock()
        mock_response = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_router.embedding.side_effect = [
            Exception("API Error"),
            mock_response,
        ]
        mock_get_router.return_value = mock_router
        texts = ["text 1"]

        result = litellm_client.embed(texts, max_retries=2)

        self.assertEqual(result, [[0.1, 0.2, 0.3]])
        self.assertEqual(mock_router.embedding.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)
