"""
Centralized, validated settings for the application.

This module uses Pydantic's BaseSettings to load configuration from environment
variables and .env files. It provides a hierarchical structure for settings,
making them easier to manage and use throughout the application.
"""

import os
from typing import Dict, List

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .litellm import LiteLLMSettings
from .telegram import TelegramSettings


from .paths import PathSettings


from .synthesis import SynthesisSettings


from .rag import RAGSettings


from .conversation import ConversationSettings


class AppSettings(BaseSettings):
    """Root settings object for the application."""
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    litellm: LiteLLMSettings = Field(default_factory=LiteLLMSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    synthesis: SynthesisSettings = Field(default_factory=SynthesisSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    console_log_level: str = Field("INFO", env="CHATBOT_CONSOLE_LEVEL")


def load_settings() -> AppSettings:
    """Loads and returns the application settings."""
    return AppSettings()
