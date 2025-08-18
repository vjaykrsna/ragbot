import logging
import os
from unittest.mock import MagicMock, patch

from src.core.config import AppSettings, PathSettings
from src.core.logger import setup_logging


@patch("os.makedirs")
@patch("logging.handlers.RotatingFileHandler")
@patch("logging.StreamHandler")
def test_setup_logging(mock_stream_handler, mock_file_handler, mock_makedirs):
    """Test the logging setup function."""
    # Create a mock settings object
    mock_settings = MagicMock(spec=AppSettings)
    mock_settings.paths = MagicMock(spec=PathSettings)
    mock_settings.paths.log_dir = "/fake/log/dir"
    mock_settings.console_log_level = "INFO"

    # Configure mock handlers to have a 'level' attribute
    mock_stream_handler.return_value.level = logging.INFO
    mock_file_handler.return_value.level = logging.DEBUG

    # Call the setup function
    setup_logging(mock_settings)

    # Assert that directories are created
    mock_makedirs.assert_called_once_with("/fake/log/dir", exist_ok=True)

    # Assert that handlers are created with correct parameters
    mock_stream_handler.assert_called_once()
    mock_file_handler.assert_called_once_with(
        os.path.join("/fake/log/dir", "chatbot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )

    # Assert that noisy loggers are quieted
    noisy_loggers = [
        "telethon",
        "asyncio",
        "urllib3",
        "httpx",
        "chardet",
        "litellm",
        "LiteLLM",
    ]
    for logger_name in noisy_loggers:
        assert logging.getLogger(logger_name).level == logging.WARNING
