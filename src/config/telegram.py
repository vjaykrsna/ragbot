from typing import List
from pydantic import BaseModel, Field

class TelegramSettings(BaseModel):
    """Settings for Telegram client and bot."""
    bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    group_ids: List[int] = Field(default_factory=list, env="GROUP_IDS")
    session_name: str = Field("ragbot_session", env="SESSION_NAME")
    phone: str | None = Field(None, env="TELEGRAM_PHONE")
    password: str | None = Field(None, env="TELEGRAM_PASSWORD")