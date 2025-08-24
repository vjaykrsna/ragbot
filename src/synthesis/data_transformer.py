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
        # Use the shared regex pattern from text_utils
        from src.core.text_utils import NUMBER_RE

        self.number_re = NUMBER_RE

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
            # Use safe access with defaults for required fields
            source_group_id = msg.get("source_group_id", 0)
            topic_id = msg.get("topic_id", 0)
            key = (source_group_id, topic_id)
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
                    # Use the shared normalize_numbers function
                    from src.core.text_utils import normalize_numbers

                    normalized_values = normalize_numbers(content)
                else:
                    normalized_values = []

                # Create message with only the fields expected by synthesis
                processed_msg = {
                    "id": msg.get("id", 0),
                    "date": msg.get("date", ""),
                    "sender_id": msg.get("sender_id", ""),
                    "content": msg.get("content", ""),
                    "normalized_values": normalized_values,
                }
                processed_messages.append(processed_msg)

            # Create conversation envelope
            conversation = {
                "ingestion_timestamp": conv_messages[0].get("ingestion_timestamp", "")
                if conv_messages
                else "",
                "ingestion_hash": f"{source_group_id}_{topic_id}",  # Simple hash for now
                "source_files": [conv_messages[0].get("source_name", "")]
                if conv_messages
                else [],
                "source_names": [conv_messages[0].get("source_name", "")]
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
