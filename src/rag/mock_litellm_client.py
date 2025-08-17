"""
Mock LiteLLM client for testing purposes.
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


def complete(
    prompt_messages: List[Dict[str, str]], max_retries: int = 3
) -> Optional[Any]:
    """
    Mock completion function that returns a dummy response.
    """
    mock_response = MagicMock()
    nugget = {
        "topic": "Test Topic",
        "timestamp": "2023-01-01T12:00:00Z",
        "topic_summary": "This is a test topic.",
        "detailed_analysis": "This is a detailed analysis of the test topic.",
        "status": "Complete",
        "keywords": ["test", "topic"],
        "source_message_ids": [1, 2],
        "user_ids_involved": ["user1", "user2"],
        "normalized_values": [],
        "ingestion_timestamp": "2023-01-01T12:00:00Z",
    }
    nuggets = [nugget]
    mock_response.choices[0].message.content = json.dumps(nuggets)
    return mock_response


def embed(texts: List[str], max_retries: int = 2) -> Optional[List[List[float]]]:
    """
    Mock embedding function that returns dummy embeddings.
    """
    # Return a list of vectors, one for each text.
    embedding_dimension = 1536  # a common dimension for embeddings
    return [[0.1] * embedding_dimension for _ in texts]
