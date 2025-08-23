import time
from functools import wraps
from typing import Callable

import structlog
from litellm import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

logger = structlog.get_logger(__name__)


def retry_with_backoff(
    func: Callable,
    max_retries: int = 5,
    initial_wait: int = 5,
    backoff_factor: int = 2,
):
    """
    A decorator to retry a function with exponential backoff.

    Args:
        func: The function to retry.
        max_retries: The maximum number of retries.
        initial_wait: The initial wait time in seconds.
        backoff_factor: The factor by which to increase the wait time on each retry.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (
                RateLimitError,
                APIConnectionError,
                ServiceUnavailableError,
                Timeout,
                APIError,
            ) as e:
                if attempt < max_retries - 1:
                    sleep_time = initial_wait * (backoff_factor**attempt)
                    logger.warning(
                        f"API Error in {func.__name__} (retriable), attempt {attempt + 1}/{max_retries}. Retrying in {sleep_time}s. Error: {e}",
                        exc_info=True,
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(
                        f"API Error in {func.__name__} failed after {max_retries} attempts. Error: {e}",
                        exc_info=True,
                    )
                    return None
        return None

    return wrapper
