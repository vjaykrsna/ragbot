import logging
import logging.handlers
import os
import sys

import structlog

from src.core.config import AppSettings


def setup_logging(settings: AppSettings) -> None:
    """
    Configures structured logging using structlog.
    """
    log_dir = settings.paths.log_dir
    os.makedirs(log_dir, exist_ok=True)

    # Get console log level from settings
    console_level_name = settings.console_log_level.upper()
    console_level = getattr(logging, console_level_name, logging.INFO)

    # Shared processors for structlog
    shared_processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Configure logging
    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )
    console_handler.setFormatter(console_formatter)

    # Rotating file handler (JSON format)
    log_file_path = os.path.join(log_dir, "chatbot.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )
    file_handler.setFormatter(file_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Quiet noisy third-party loggers
    noisy_loggers = [
        "asyncio",
        "urllib3",
        "httpx",
        "chardet",
        "litellm",
        "LiteLLM",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    structlog.get_logger(__name__).info("Logging configured successfully.")
