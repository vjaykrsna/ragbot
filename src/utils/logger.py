import logging
import logging.handlers
import os
import sys

LOG_DIR = "logs"
MAX_LOG_SIZE_MB = 5
LOG_BACKUP_COUNT = 3


def setup_logging() -> None:
    """
    Creates a rotating file handler (DEBUG+) and a console handler (INFO+).
    """
# Ensure logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s"
    )

# Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

# Allow overriding console level via env var for quick control
    console_level_name = os.getenv("CHATBOT_CONSOLE_LEVEL", "INFO").upper()
    console_level = getattr(logging, console_level_name, logging.INFO)

# Console handler (configurable, default INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(log_formatter)

# Quiet noisy third-party loggers on the console while preserving file logs (th...
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
        l = logging.getLogger(logger_name)
# Set higher level so debug/verbose messages don't appear on console
        l.setLevel(logging.WARNING)
# Remove any handlers third-party libs may have attached so they don't bypass t...
        for h in list(l.handlers):
            l.removeHandler(h)
        l.propagate = True

# Rotating file handler (DEBUG level)
    log_file_path = os.path.join(LOG_DIR, "chatbot.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_formatter)

# Remove existing handlers to avoid duplication when reloading
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info("Logging configured successfully.")
