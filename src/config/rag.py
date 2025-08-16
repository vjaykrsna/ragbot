from typing import Dict
from pydantic import BaseModel, Field

class RAGSettings(BaseModel):
    """Settings for the RAG pipeline."""
    semantic_score_weight: float = Field(0.5, env="SEMANTIC_SCORE_WEIGHT")
    recency_score_weight: float = Field(0.3, env="RECENCY_SCORE_WEIGHT")
    status_score_weight: float = Field(0.2, env="STATUS_SCORE_WEIGHT")
    status_weights: Dict[str, float] = {
        "FACT": 1.5,
        "COMMUNITY_OPINION": 1.0,
        "SPECULATION": 0.5,
        "DEFAULT": 0.1,
    }
    collection_name: str = "telegram_knowledge_base_v2"