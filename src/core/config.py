"""
Centralized configuration management.
"""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List

from dotenv import load_dotenv


@dataclass
class TelegramSettings:
    """Settings for Telegram client."""

    api_id: int
    api_hash: str
    phone: str
    password: str
    bot_token: str
    session_name: str = "telegram_session"
    group_ids: List[int] = field(default_factory=list)


@dataclass
class PathSettings:
    """
    Path and filename settings.
    All paths are absolute and constructed from a few base directories.
    """

    # Base Directories
    root_dir: str = field(init=False)
    data_dir: str = field(init=False)
    log_dir: str = field(init=False)
    docs_dir: str = field(init=False)

    # Computed Paths
    raw_data_dir: str = field(init=False)
    processed_data_dir: str = field(init=False)
    db_dir: str = field(init=False)
    processed_conversations_file: str = field(init=False)
    user_map_file: str = field(init=False)
    synthesis_progress_file: str = field(init=False)
    tracking_file: str = field(init=False)
    failed_batches_file: str = field(init=False)
    processed_hashes_file: str = field(init=False)
    prompt_file: str = field(init=False)

    def __post_init__(self):
        self.root_dir = get_project_root()
        self.data_dir = os.path.join(self.root_dir, "data")
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.docs_dir = os.path.join(self.root_dir, "docs")
        self.raw_data_dir = os.path.join(self.data_dir, "raw")
        self.processed_data_dir = os.path.join(self.data_dir, "processed")
        self.db_dir = os.path.join(self.data_dir, "knowledge_base")
        self.processed_conversations_file = os.path.join(
            self.processed_data_dir, "processed_conversations.json"
        )
        self.user_map_file = os.path.join(self.processed_data_dir, "user_map.json")
        self.synthesis_progress_file = os.path.join(
            self.processed_data_dir, "synthesis_progress.json"
        )
        self.tracking_file = os.path.join(self.data_dir, "last_msg_ids.json")
        self.failed_batches_file = os.path.join(self.data_dir, "failed_batches.jsonl")
        self.processed_hashes_file = os.path.join(
            self.processed_data_dir, "processed_hashes.json"
        )
        self.prompt_file = os.path.join(self.docs_dir, "knowledge_synthesis_prompt.md")


@dataclass
class LiteLLMCacheSettings:
    """Settings for LiteLLM response caching."""

    type: str = "redis"
    host: str | None = None
    port: int | None = None
    password: str | None = None
    ttl: int = 3600


@dataclass
class LiteLLMRouterSettings:
    """Settings for LiteLLM router."""

    routing_strategy: str = "usage-based-routing-v2"
    cache_responses: bool = True
    cache_kwargs: LiteLLMCacheSettings = field(default_factory=LiteLLMCacheSettings)


@dataclass
class LiteLLMModelParams:
    """Parameters for a specific LiteLLM model."""

    model: str
    api_key: str
    rpm: int | None = None
    tpm: int | None = None
    stream: bool = False
    output_dimensionality: int | None = None


@dataclass
class LiteLLMModelInfo:
    """Container for a model and its parameters."""

    model_name: str
    litellm_params: LiteLLMModelParams


@dataclass
class LiteLLMSettings:
    """Settings for LiteLLM client."""

    # General settings
    drop_params: bool = True
    turn_off_message_logging: bool = True
    set_verbose: bool = False

    # Model and Router settings
    model_list: List[LiteLLMModelInfo] = field(default_factory=list)
    router_settings: LiteLLMRouterSettings = field(
        default_factory=LiteLLMRouterSettings
    )

    # Legacy simple settings (can be deprecated later)
    synthesis_model_name: str = "gemini-pro"
    embedding_model_name: str = "text-embedding-ada-002"
    embedding_model_proxy: str | None = None


@dataclass
class SynthesisSettings:
    """Settings for the knowledge synthesis process."""

    max_workers: int = 5
    requests_per_minute: int = 90
    batch_size: int = 2


@dataclass
class RAGSettings:
    """Settings for the RAG pipeline."""

    semantic_score_weight: float = 0.5
    recency_score_weight: float = 0.3
    status_score_weight: float = 0.2
    status_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "FACT": 1.5,
            "COMMUNITY_OPINION": 1.0,
            "SPECULATION": 0.5,
            "DEFAULT": 0.1,
        }
    )
    collection_name: str = "telegram_knowledge_base_v2"


@dataclass
class ConversationSettings:
    """Settings for conversation grouping."""

    time_threshold_seconds: int = 300
    session_window_seconds: int = 3600


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


