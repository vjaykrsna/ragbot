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
class TelegramExtractionSettings:
    """Settings for Telegram message extraction process."""

    concurrent_groups: int = 1  # Process one group at a time to avoid rate limits
    messages_per_request: int = (
        100  # Optimized for Telegram API limits (max 100 per call)
    )
    buffer_size: int = 1000  # Reduced from 2000 to save memory
    ui_update_interval: int = 2  # Good balance of responsiveness and performance
    batch_size: int = 250  # Default batch size for message processing
    progress_update_messages: int = 100  # Update progress every N messages


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
    extraction: TelegramExtractionSettings = field(
        default_factory=TelegramExtractionSettings
    )


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
    """
    Settings for LiteLLM client.
    This entire configuration is loaded from a single JSON object.
    """

    # General settings
    drop_params: bool = True
    turn_off_message_logging: bool = True
    set_verbose: bool = False

    # Model and Router settings
    embedding_model_name: str | None = (
        None  # The actual model name, e.g., "text-embedding-ada-002"
    )
    embedding_model_proxy: str | None = (
        None  # The proxy/alias for the model, e.g., "azure-embedding-model"
    )
    model_list: List[LiteLLMModelInfo] = field(default_factory=list)
    router_settings: LiteLLMRouterSettings = field(
        default_factory=LiteLLMRouterSettings
    )


