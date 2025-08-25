"""
Tests for the simple error handler module.
"""

from unittest.mock import patch

import pytest

from src.core.simple_error_handler import log_exception, retry_on_failure, safe_call


def test_log_exception_sync():
    """Test the log_exception decorator with a synchronous function."""

    @log_exception
    def failing_function():
        raise ValueError("Test error")

    with patch("src.core.simple_error_handler.logger.error") as mock_error:
        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Verify that the error was logged
        mock_error.assert_called_once()
        call_args = mock_error.call_args
        # Check that exc_info=True was passed to the logger
        assert call_args[1]["exc_info"] is True


@pytest.mark.asyncio
async def test_log_exception_async():
    """Test the log_exception decorator with an asynchronous function."""

    @log_exception
    async def failing_async_function():
        raise ValueError("Test async error")

    with patch("src.core.simple_error_handler.logger.error") as mock_error:
        with pytest.raises(ValueError, match="Test async error"):
            await failing_async_function()

        # Verify that the error was logged
        mock_error.assert_called_once()
        call_args = mock_error.call_args
        # Check that exc_info=True was passed to the logger
        assert call_args[1]["exc_info"] is True


def test_retry_on_failure_sync_success():
    """Test the retry_on_failure decorator with a function that eventually succeeds."""
    call_count = 0

    @retry_on_failure(max_retries=2)
    def sometimes_failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Temporary error")
        return "success"

    with patch("src.core.simple_error_handler.logger.warning") as mock_warning:
        result = sometimes_failing_function()
        assert result == "success"
        assert call_count == 2
        # Verify that one warning was logged for the retry
        mock_warning.assert_called_once()


def test_retry_on_failure_sync_failure():
    """Test the retry_on_failure decorator with a function that always fails."""
    call_count = 0

    @retry_on_failure(max_retries=2)
    def always_failing_function():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Permanent error")

    with patch("src.core.simple_error_handler.logger.error") as mock_error:
        with pytest.raises(ConnectionError, match="Permanent error"):
            always_failing_function()

        assert call_count == 3  # Initial call + 2 retries
        # Verify that an error was logged
        mock_error.assert_called_once()


@pytest.mark.asyncio
async def test_retry_on_failure_async_success():
    """Test the retry_on_failure decorator with an async function that eventually succeeds."""
    call_count = 0

    @retry_on_failure(max_retries=2)
    async def sometimes_failing_async_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Temporary error")
        return "success"

    with patch("src.core.simple_error_handler.logger.warning") as mock_warning:
        result = await sometimes_failing_async_function()
        assert result == "success"
        assert call_count == 2
        # Verify that one warning was logged for the retry
        mock_warning.assert_called_once()


def test_safe_call_success():
    """Test safe_call with a function that succeeds."""

    def successful_function():
        return "result"

    success, result = safe_call(successful_function)
    assert success is True
    assert result == "result"


def test_safe_call_failure():
    """Test safe_call with a function that fails."""

    def failing_function():
        raise ValueError("Test error")

    with patch("src.core.simple_error_handler.logger.error") as mock_error:
        success, result = safe_call(failing_function)
        assert success is False
        assert isinstance(result, ValueError)
        assert str(result) == "Test error"
        # Verify that the error was logged
        mock_error.assert_called_once()
