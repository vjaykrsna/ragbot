"""
Centralized, validated settings for the application.

This module uses Pydantic's BaseSettings to load configuration from environment
variables and .env files. It provides a hierarchical structure for settings,
making them easier to manage and use throughout the application.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .conversation import ConversationSettings
from .litellm import LiteLLMSettings
from .paths import PathSettings
from .rag import RAGSettings
from .synthesis import SynthesisSettings
from .telegram import TelegramSettings


@dataclass
class AppSettings:
    """Root settings object for the application."""

    telegram: TelegramSettings
    litellm: LiteLLMSettings
    paths: PathSettings
    synthesis: SynthesisSettings
    rag: RAGSettings
    conversation: ConversationSettings
    console_log_level: str


def load_settings() -> AppSettings:
    """Loads and returns the application settings."""
    load_dotenv()

    group_ids_str = os.getenv("TELEGRAM__GROUP_IDS", "")
    if group_ids_str:
        group_ids = [int(gid.strip()) for gid in group_ids_str.split(",")]
    else:
        group_ids = []

    return AppSettings(
        telegram=TelegramSettings(
            bot_token=os.getenv("TELEGRAM__BOT_TOKEN"),
            group_ids=group_ids,
            session_name=os.getenv("TELEGRAM__SESSION_NAME", "ragbot_session"),
            phone=os.getenv("TELEGRAM__PHONE"),
            password=os.getenv("TELEGRAM__PASSWORD"),
        ),
        litellm=LiteLLMSettings(),
        paths=PathSettings(),
        synthesis=SynthesisSettings(),
        rag=RAGSettings(),
        conversation=ConversationSettings(),
        console_log_level=os.getenv("CHATBOT_CONSOLE_LEVEL", "INFO"),
    )
