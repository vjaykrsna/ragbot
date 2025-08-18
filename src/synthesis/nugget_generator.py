import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from litellm import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pyrate_limiter import Limiter

from src.core.config import AppSettings
from src.rag import litellm_client
from src.synthesis.decorators import retry_with_backoff

logger = logging.getLogger(__name__)


class NuggetGenerator:
    """
    Handles the generation of knowledge nuggets from conversations.
    """

    def __init__(self, settings: AppSettings, limiter: Limiter):
        self.settings = settings
        self.limiter = limiter

    @retry_with_backoff
    def generate_nuggets_batch(
        self, conv_batch: List[Dict[str, Any]], prompt_template: str
    ) -> List[Dict[str, Any]]:
        @self.limiter.as_decorator()
        def _decorated_generation():
            compact_batch = []
            for conv in conv_batch:
                conv_msgs = conv.get("conversation") or conv.get("messages") or conv
                compact_msgs = [
                    {
                        "id": m.get("id"),
                        "date": m.get("date"),
                        "sender_id": m.get("sender_id"),
                        "content": m.get("content"),
                        "normalized_values": m.get("normalized_values", []),
                    }
                    for m in conv_msgs
                ]
                compact_batch.append(
                    {
                        "ingestion_hash": conv.get("ingestion_hash"),
                        "message_count": conv.get("message_count", len(compact_msgs)),
                        "messages": compact_msgs,
                    }
                )

            formatted_batch = json.dumps(compact_batch, separators=(",", ":"))
            prompt_payload = f"{prompt_template}\n\n**Input Conversation Batch:**\n```json\n{formatted_batch}\n```"

            attempts = 3
            response = None
            response_content = ""
            json_match = None
            for attempt in range(attempts):
                response = litellm_client.complete(
                    [{"role": "user", "content": prompt_payload}], max_retries=1
                )
                if not response:
                    logger.warning(
                        "LLM returned empty response, retrying (%d/%d)",
                        attempt + 1,
                        attempts,
                    )
                    time.sleep(2**attempt)
                    continue

                response_content = (
                    getattr(response.choices[0].message, "content", "") or ""
                )
                json_match = re.search(r"\[.*\]", response_content, re.DOTALL)
                if json_match:
                    break
                logger.warning(
                    "Malformed/incomplete LLM response on attempt %d/%d; retrying",
                    attempt + 1,
                    attempts,
                )
                time.sleep(2**attempt)

            if not response or not json_match:
                logger.warning(
                    "LLM failed to return a valid JSON array after %d attempts.",
                    attempts,
                )
                self._save_failed_batch(
                    conv_batch,
                    "No JSON array in response after retries",
                    response_content,
                )
                return []

            json_str = json_match.group(0)
            try:
                response_data = json.loads(json_str)
                if not isinstance(response_data, list):
                    logger.warning(f"LLM response is not a list. Response: {json_str}")
                    self._save_failed_batch(
                        conv_batch, "LLM response is not a list", json_str
                    )
                    return []

                validated_nuggets = []
                for nugget in response_data:
                    required_keys = [
                        "topic",
                        "timestamp",
                        "topic_summary",
                        "detailed_analysis",
                        "status",
                        "keywords",
                        "source_message_ids",
                        "user_ids_involved",
                    ]
                    if all(k in nugget for k in required_keys):
                        if "normalized_values" not in nugget:
                            nugget["normalized_values"] = []
                        if "ingestion_timestamp" not in nugget:
                            nugget["ingestion_timestamp"] = datetime.now(
                                timezone.utc
                            ).isoformat()
                        validated_nuggets.append(nugget)
                    else:
                        logger.warning(f"Invalid nugget structure: {nugget}")
                        self._save_failed_batch(
                            conv_batch, "Invalid nugget structure", str(nugget)
                        )
                return validated_nuggets
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to decode JSON from LLM response.", exc_info=True
                )
                self._save_failed_batch(conv_batch, "JSONDecodeError", json_str)
                return []

        return _decorated_generation()
