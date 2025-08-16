"""Small thin wrapper around litellm to centralize retries, logging and defaults.

Keep it intentionally small: provides `complete()` and `embed()` which call
the litellm library with sane defaults and basic retry/backoff. This lets
the rest of the code avoid repeating retry logic and ensures consistent
flags (cache=True) and logging.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.utils import config

logger = logging.getLogger(__name__)


def complete(
    prompt_messages: List[Dict[str, str]], max_retries: int = 3
) -> Optional[Any]:
    """Call litellm.completion with a few retries. Returns the raw response or None."""
    import litellm

    for attempt in range(max_retries):
        try:
            resp = litellm.completion(
                model=config.SYNTHESIS_MODEL_PROXY,
                messages=prompt_messages,
                stream=False,
                cache=True,
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


def embed(texts: List[str], max_retries: int = 2) -> Optional[List[List[float]]]:
    """Call litellm.embedding with retries. Returns list of vectors or None."""
    import litellm

    for attempt in range(max_retries):
        try:
            resp = litellm.embedding(model=config.EMBEDDING_MODEL_PROXY, input=texts)
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
