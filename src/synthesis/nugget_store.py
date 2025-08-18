import json
import logging
import threading
import uuid
from typing import Any, Dict, List

import chromadb
import chromadb.errors
from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)

# Thread-safe lock
chroma_lock = threading.Lock()


class NuggetStore:
    """
    Handles the storage of knowledge nuggets in ChromaDB.
    """

    def store_nuggets_batch(
        self, collection: Collection, nuggets_with_embeddings: List[Dict[str, Any]]
    ) -> int:
        if not nuggets_with_embeddings:
            return 0

        try:
            with chroma_lock:
                ids = [str(uuid.uuid4()) for _ in nuggets_with_embeddings]
                embeddings = [n["embedding"] for n in nuggets_with_embeddings]
                metadatas = []
                for n in nuggets_with_embeddings:
                    meta = n.copy()
                    del meta["embedding"]
                    if isinstance(meta.get("normalized_values"), list):
                        nv = meta["normalized_values"]
                        meta["normalized_values_count"] = len(nv)
                        meta["normalized_values"] = json.dumps(nv[:10])
                    for key, value in list(meta.items()):
                        if isinstance(value, list) and key != "normalized_values":
                            if len(value) > 10:
                                meta[key] = json.dumps(value[:10])
                            else:
                                meta[key] = json.dumps(value)
                    # ChromaDB cannot handle None values in metadata, so we filter them out.
                    sanitized_meta = {k: v for k, v in meta.items() if v is not None}
                    metadatas.append(sanitized_meta)

                documents = [n["detailed_analysis"] for n in nuggets_with_embeddings]

                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
            return len(nuggets_with_embeddings)
        except (
            ValueError,
            chromadb.errors.DuplicateIDError,
        ) as e:
            logger.error(f"ChromaDB Error storing nuggets: {e}", exc_info=True)
            return 0
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while storing nuggets in ChromaDB: {e}",
                exc_info=True,
            )
            return 0
