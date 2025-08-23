"""
Centralized error handling and recovery mechanisms.

This module provides:
1. Retry mechanisms with exponential backoff
2. Checkpoint-based recovery
3. Alerting for critical failures
4. Standardized error handling patterns
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, Optional, Set, Tuple, Type

import structlog
from litellm import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

logger = structlog.get_logger(__name__)

# Define retryable exceptions
RETRYABLE_EXCEPTIONS = (
    RateLimitError,
    APIConnectionError,
    ServiceUnavailableError,
    Timeout,
    APIError,
    ConnectionError,
    TimeoutError,
)

# Define critical exceptions that should trigger alerts
CRITICAL_EXCEPTIONS = (
    ValueError,
    TypeError,
    AttributeError,
    ImportError,
    RuntimeError,
)


class CheckpointManager:
    """
    Manages checkpoint-based recovery for long-running processes.
    """

    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.last_checkpoint = {}

    def save_checkpoint(self, **kwargs) -> None:
        """
        Save a checkpoint with the provided state information.

        Args:
            **kwargs: State information to save
        """
        self.last_checkpoint = kwargs
        try:
            import json
            import os

            os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
            with open(self.checkpoint_file, "w") as f:
                json.dump(kwargs, f)
            logger.debug(f"Checkpoint saved to {self.checkpoint_file}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self) -> Dict[str, Any]:
        """
        Load the last saved checkpoint.

        Returns:
            Dictionary containing checkpoint data or empty dict if no checkpoint exists
        """
        try:
            import json

            with open(self.checkpoint_file, "r") as f:
                data = json.load(f)
            self.last_checkpoint = data
            logger.debug(f"Checkpoint loaded from {self.checkpoint_file}")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"No checkpoint found or invalid checkpoint: {e}")
            return {}

    def clear_checkpoint(self) -> None:
        """Clear the current checkpoint."""
        self.last_checkpoint = {}
        try:
            import os

            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            logger.debug("Checkpoint cleared")
        except Exception as e:
            logger.warning(f"Failed to clear checkpoint: {e}")


class AlertManager:
    """
    Manages alerting for critical failures.
    """

    def __init__(self):
        self.alerted_exceptions: Set[str] = set()

    def send_alert(self, message: str, exception: Optional[Exception] = None) -> None:
        """
        Send an alert for a critical failure.

        Args:
            message: Alert message
            exception: Exception that triggered the alert (optional)
        """
        exception_str = str(exception) if exception else "No exception details"
        alert_key = f"{message}:{exception_str}"

        # Avoid sending duplicate alerts for the same issue
        if alert_key in self.alerted_exceptions:
            return

        self.alerted_exceptions.add(alert_key)

        # Log the critical error
        logger.critical(f"CRITICAL ALERT: {message}", exception=exception_str)

        # In a real implementation, this would send alerts via:
        # - Email
        # - Slack/Teams
        # - SMS
        # - Monitoring systems (Prometheus, etc.)
        # For now, we just log it


def retry_with_backoff(
    max_retries: int = 5,
    initial_wait: float = 1.0,
    backoff_factor: float = 2.0,
    max_wait: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        backoff_factor: Factor to multiply wait time by on each retry
        max_wait: Maximum wait time between retries
        retryable_exceptions: Tuple of exceptions that should trigger retries
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = min(
                            initial_wait * (backoff_factor**attempt), max_wait
                        )
                        logger.warning(
                            f"Retryable error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {wait_time:.1f}s. Error: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown error in retry mechanism")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = min(
                            initial_wait * (backoff_factor**attempt), max_wait
                        )
                        logger.warning(
                            f"Retryable error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {wait_time:.1f}s. Error: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown error in retry mechanism")

        # Return the appropriate wrapper based on whether the function is async
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def handle_critical_errors(alert_manager: Optional[AlertManager] = None):
    """
    Decorator to handle critical errors and send alerts.

    Args:
        alert_manager: AlertManager instance to use for sending alerts
    """
    if alert_manager is None:
        alert_manager = AlertManager()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CRITICAL_EXCEPTIONS as e:
                alert_manager.send_alert(
                    f"Critical error in {func.__name__}", exception=e
                )
                raise
            except Exception:
                # Re-raise non-critical exceptions
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CRITICAL_EXCEPTIONS as e:
                alert_manager.send_alert(
                    f"Critical error in {func.__name__}", exception=e
                )
                raise
            except Exception:
                # Re-raise non-critical exceptions
                raise

        # Return the appropriate wrapper based on whether the function is async
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Default instances
default_alert_manager = AlertManager()
default_checkpoint_manager = None  # Will be initialized with a file path when needed
