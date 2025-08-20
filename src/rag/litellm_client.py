"""Small thin wrapper around litellm to centralize retries, logging and defaults.

Keep it intentionally small: provides `complete()` and `embed()` which call
the litellm library with sane defaults and basic retry/backoff. This lets
the rest of the code avoid repeating retry logic and ensures consistent
flags (cache=True) and logging.
"""

import logging
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import litellm

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# --- Lazy Client Initialization ---
# The router is initialized lazily on the first call to complete() or embed()
# to prevent `get_settings()` from running on module import. This allows
# utility scripts to import this module without a fully configured environment.
_router: Optional[litellm.Router] = None


def _get_router() -> litellm.Router:
    """Initializes and returns the LiteLLM router, ensuring it's a singleton."""
    global _router
    if _router is None:
        logger.info("Initializing LiteLLM router...")
        settings = get_settings().litellm

        # Set general LiteLLM settings
        litellm.drop_params = settings.drop_params
        litellm.turn_off_message_logging = settings.turn_off_message_logging
        litellm.set_verbose = settings.set_verbose

        # Convert dataclasses to dicts for LiteLLM
        model_list_dict = [asdict(m) for m in settings.model_list]
        router_settings_dict = asdict(settings.router_settings)

        # Instantiate the router
        _router = litellm.Router(model_list=model_list_dict, **router_settings_dict)
        logger.info("LiteLLM router initialized.")
    return _router


def complete(
    prompt_messages: List[Dict[str, str]], max_retries: int = None
) -> Optional[Any]:
    """Call router.completion with retries. Returns the raw response or None."""
    if max_retries is None:
        max_retries = int(os.getenv("COMPLETION_MAX_RETRIES", "3"))

    router = _get_router()
    synthesis_model_name = os.getenv("SYNTHESIS_MODEL_NAME", "gemini-synthesis-model")

    for attempt in range(max_retries):
        try:
            resp = router.completion(
                model=synthesis_model_name,  # Target the synthesis model group
                messages=prompt_messages,
            )
            return resp
        except Exception as e:
            logger.warning(
                "Completion attempt %d/%d failed: %s",
                attempt + 1,
                max_retries,
                e,
                exc_info=True,
            )
            time.sleep(1 + attempt)
    logger.error("Completion failed after %d attempts", max_retries)
    return None


def embed(texts: List[str], max_retries: int = None) -> Optional[List[List[float]]]:
    """Call router.embedding with retries. Returns list of vectors or None."""
    if max_retries is None:
        max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "2"))

    router = _get_router()
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "gemini-embedding-model")

    for attempt in range(max_retries):
        try:
            resp = router.embedding(
                model=embedding_model_name,  # Target the embedding model group
                input=texts,
            )
            if resp and resp.get("data"):
                return [item.get("embedding") for item in resp["data"]]
        except Exception as e:
            logger.warning(
                "Embedding attempt %d/%d failed: %s",
                attempt + 1,
                max_retries,
                e,
                exc_info=True,
            )
            time.sleep(1 + attempt)
    logger.error("Embedding failed after %d attempts", max_retries)
    return None