@dataclass
class SynthesisSettings:
    """Settings for the knowledge synthesis process.

    These defaults are optimized for users with 20+ API keys.
    Adjust based on your specific rate limits and performance needs:

    - max_workers: Number of parallel processing threads
    - requests_per_minute: API rate limit (higher with more keys)
    - batch_size: Conversations per API call (larger = more efficient)
    """

    max_workers: int = 4  # Reduced from 6
    requests_per_minute: int = 180  # Back to original
    batch_size: int = 8  # Back to original
    page_size: int = 10000  # Page size for database pagination


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
    collection_name: str = "telegram_knowledge_base"


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
        extraction=TelegramExtractionSettings(
            concurrent_groups=max(
                1, min(5, int(os.getenv("TELEGRAM_CONCURRENT_GROUPS", "1")))
            ),  # Validate range 1-5
            messages_per_request=int(os.getenv("TELEGRAM_MESSAGES_PER_REQUEST", "200")),
            buffer_size=int(os.getenv("TELEGRAM_BUFFER_SIZE", "1000")),
            ui_update_interval=int(os.getenv("TELEGRAM_UI_UPDATE_INTERVAL", "3")),
            batch_size=int(os.getenv("TELEGRAM_BATCH_SIZE", "250")),
            progress_update_messages=int(
                os.getenv("TELEGRAM_PROGRESS_UPDATE_MESSAGES", "100")
            ),
        ),
    )

    # --- Path Settings ---
    path_settings = PathSettings()

    # --- LiteLLM Settings ---
    litellm_config_json = os.getenv("LITELLM_CONFIG_JSON")
    if not litellm_config_json:
        raise RuntimeError("Environment variable 'LITELLM_CONFIG_JSON' must be set.")

    litellm_config_data = json.loads(litellm_config_json)

    # Build the model list
    model_list_data = litellm_config_data.get("model_list", [])
    model_list = [
        LiteLLMModelInfo(
            model_name=m["model_name"],
            litellm_params=LiteLLMModelParams(**m["litellm_params"]),
        )
        for m in model_list_data
    ]

    # Build the cache settings
    router_settings_data = litellm_config_data.get("router_settings", {})
    cache_kwargs_data = router_settings_data.get("cache_kwargs", {})
    cache_kwargs = LiteLLMCacheSettings(**cache_kwargs_data)

    # Build the router settings
    router_settings = LiteLLMRouterSettings(
        routing_strategy=router_settings_data.get(
            "routing_strategy", "usage-based-routing-v2"
        ),
        cache_responses=router_settings_data.get("cache_responses", True),
        cache_kwargs=cache_kwargs,
    )

    # Build the main LiteLLM settings
    litellm_settings_data = litellm_config_data.get("litellm_settings", {})
    litellm_settings = LiteLLMSettings(
        drop_params=litellm_settings_data.get("drop_params", True),
        turn_off_message_logging=litellm_settings_data.get(
            "turn_off_message_logging", True
        ),
        set_verbose=litellm_settings_data.get("set_verbose", False),
        model_list=model_list,
        router_settings=router_settings,
    )

    # --- Find and set the embedding model from the model list ---
    embedding_model_info = next(
        (m for m in model_list if "embedding" in m.litellm_params.model.lower()),
        None,
    )
    if embedding_model_info:
        litellm_settings.embedding_model_name = (
            embedding_model_info.litellm_params.model
        )
        litellm_settings.embedding_model_proxy = embedding_model_info.model_name

    # --- Synthesis Settings ---
    # Optimized defaults leveraging 20 API keys for higher throughput
    synthesis_settings = SynthesisSettings(
        requests_per_minute=int(
            os.getenv("REQUESTS_PER_MINUTE", "180")
        ),  # Back to original
        batch_size=int(os.getenv("BATCH_SIZE", "8")),  # Back to original
        max_workers=int(os.getenv("MAX_WORKERS", "4")),  # Reduced
    )

    # --- RAG Settings ---
    status_weights_str = os.getenv(
        "STATUS_WEIGHTS",
        '{"FACT": 1.5, "COMMUNITY_OPINION": 1.0, "SPECULATION": 0.5, "DEFAULT": 0.1}',
    )
    rag_settings = RAGSettings(
        collection_name=os.getenv("COLLECTION_NAME", "telegram_knowledge_base"),
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

    # --- Validate Configuration ---
    _validate_configuration(
        telegram_settings, litellm_settings, synthesis_settings, rag_settings
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


def _validate_configuration(
    telegram: TelegramSettings,
    litellm: LiteLLMSettings,
    synthesis: SynthesisSettings,
    rag: RAGSettings,
) -> None:
    """Validate configuration values and provide helpful warnings."""

    # Count API keys from model list
    synthesis_keys = sum(
        1
        for m in litellm.model_list
        if "synthesis" in m.model_name
        and m.litellm_params.api_key.startswith("os.environ/GEMINI_API_KEY_")
    )
    # Count embedding keys (for future use if needed)
    sum(
        1
        for m in litellm.model_list
        if "embedding" in m.model_name
        and m.litellm_params.api_key.startswith("os.environ/GEMINI_API_KEY_")
    )

    # Validate synthesis settings based on available API keys
    if synthesis.max_workers > synthesis_keys:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"max_workers ({synthesis.max_workers}) exceeds synthesis API keys ({synthesis_keys}). "
            f"Consider reducing max_workers or adding more API keys."
        )

    # Validate rate limits
    if synthesis.requests_per_minute > (
        synthesis_keys * 60
    ):  # Conservative estimate per key
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"requests_per_minute ({synthesis.requests_per_minute}) seems high for {synthesis_keys} API keys. "
            f"Consider reducing to {synthesis_keys * 60} or add more API keys."
        )

    # Validate batch size
    if synthesis.batch_size < 1 or synthesis.batch_size > 20:
        raise ValueError(
            f"batch_size must be between 1 and 20, got {synthesis.batch_size}"
        )

    # Validate RAG weights
    total_weight = (
        rag.semantic_score_weight + rag.recency_score_weight + rag.status_score_weight
    )
    if not abs(total_weight - 1.0) < 0.001:  # Allow small floating point errors
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"RAG weights should sum to 1.0, got {total_weight}. Consider normalizing."
        )

    # Validate model list
    if not litellm.model_list:
        raise ValueError("No models configured in LITELLM_CONFIG_JSON")

    synthesis_models = [m for m in litellm.model_list if "synthesis" in m.model_name]
    embedding_models = [m for m in litellm.model_list if "embedding" in m.model_name]

    if not synthesis_models:
        raise ValueError("No synthesis models configured")
    if not embedding_models:
        raise ValueError("No embedding models configured")

    # Validate Telegram extraction settings
    if (
        telegram.extraction.concurrent_groups < 1
        or telegram.extraction.concurrent_groups > 5
    ):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_CONCURRENT_GROUPS ({telegram.extraction.concurrent_groups}) should be between 1 and 5. "
            f"Values outside this range may cause performance issues or rate limiting."
        )

    if (
        telegram.extraction.messages_per_request < 50
        or telegram.extraction.messages_per_request > 1000
    ):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_MESSAGES_PER_REQUEST ({telegram.extraction.messages_per_request}) should be between 50 and 1000. "
            f"Values outside this range may cause performance issues or rate limiting."
        )

    if telegram.extraction.buffer_size < 100 or telegram.extraction.buffer_size > 5000:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_BUFFER_SIZE ({telegram.extraction.buffer_size}) should be between 100 and 5000. "
            f"Values outside this range may cause performance issues or memory problems."
        )

    if (
        telegram.extraction.ui_update_interval < 1
        or telegram.extraction.ui_update_interval > 5
    ):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_UI_UPDATE_INTERVAL ({telegram.extraction.ui_update_interval}) should be between 1 and 5 seconds. "
            f"Values outside this range may cause UI issues or unnecessary I/O overhead."
        )

    if telegram.extraction.batch_size < 50 or telegram.extraction.batch_size > 1000:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_BATCH_SIZE ({telegram.extraction.batch_size}) should be between 50 and 1000. "
            f"Values outside this range may cause performance issues or memory problems."
        )

    if (
        telegram.extraction.progress_update_messages < 10
        or telegram.extraction.progress_update_messages > 1000
    ):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_PROGRESS_UPDATE_MESSAGES ({telegram.extraction.progress_update_messages}) should be between 10 and 1000. "
            f"Values outside this range may cause UI issues or unnecessary I/O overhead."
        )
