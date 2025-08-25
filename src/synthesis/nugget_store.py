import json
import threading
import uuid
from typing import Any, Dict, List, Mapping, Union

import chromadb
import structlog
from chromadb.api.models.Collection import Collection

from src.core.di.interfaces import NuggetStorerInterface

logger = structlog.get_logger(__name__)

# Thread-safe lock for ChromaDB operations
chroma_lock = threading.Lock()


class NuggetStore(NuggetStorerInterface):
    """
    Handles the storage of knowledge nuggets in ChromaDB.
    """

    def store_nuggets_batch(
        self, collection: Collection, nuggets_with_embeddings: List[Dict[str, Any]]
    ) -> int:
        """
        Stores a batch of nuggets with embeddings in the database.

        Args:
            collection: The ChromaDB collection to store the nuggets in.
            nuggets_with_embeddings: A list of nuggets with embeddings.

        Returns:
            The number of nuggets stored.
        """
        if not nuggets_with_embeddings:
            return 0

        try:
            with chroma_lock:
                ids = [str(uuid.uuid4()) for _ in nuggets_with_embeddings]
                embeddings = [n["embedding"] for n in nuggets_with_embeddings]
                # Prepare metadata for ChromaDB
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
                    # Also ensure all values are of allowed types (str, int, float, bool, None)
                    sanitized_meta: Dict[str, Union[str, int, float, bool, None]] = {}
                    for k, v in meta.items():
                        if v is None:
                            continue
                        # Convert values to allowed types
                        if isinstance(v, (str, int, float, bool)):
                            sanitized_meta[k] = v
                        elif isinstance(v, (list, dict)):
                            # Convert complex types to JSON strings
                            sanitized_meta[k] = json.dumps(v)
                        else:
                            # Convert everything else to string
                            sanitized_meta[k] = str(v)
                    metadatas.append(sanitized_meta)

                documents = [n["detailed_analysis"] for n in nuggets_with_embeddings]

                from typing import cast

                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=cast(
                        List[Mapping[str, Union[str, int, float, bool, None]]],
                        metadatas,
                    ),
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
