import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from litellm import APIError
from pyrate_limiter import Limiter

from src.core.config import AppSettings
from src.rag import litellm_client
from src.synthesis.decorators import retry_with_backoff

logger = logging.getLogger(__name__)


class NuggetEmbedder:
    """
    Handles the embedding of knowledge nuggets.
    """

    def __init__(self, settings: AppSettings, limiter: Limiter):
        self.settings = settings
        self.limiter = limiter

    @retry_with_backoff
    def embed_nuggets_batch(
        self, nuggets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        @self.limiter.as_decorator()
        def _decorated_embedding():
            valid_nuggets = [
                n
                for n in nuggets
                if isinstance(n.get("detailed_analysis"), str)
                and n["detailed_analysis"].strip()
            ]
            if not valid_nuggets:
                logger.warning("No valid documents to embed in the batch.")
                return []

            docs_to_embed = [n["detailed_analysis"] for n in valid_nuggets]
            embed_attempts = 2
            embedding_response = None
            for attempt in range(embed_attempts):
                emb = litellm_client.embed(docs_to_embed, max_retries=1)
                if emb is not None:
                    embedding_response = {"data": [{"embedding": e} for e in emb]}
                else:
                    embedding_response = None

                if embedding_response and embedding_response.get("data"):
                    break
                logger.warning(
                    "Embedding call failed or returned empty on attempt %d/%d",
                    attempt + 1,
                    embed_attempts,
                )
                time.sleep(1 + attempt)

            if not embedding_response or not embedding_response.get("data"):
                logger.error("Embedding response invalid after retries")
                raise APIError("Embedding response is empty or invalid")

            returned_embeddings = [
                item.get("embedding") for item in embedding_response.get("data", [])
            ]
            if len(returned_embeddings) != len(docs_to_embed):
                logger.error(
                    "Mismatch between embeddings returned and docs requested: %d vs %d",
                    len(returned_embeddings),
                    len(docs_to_embed),
                )
                raise APIError("Embedding count mismatch")

            for i, emb in enumerate(returned_embeddings):
                valid_nuggets[i]["embedding"] = emb
                nugget = valid_nuggets[i]
                nugget["embedding_model"] = self.settings.litellm.embedding_model_proxy
                nugget["embedding_created_at"] = datetime.now(timezone.utc).isoformat()

            return valid_nuggets

        return _decorated_embedding()
