"""
Configuration validator that validates settings values.
"""

import logging

from .models import (
    LiteLLMSettings,
    RAGSettings,
    SynthesisSettings,
    TelegramSettings,
)


def validate_configuration(
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
        logger = logging.getLogger(__name__)
        logger.warning(
            f"max_workers ({synthesis.max_workers}) exceeds synthesis API keys ({synthesis_keys}). "
            f"Consider reducing max_workers or adding more API keys."
        )

    # Validate rate limits
    if synthesis.requests_per_minute > (
        synthesis_keys * 60
    ):  # Conservative estimate per key
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
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_CONCURRENT_GROUPS ({telegram.extraction.concurrent_groups}) should be between 1 and 5. "
            f"Values outside this range may cause performance issues or rate limiting."
        )

    if (
        telegram.extraction.messages_per_request < 50
        or telegram.extraction.messages_per_request > 1000
    ):
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_MESSAGES_PER_REQUEST ({telegram.extraction.messages_per_request}) should be between 50 and 1000. "
            f"Values outside this range may cause performance issues or rate limiting."
        )

    if telegram.extraction.buffer_size < 100 or telegram.extraction.buffer_size > 5000:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_BUFFER_SIZE ({telegram.extraction.buffer_size}) should be between 100 and 5000. "
            f"Values outside this range may cause performance issues or memory problems."
        )

    if (
        telegram.extraction.ui_update_interval < 1
        or telegram.extraction.ui_update_interval > 5
    ):
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_UI_UPDATE_INTERVAL ({telegram.extraction.ui_update_interval}) should be between 1 and 5 seconds. "
            f"Values outside this range may cause UI issues or unnecessary I/O overhead."
        )

    if telegram.extraction.batch_size < 50 or telegram.extraction.batch_size > 1000:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_BATCH_SIZE ({telegram.extraction.batch_size}) should be between 50 and 1000. "
            f"Values outside this range may cause performance issues or memory problems."
        )

    if (
        telegram.extraction.progress_update_messages < 10
        or telegram.extraction.progress_update_messages > 1000
    ):
        logger = logging.getLogger(__name__)
        logger.warning(
            f"TELEGRAM_PROGRESS_UPDATE_MESSAGES ({telegram.extraction.progress_update_messages}) should be between 10 and 1000. "
            f"Values outside this range may cause UI issues or unnecessary I/O overhead."
        )
