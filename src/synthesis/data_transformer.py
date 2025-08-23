import re
from collections import defaultdict
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


class DataTransformer:
    """
    Transforms raw database data into the format expected by the synthesis process.

    This class handles the conversion of database messages into conversation envelopes
    with the proper structure and fields required by the synthesis pipeline.
    """

    def __init__(self):
        self.number_re = re.compile(
            r"(?P<number>\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\b)\s*(?P<unit>%|percent\b|rs\b|inr\b|₹|km\b|m\b|kg\b|k\b|lakh\b|crore\b|million\b|billion\b)?",
            re.IGNORECASE,
        )

    def transform_database_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transforms a list of raw database messages into conversation envelopes.

        Args:
            messages: List of message dictionaries from the database

        Returns:
            List of conversation envelopes in the format expected by synthesis
        """
        if not messages:
            return []

        logger.info(
            f"Transforming {len(messages)} database messages into conversation envelopes"
        )

        # Group messages by source_group_id and topic_id to form conversations
        grouped_messages = defaultdict(list)
        for msg in messages:
            key = (msg["source_group_id"], msg["topic_id"])
            grouped_messages[key].append(msg)

        # Convert grouped messages into conversation format expected by synthesis
        conversations = []
        for (source_group_id, topic_id), conv_messages in grouped_messages.items():
            # Sort messages by date
            conv_messages.sort(key=lambda x: x["date"])

            # Process each message to add normalized_values
            processed_messages = []
            for msg in conv_messages:
                # Add normalized_values field by processing the content
                content = msg.get("content", "")
                if isinstance(content, str):
                    normalized_values = self._normalize_numbers(content)
                else:
                    normalized_values = []

                # Create message with only the fields expected by synthesis
                processed_msg = {
                    "id": msg["id"],
                    "date": msg["date"],
                    "sender_id": msg["sender_id"],
                    "content": msg["content"],
                    "normalized_values": normalized_values,
                }
                processed_messages.append(processed_msg)

            # Create conversation envelope
            conversation = {
                "ingestion_timestamp": conv_messages[0]["ingestion_timestamp"]
                if conv_messages
                else "",
                "ingestion_hash": f"{source_group_id}_{topic_id}",  # Simple hash for now
                "source_files": [conv_messages[0]["source_name"]]
                if conv_messages
                else [],
                "source_names": [conv_messages[0]["source_name"]]
                if conv_messages
                else [],
                "conversation": processed_messages,
                "message_count": len(conv_messages),
            }
            conversations.append(conversation)

        logger.info(
            f"Transformation complete: {len(conversations)} conversation envelopes created"
        )
        return conversations

    def _normalize_numbers(self, text: str) -> List[Dict[str, Any]]:
        """Extracts simple numeric facts from text."""
        results = []
        for m in self.number_re.finditer(text):
            num_str = m.group("number").replace(",", "")
            try:
                val = float(num_str)
            except ValueError:
                val = None
            results.append(
                {
                    "span": m.group(0),
                    "value": val,
                    "unit": (m.group("unit") or "").lower(),
                    "confidence": "medium" if val is not None else "low",
                }
            )
        return results
