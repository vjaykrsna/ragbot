"""
Simple, standardized error handling for the application.

This module provides basic error handling utilities that can be used throughout
the application to ensure consistent error logging and handling.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Tuple, Type

import structlog

logger = structlog.get_logger(__name__)

# Define common retryable exceptions
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
)


def log_exception(func: Callable) -> Callable:
    """
    Decorator to log exceptions with full traceback information.

    This decorator ensures that any exception raised by the wrapped function
    is properly logged with traceback information before being re-raised.
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Exception in {func.__name__}: {str(e)}",
                exc_info=True,
                func_name=func.__name__,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Exception in {func.__name__}: {str(e)}",
                exc_info=True,
                func_name=func.__name__,
            )
            raise

    # Return the appropriate wrapper based on whether the function is async
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
):
    """
    Decorator to retry a function on failure.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier applied to delay after each retry
        retryable_exceptions: Tuple of exceptions that should trigger retries
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retryable error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}",
                            exc_info=True,
                        )
                        raise
                except Exception as e:
                    # Non-retryable exception
                    logger.error(
                        f"Non-retryable error in {func.__name__}: {e}", exc_info=True
                    )
                    raise

            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown error in retry mechanism")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retryable error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}",
                            exc_info=True,
                        )
                        raise
                except Exception as e:
                    # Non-retryable exception
                    logger.error(
                        f"Non-retryable error in {func.__name__}: {e}", exc_info=True
                    )
                    raise

            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown error in retry mechanism")

        # Return the appropriate wrapper based on whether the function is async
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def safe_call(func: Callable, *args, **kwargs) -> Any:
    """
    Safely call a function and return (success, result_or_exception).

    This function wraps a call and returns a tuple indicating success/failure
    and the result or exception.

    Returns:
        tuple: (success: bool, result: Any)
            - If successful: (True, result)
            - If failed: (False, exception)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        logger.error(
            f"Safe call failed for {func.__name__}: {str(e)}",
            exc_info=True,
            func_name=func.__name__,
        )
        return False, e
