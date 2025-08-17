"""
Centralized configuration management.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List

from dotenv import load_dotenv


@dataclass
class TelegramSettings:
    """Settings for Telegram client."""

    api_id: int = None
    api_hash: str = None
    phone: str = None
    password: str = None
    bot_token: str = None
    session_name: str = "telegram_session"
    group_ids: List[int] = field(default_factory=list)


@dataclass
class PathSettings:
    """Settings for file paths."""

    root_dir: str
    data_dir: str = field(init=False)
    raw_data_dir: str = field(init=False)
    processed_data_dir: str = field(init=False)
    db_dir: str = field(init=False)
    tracking_file: str = field(init=False)
    log_dir: str = field(init=False)
    docs_dir: str = field(init=False)
    prompt_file: str = field(init=False)

    def __post_init__(self):
        self.data_dir = os.path.join(self.root_dir, "data")
        self.raw_data_dir = os.path.join(self.data_dir, "raw")
        self.processed_data_dir = os.path.join(self.data_dir, "processed")
        self.db_dir = os.path.join(self.data_dir, "db")
        self.tracking_file = os.path.join(self.data_dir, ".last_message_ids.json")
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.user_map_file = os.path.join(self.processed_data_dir, "user_map.json")
        self.docs_dir = os.path.join(self.root_dir, "docs")
        self.prompt_file = os.path.join(self.docs_dir, "knowledge_synthesis_prompt.md")

    processed_conversations_file: str = "conversations.json"
    synthesis_progress_file: str = ".synthesis_progress.json"
    processed_hashes_file: str = ".processed_hashes.json"


@dataclass
class LiteLLMSettings:
    """Settings for LiteLLM client."""

    embedding_model_name: str = "text-embedding-ada-002"
    embedding_model_proxy: str = None


@dataclass
class SynthesisSettings:
    """Settings for knowledge synthesis."""

    requests_per_minute: int = 60
    batch_size: int = 10
    max_workers: int = 4


@dataclass
class RAGSettings:
    """Settings for RAG pipeline."""

    collection_name: str = "telegram_knowledge_base"
    status_weights: Dict[str, float] = field(
        default_factory=lambda: {"DEFAULT": 1.0, "IMPORTANT": 1.5}
    )
    semantic_score_weight: float = 0.6
    recency_score_weight: float = 0.2
    status_score_weight: float = 0.2


@dataclass
class ConversationSettings:
    """Settings for conversation processing."""

    session_window_seconds: int = 3600
    time_threshold_seconds: int = 120


@dataclass
class AppSettings:
    """Root application settings."""

    telegram: TelegramSettings
    paths: PathSettings
    litellm: LiteLLMSettings
    synthesis: SynthesisSettings
    rag: RAGSettings
    conversation: ConversationSettings
    console_log_level: str = "INFO"


@lru_cache(maxsize=None)
def get_settings() -> AppSettings:
    """
    Loads the application settings from environment variables.
    Uses a cache to ensure settings are loaded only once.
    """
    load_dotenv()

    # --- Project Root ---
    # Assumes the script is run from the project root.
    # This is a common convention.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # --- Telegram Settings ---
    api_id_env = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    if not api_id_env or not api_hash:
        raise RuntimeError("API_ID and API_HASH must be set in the environment.")
    api_id = int(api_id_env)

    phone = os.getenv("PHONE")
    if not phone:
        raise RuntimeError("PHONE must be set in the environment.")

    password = os.getenv("PASSWORD")
    if not password:
        raise RuntimeError("PASSWORD must be set in the environment.")

    group_ids_str = os.getenv("GROUP_IDS", "")
    group_ids = [int(gid.strip()) for gid in group_ids_str.split(",") if gid.strip()]

    telegram_settings = TelegramSettings(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        password=password,
        group_ids=group_ids,
    )

    # --- Path Settings ---
    path_settings = PathSettings(root_dir=project_root)

    # --- App Settings ---
    return AppSettings(
        telegram=telegram_settings,
        paths=path_settings,
        litellm=LiteLLMSettings(),
        synthesis=SynthesisSettings(),
        rag=RAGSettings(),
        conversation=ConversationSettings(),
        console_log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