@lru_cache(maxsize=1)
def get_project_root() -> str:
    """Returns the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@lru_cache(maxsize=None)
def get_settings() -> AppSettings:
    """
    Loads the application settings from environment variables.
    Uses a cache to ensure settings are loaded only once.
    """
    load_dotenv()

    # --- Telegram Settings ---
    api_id = os.getenv("API_ID")
    if not api_id:
        raise RuntimeError("Environment variable 'API_ID' must be set.")
    api_hash = os.getenv("API_HASH")
    if not api_hash:
        raise RuntimeError("Environment variable 'API_HASH' must be set.")
    phone = os.getenv("PHONE")
    if not phone:
        raise RuntimeError("Environment variable 'PHONE' must be set.")
    password = os.getenv("PASSWORD")
    if not password:
        raise RuntimeError("Environment variable 'PASSWORD' must be set.")
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("Environment variable 'BOT_TOKEN' must be set.")

    group_ids_str = os.getenv("GROUP_IDS", "")
    telegram_settings = TelegramSettings(
        api_id=int(api_id),
        api_hash=api_hash,
        phone=phone,
        password=password,
        bot_token=bot_token,
        session_name=os.getenv("SESSION_NAME", "telegram_session"),
        group_ids=[int(gid.strip()) for gid in group_ids_str.split(",") if gid.strip()],
    )

    # --- Path Settings ---
    path_settings = PathSettings()

    # --- LiteLLM Settings ---
    # Parse complex model list from JSON string
    model_list_json = os.getenv("LITELLM_MODEL_LIST_JSON", "[]")
    model_list_data = json.loads(model_list_json)
    model_list = [
        LiteLLMModelInfo(
            model_name=m["model_name"],
            litellm_params=LiteLLMModelParams(**m["litellm_params"]),
        )
        for m in model_list_data
    ]

    # Cache settings
    cache_kwargs = LiteLLMCacheSettings(
        type=os.getenv("LITELLM_CACHE_TYPE", "redis"),
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT", "6380")),
        password=os.getenv("REDIS_PASSWORD"),
        ttl=int(os.getenv("LITELLM_CACHE_TTL", "3600")),
    )

    # Router settings
    router_settings = LiteLLMRouterSettings(
        routing_strategy=os.getenv(
            "LITELLM_ROUTING_STRATEGY", "usage-based-routing-v2"
        ),
        cache_responses=os.getenv("LITELLM_CACHE_RESPONSES", "true").lower() == "true",
        cache_kwargs=cache_kwargs,
    )

    litellm_settings = LiteLLMSettings(
        drop_params=os.getenv("LITELLM_DROP_PARAMS", "true").lower() == "true",
        turn_off_message_logging=os.getenv(
            "LITELLM_TURN_OFF_MESSAGE_LOGGING", "true"
        ).lower()
        == "true",
        set_verbose=os.getenv("LITELLM_SET_VERBOSE", "false").lower() == "true",
        model_list=model_list,
        router_settings=router_settings,
        synthesis_model_name=os.getenv("SYNTHESIS_MODEL_NAME", "gemini-pro"),
        embedding_model_name=os.getenv(
            "EMBEDDING_MODEL_NAME", "text-embedding-ada-002"
        ),
        embedding_model_proxy=os.getenv("EMBEDDING_MODEL_PROXY"),
    )

    # --- Synthesis Settings ---
    synthesis_settings = SynthesisSettings(
        requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE", "60")),
        batch_size=int(os.getenv("BATCH_SIZE", "10")),
        max_workers=int(os.getenv("MAX_WORKERS", "4")),
    )

    # --- RAG Settings ---
    status_weights_str = os.getenv(
        "STATUS_WEIGHTS",
        '{"FACT": 1.5, "COMMUNITY_OPINION": 1.0, "SPECULATION": 0.5, "DEFAULT": 0.1}',
    )
    rag_settings = RAGSettings(
        collection_name=os.getenv("COLLECTION_NAME", "telegram_knowledge_base_v2"),
        status_weights=json.loads(status_weights_str),
        semantic_score_weight=float(os.getenv("SEMANTIC_SCORE_WEIGHT", "0.5")),
        recency_score_weight=float(os.getenv("RECENCY_SCORE_WEIGHT", "0.3")),
        status_score_weight=float(os.getenv("STATUS_SCORE_WEIGHT", "0.2")),
    )

    # --- Conversation Settings ---
    conversation_settings = ConversationSettings(
        session_window_seconds=int(os.getenv("SESSION_WINDOW_SECONDS", "3600")),
        time_threshold_seconds=int(os.getenv("TIME_THRESHOLD_SECONDS", "300")),
    )

    # --- App Settings ---
    return AppSettings(
        telegram=telegram_settings,
        paths=path_settings,
        litellm=litellm_settings,
        synthesis=synthesis_settings,
        rag=rag_settings,
        conversation=conversation_settings,
        console_log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
