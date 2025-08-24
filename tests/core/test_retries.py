import unittest
from unittest.mock import MagicMock, patch

from litellm import RateLimitError

from src.core.error_handler import retry_with_backoff


class TestRetryDecorator(unittest.TestCase):
    @patch("time.sleep", return_value=None)  # Mock time.sleep to speed up the test
    def test_retry_on_rate_limit_error(self, mock_sleep):
        """
        Tests that the decorator retries the function call on RateLimitError.
        """
        # Create a mock function that will be decorated
        mock_func = MagicMock()
        mock_func.__name__ = "mock_func"
        # The first call will raise RateLimitError, the second will succeed
        mock_func.side_effect = [
            RateLimitError(
                "API rate limit exceeded", llm_provider="test", model="test"
            ),
            "Success",
        ]

        # Decorate the mock function
        # Use a small initial_wait to speed up the test
        decorated_func = retry_with_backoff(initial_wait=0.1)(mock_func)

        # Call the decorated function
        result = decorated_func()

        # Assertions
        # 1. The function should have been called twice (1 failure, 1 success)
        self.assertEqual(mock_func.call_count, 2)

        # 2. The sleep function should have been called once between retries
        mock_sleep.assert_called_once()

        # 3. The final result should be the successful one
        self.assertEqual(result, "Success")

    @patch("time.sleep", return_value=None)
    def test_exceeds_max_retries(self, mock_sleep):
        """
        Tests that the function gives up after exceeding max_retries.
        """
        mock_func = MagicMock()
        mock_func.__name__ = "mock_func"
        mock_func.side_effect = RateLimitError(
            "API rate limit exceeded", llm_provider="test", model="test"
        )

        # Set max_retries to 2 for this test
        decorated_func = retry_with_backoff(max_retries=2, initial_wait=0.1)(mock_func)

        with self.assertRaises(RateLimitError):
            decorated_func()

        # Assertions
        # 1. The function should have been called 3 times (1 initial + 2 retries)
        self.assertEqual(mock_func.call_count, 3)

        # 2. No result is expected as it failed all retries


if __name__ == "__main__":
    unittest.main()
