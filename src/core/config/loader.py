"""
Configuration loader that loads settings from environment variables.
"""

import json
import os
from functools import lru_cache

from dotenv import load_dotenv

from .models import (
    AppSettings,
    ConversationSettings,
    LiteLLMCacheSettings,
    LiteLLMModelInfo,
    LiteLLMModelParams,
    LiteLLMRouterSettings,
    LiteLLMSettings,
    PathSettings,
    RAGSettings,
    SynthesisSettings,
    TelegramExtractionSettings,
    TelegramSettings,
)


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
    from .validator import validate_configuration

    validate_configuration(
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
