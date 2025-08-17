from dataclasses import dataclass, field
from typing import Dict


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
    collection_name: str = "telegram_knowledge_base_v2"
