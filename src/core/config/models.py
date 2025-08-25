"""
Configuration models for the application.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List


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
    synthesis_checkpoint_file: str = field(init=False)

    def __post_init__(self):
        from .utils import get_project_root

        self.root_dir = get_project_root()
        self.data_dir = os.path.join(self.root_dir, "data")
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.docs_dir = os.path.join(self.root_dir, "docs")
        self.raw_data_dir = os.path.join(self.data_dir, "raw")
        self.processed_data_dir = os.path.join(self.data_dir, "processed")
        # Allow overriding db_dir with environment variable
        self.db_dir = os.getenv("DB_DIR", os.path.join(self.data_dir, "knowledge_base"))
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
        self.synthesis_checkpoint_file = os.path.join(
            self.processed_data_dir, "synthesis_checkpoint.json"
        )


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
