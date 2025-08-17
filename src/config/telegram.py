from dataclasses import dataclass
from typing import List


@dataclass
class TelegramSettings:
    """Settings for Telegram client and bot."""

    bot_token: str
    group_ids: List[int]
    session_name: str
    phone: str | None
    password: str | None
