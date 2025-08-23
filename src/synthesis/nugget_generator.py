import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from pyrate_limiter import Limiter

from src.core.config import AppSettings
from src.core.error_handler import (
    default_alert_manager,
    handle_critical_errors,
    retry_with_backoff,
)
from src.core.metrics import Metrics
from src.rag import litellm_client
from src.synthesis.conversation_optimizer import ConversationOptimizer

logger = structlog.get_logger(__name__)


class NuggetGenerator:
    """
    Handles the generation of knowledge nuggets from conversations.

    Args:
        settings: The application settings.
        limiter: The rate limiter.
    """

    def __init__(
        self,
        settings: AppSettings,
        limiter: Limiter,
        optimizer: ConversationOptimizer = None,
    ):
        self.settings = settings
        self.limiter = limiter
        self.optimizer = optimizer or ConversationOptimizer()
        self.metrics = Metrics()

    @retry_with_backoff(max_retries=3, initial_wait=2.0, backoff_factor=2.0)
    @handle_critical_errors(default_alert_manager)
    def generate_nuggets(
        self, conv_batch: List[Dict[str, Any]], prompt_template: str
    ) -> List[Dict[str, Any]]:
        """
        Generates a batch of knowledge nuggets from a batch of conversations.

        Args:
            conv_batch: A list of conversations.
            prompt_template: The prompt template to use for generation.

        Returns:
            A list of generated nuggets.
        """

        @self.limiter.as_decorator()
        def _decorated_generation():
            # Apply cost optimization
            optimized_batch = self.optimizer.deduplicate_conversations(conv_batch)
            logger.info(
                f"Optimization: {len(conv_batch)} → {len(optimized_batch)} conversations after deduplication"
            )

            compact_batch = []
            for conv in optimized_batch:
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
            # Safe string formatting - prompt_template is treated as literal text
            prompt_payload = f"{prompt_template}\n\n**Input Conversation Batch:**\n```json\n{formatted_batch}\n```"

            attempts = 3
            response = None
            response_content = ""
            json_match = None
            for attempt in range(attempts):
                try:
                    response = litellm_client.complete(
                        [{"role": "user", "content": prompt_payload}], max_retries=1
                    )
                    self.metrics.record_api_call("litellm_complete", success=True)
                except Exception as e:
                    self.metrics.record_api_call("litellm_complete", success=False)
                    self.metrics.record_error(f"litellm_error: {type(e).__name__}")
                    logger.warning(
                        "LLM returned error, retrying (%d/%d): %s",
                        attempt + 1,
                        attempts,
                        str(e),
                    )
                    time.sleep(2**attempt)
                    continue

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

                # Record metrics
                self.metrics.record_nuggets(len(validated_nuggets))
                self.metrics.record_conversations(len(conv_batch))

                # Log metrics periodically
                if len(validated_nuggets) > 0:
                    self.metrics.log_summary()

                return validated_nuggets
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to decode JSON from LLM response.", exc_info=True
                )
                self._save_failed_batch(conv_batch, "JSONDecodeError", json_str)
                return []

        return _decorated_generation()
