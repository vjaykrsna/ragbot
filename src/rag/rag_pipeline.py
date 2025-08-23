import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import chromadb
import structlog
from chromadb.api.models.Collection import Collection

from src.core.config import AppSettings
from src.rag import litellm_client

logger = structlog.get_logger(__name__)


def sanitize_query_text(text: str) -> str:
    """
    Sanitize query text to prevent injection and improve processing.

    Args:
        text: The input query text

    Returns:
        Sanitized text safe for processing
    """
    if not text:
        return ""

    # Remove excessive whitespace and normalize
    sanitized = re.sub(r"\s+", " ", text.strip())

    # Remove potentially harmful patterns
    sanitized = re.sub(r"[<>]", "", sanitized)  # Remove angle brackets
    sanitized = re.sub(r"javascript:", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"data:", "", sanitized, flags=re.IGNORECASE)

    return sanitized[:2000]  # Limit length


class LiteLLMEmbeddingFunction:
    """Wrapper for litellm.embed to conform to ChromaDB's interface."""

    def __init__(self, model_name: str):
        self._model_name = model_name

    def __call__(self, input: List[str]) -> List[List[float]]:
        return litellm_client.embed(input)

    def name(self) -> str:
        return self._model_name


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline."""

    def __init__(self, settings: AppSettings, db_client: chromadb.Client) -> None:
        self.settings = settings
        self.db_client = db_client
        try:
            embedding_function = LiteLLMEmbeddingFunction(
                model_name=self.settings.litellm.embedding_model_name
            )
            self.collection: Collection = self.db_client.get_or_create_collection(
                name=self.settings.rag.collection_name,
                embedding_function=embedding_function,
            )
            logger.info(
                "Connected to ChromaDB collection '%s' with %d items.",
                self.settings.rag.collection_name,
                self.collection.count(),
            )
        except Exception:
            logger.exception(
                "Failed to connect to ChromaDB collection '%s'.",
                self.settings.rag.collection_name,
            )
            raise

    def embed_query(self, query_text: str) -> List[float]:
        """Generate embedding for the query. Returns vector as list[float]."""
        try:
            if not query_text or not query_text.strip():
                raise ValueError("Query text cannot be empty")

            emb = litellm_client.embed([query_text])
            if emb is None or not emb:
                raise Exception("Embedding service returned empty result")

            if not isinstance(emb, list) or len(emb) == 0:
                raise Exception("Invalid embedding format received")

            embedding = emb[0]
            if not isinstance(embedding, list) or len(embedding) == 0:
                raise Exception("Invalid embedding vector format")

            return embedding

        except ValueError as e:
            logger.error("Invalid query text for embedding: %s", e)
            raise
        except Exception as e:
            logger.exception("Failed to generate embedding for query: %s", query_text)
            raise Exception(f"Embedding generation failed: {str(e)}") from e

    def retrieve_context(
        self, query_embedding: List[float], n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve top-n candidate nuggets from the vector DB and re-rank them."""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["metadatas", "distances"],
            )
            nuggets = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            return self.rerank_and_filter_nuggets(nuggets, distances)
        except Exception:
            logger.exception("Failed to retrieve context from ChromaDB")
            return []

    def rerank_and_filter_nuggets(
        self, nuggets: List[Dict[str, Any]], distances: List[float]
    ) -> List[Dict[str, Any]]:
        if not nuggets:
            return []

        # Filter outdated
        filtered = [n for n in nuggets if n.get("status") != "OUTDATED"]

        now = datetime.now(timezone.utc)
        scored = []
        for i, nugget in enumerate(filtered):
            recency_score = 0.0
            ts = nugget.get("last_message_timestamp")
            if ts:
                try:
                    last_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    days = (now - last_ts).days
                    if days < 1:
                        recency_score = 1.0
                    elif days < 7:
                        recency_score = 0.8
                    elif days < 30:
                        recency_score = 0.5
                    else:
                        recency_score = 0.2
                except Exception:
                    pass

            status_score = self.settings.rag.status_weights.get(
                nugget.get("status", "DEFAULT"),
                self.settings.rag.status_weights["DEFAULT"],
            )
            semantic_score = 1.0 - distances[i] if i < len(distances) else 0.0

            final = (
                semantic_score * self.settings.rag.semantic_score_weight
                + recency_score * self.settings.rag.recency_score_weight
                + status_score * self.settings.rag.status_score_weight
            )
            scored.append((nugget, final))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored]

    def generate_response(
        self, query: str, context_nuggets: List[Dict[str, Any]]
    ) -> str:
        if not context_nuggets:
            return "I couldn't find any relevant information in the knowledge base to answer your question."

        context_str = "\n\n---\n\n".join(
            n.get("full_text", "") for n in context_nuggets
        )
        system_prompt = (
            "You are an AI assistant answering questions based on a provided knowledge base of Telegram chat excerpts.\n"
            "Base your answer strictly on the provided excerpts. If information is missing, say so.\n\n"
            f"Here are the relevant excerpts:\n---\n{context_str}\n---\n"
        )

        try:
            resp = litellm_client.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ]
            )
            if not resp or not getattr(resp, "choices", None):
                raise Exception("LLM completion returned empty")
            return resp.choices[0].message.content
        except Exception:
            logger.exception("Failed to generate response from LLM")
            return "I encountered an error while trying to generate a response."

    def query(self, user_query: str) -> str:
        """Run the full pipeline: embed -> retrieve -> generate."""
        try:
            # Sanitize input first
            sanitized_query = sanitize_query_text(user_query)
            logger.info("Received query: %s", sanitized_query)

            # Basic input validation
            if not sanitized_query:
                return "Please provide a valid question."

            query_embedding = self.embed_query(sanitized_query)
            context_nuggets = self.retrieve_context(query_embedding, n_results=10)
            final = self.generate_response(sanitized_query, context_nuggets[:5])

            logger.info("Generated response successfully")
            return final

        except Exception as e:
            logger.exception("Error in RAG pipeline query: %s", e)
            return "I encountered an error while processing your question. Please try again."


if __name__ == "__main__":
    from src.core.app import initialize_app

    # This is for demonstration and testing purposes.
    # In a real application, the settings would be passed from the entrypoint.
    app_settings = initialize_app()
    rp = RAGPipeline(app_settings)
    q = "What was the discussion about regarding the project architecture?"
    print(rp.query(q))
