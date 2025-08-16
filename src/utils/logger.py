import logging
import logging.handlers
import os
import sys
from typing import NoReturn

LOG_DIR = "logs"
MAX_LOG_SIZE_MB = 5
LOG_BACKUP_COUNT = 3


def setup_logging() -> None:
    """Set up centralized logging for the application.

    Creates a rotating file handler (DEBUG+) and a console handler (INFO+).
    This is idempotent and safe to call multiple times.
    """
    # Ensure logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)

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
