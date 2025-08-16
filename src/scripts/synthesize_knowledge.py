"""
Entrypoint for the knowledge synthesis pipeline.

This script initializes the application environment and runs the main knowledge
synthesis pipeline to convert structured conversations into a searchable
knowledge base.
"""

import concurrent.futures
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
import chromadb.errors
from chromadb.api.models.Collection import Collection
from litellm import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pyrate_limiter import Duration, Limiter, Rate
from tqdm import tqdm

from src.core.app import initialize_app
from src.core.settings import AppSettings
from src.utils import litellm_client

logger = logging.getLogger(__name__)

# Thread-safe locks
chroma_lock = threading.Lock()
fail_file_lock = threading.Lock()


def retry_with_backoff(
    func: Callable,
    max_retries: int = 5,
    initial_wait: int = 5,
    backoff_factor: int = 2,
):
    """A decorator to retry a function with exponential backoff."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (
                RateLimitError,
                APIConnectionError,
                ServiceUnavailableError,
                Timeout,
                APIError,
            ) as e:
                if attempt < max_retries - 1:
                    sleep_time = initial_wait * (backoff_factor**attempt)
                    logger.warning(
                        f"API Error in {func.__name__} (retriable), attempt {attempt + 1}/{max_retries}. Retrying in {sleep_time}s. Error: {e}",
                        exc_info=True,
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(
                        f"API Error in {func.__name__} failed after {max_retries} attempts. Error: {e}",
                        exc_info=True,
                    )
                    return None
        return None

    return wrapper


class KnowledgeSynthesizer:
    """
    Orchestrates the entire knowledge base population process.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.rate = Rate(self.settings.synthesis.requests_per_minute, Duration.MINUTE)
        self.limiter = Limiter(self.rate, max_delay=60000)

    def run(self) -> None:
        """Executes the entire synthesis pipeline."""
        logger.info("🚀 Starting Knowledge Base v2 Synthesis")

        collection = self._setup_database()
        conversations = self._load_processed_data()
        prompt_template = self._load_prompt_template()
        if not conversations or not prompt_template:
            return

        self._synthesize_and_populate(conversations, prompt_template, collection)

        logger.info("✅ Knowledge base synthesis complete.")

    def _setup_database(self) -> Collection:
        """Initializes or connects to the vector database and collection."""
        db_path = self.settings.paths.db_path
        collection_name = self.settings.rag.collection_name
        logger.info(f"Setting up vector database at: {db_path}")
        client = chromadb.PersistentClient(path=db_path)

        logger.info(f"Attempting to get or create collection: '{collection_name}'")
        collection = client.get_or_create_collection(name=collection_name)

        try:
            client.get_collection(name=collection_name)
            logger.info(f"Successfully verified collection '{collection_name}'.")
        except Exception as e:
            logger.error(f"Failed to verify collection '{collection_name}': {e}")
            raise

        logger.info(
            f"Database collection '{collection_name}' is ready with {collection.count()} items."
        )
        return collection

    def _load_processed_data(self) -> List[Dict[str, Any]]:
        """Loads processed conversation data from the JSON file."""
        file_path = os.path.join(
            self.settings.paths.processed_data_dir,
            self.settings.paths.processed_conversations_file,
        )
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                logger.info(f"Loading processed data from {file_path}")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load processed data from {file_path}: {e}")
            return []

    def _load_prompt_template(self) -> Optional[str]:
        """Loads the prompt template from the markdown file."""
        try:
            with open(self.settings.paths.prompt_file, "r", encoding="utf-8") as f:
                logger.info(f"Loading prompt template from {self.settings.paths.prompt_file}")
                return f.read()
        except FileNotFoundError as e:
            logger.error(f"Could not load prompt template: {e}")
            return None

    def _synthesize_and_populate(
        self,
        conversations: List[Dict[str, Any]],
        prompt_template: str,
        collection: Collection,
    ) -> None:
        """Processes all conversations in batches and populates the database."""
        last_processed_index = self._load_progress()
        start_index = last_processed_index + 1

        if start_index >= len(conversations):
            logger.info("All conversations have already been processed.")
            return

        logger.info(f"Resuming from conversation index {start_index}")

        batch_size = self.settings.synthesis.batch_size
        batches = [
            conversations[i : i + batch_size]
            for i in range(start_index, len(conversations), batch_size)
        ]

        processed_hashes = self._load_processed_hashes()
        total_nuggets_stored = 0

        with tqdm(total=len(batches), desc="Synthesizing Knowledge") as pbar:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.settings.synthesis.max_workers
            ) as executor:
                future_to_batch_index = {}
                batch_index_to_hash = {}
                for i, batch in enumerate(batches):
                    bh = self._batch_hash(batch)
                    batch_index_to_hash[i] = bh
                    if bh in processed_hashes:
                        logger.info(f"Skipping already-processed batch {i} (hash={bh})")
                        pbar.update(1)
                        continue
                    fut = executor.submit(
                        self._process_conversation_batch, batch, prompt_template, collection
                    )
                    future_to_batch_index[fut] = i

                for future in concurrent.futures.as_completed(future_to_batch_index):
                    batch_index = future_to_batch_index[future]
                    try:
                        num_stored = future.result()
                        if num_stored > 0:
                            bh = batch_index_to_hash.get(batch_index)
                            if bh:
                                processed_hashes.add(bh)
                            total_nuggets_stored += num_stored
                            last_item_in_batch = len(batches[batch_index]) - 1
                            new_last_processed_index = (
                                start_index
                                + (batch_index * batch_size)
                                + last_item_in_batch
                            )
                            self._save_progress(new_last_processed_index)
                    except Exception as e:
                        logger.error(
                            f"An error occurred while processing batch index {batch_index}: {e}",
                            exc_info=True,
                        )
                    pbar.update(1)
                    pbar.set_postfix({"Stored": f"{total_nuggets_stored}"})

        self._save_processed_hashes(processed_hashes)
        logger.info(
            f"\n--- Knowledge Synthesis Complete ---\n"
            f"Total nuggets stored in this run: {total_nuggets_stored}"
        )

    def _process_conversation_batch(
        self, batch: List[Dict[str, Any]], prompt_template: str, collection: Collection
    ) -> int:
        """Worker function to process a batch of conversations."""
        nuggets = self._generate_nuggets_batch(batch, prompt_template)
        if not nuggets:
            return 0

        nuggets_with_embeddings = self._embed_nuggets_batch(nuggets)
        if not nuggets_with_embeddings:
            return 0

        verified = self._run_numeric_verifier(nuggets_with_embeddings, batch)
        num_stored = self._store_nuggets_batch(collection, verified)
        return num_stored

    @retry_with_backoff
    def _generate_nuggets_batch(
        self, conv_batch: List[Dict[str, Any]], prompt_template: str
    ) -> List[Dict[str, Any]]:
        # This method remains largely the same, but uses self.limiter
        @self.limiter.as_decorator()(lambda: ("synthesis-worker", 1))
        def _decorated_generation():
            compact_batch = []
            for conv in conv_batch:
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
            prompt_payload = f"{prompt_template}\n\n**Input Conversation Batch:**\n```json\n{formatted_batch}\n```"

            attempts = 3
            response = None
            response_content = ""
            json_match = None
            for attempt in range(attempts):
                response = litellm_client.complete(
                    [{"role": "user", "content": prompt_payload}], max_retries=1
                )
                if not response:
                    logger.warning(
                        "LLM returned empty response, retrying (%d/%d)", attempt + 1, attempts
                    )
                    time.sleep(2**attempt)
                    continue

                response_content = getattr(response.choices[0].message, "content", "") or ""
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
                    "LLM failed to return a valid JSON array after %d attempts.", attempts
                )
                self._save_failed_batch(
                    conv_batch, "No JSON array in response after retries", response_content
                )
                return []

            json_str = json_match.group(0)
            try:
                response_data = json.loads(json_str)
                if not isinstance(response_data, list):
                    logger.warning(f"LLM response is not a list. Response: {json_str}")
                    self._save_failed_batch(conv_batch, "LLM response is not a list", json_str)
                    return []

                validated_nuggets = []
                for nugget in response_data:
                    required_keys = [
                        "topic", "timestamp", "topic_summary", "detailed_analysis",
                        "status", "keywords", "source_message_ids", "user_ids_involved",
                    ]
                    if all(k in nugget for k in required_keys):
                        if "normalized_values" not in nugget:
                            nugget["normalized_values"] = []
                        if "ingestion_timestamp" not in nugget:
                            nugget["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()
                        validated_nuggets.append(nugget)
                    else:
                        logger.warning(f"Invalid nugget structure: {nugget}")
                        self._save_failed_batch(conv_batch, "Invalid nugget structure", str(nugget))
                return validated_nuggets
            except json.JSONDecodeError:
                logger.warning("Failed to decode JSON from LLM response.", exc_info=True)
                self._save_failed_batch(conv_batch, "JSONDecodeError", json_str)
                return []
        return _decorated_generation()


    @retry_with_backoff
    def _embed_nuggets_batch(self, nuggets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # This method also remains largely the same
        @self.limiter.as_decorator()(lambda: ("synthesis-worker", 1))
        def _decorated_embedding():
            valid_nuggets = [
                n for n in nuggets if isinstance(n.get("detailed_analysis"), str) and n["detailed_analysis"].strip()
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

            returned_embeddings = [item.get("embedding") for item in embedding_response.get("data", [])]
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
                nugget.setdefault("meta", {})
                nugget["meta"]["embedding_model"] = self.settings.litellm.embedding_model_proxy
                nugget["meta"]["embedding_created_at"] = datetime.utcnow().isoformat()

            return valid_nuggets
        return _decorated_embedding()

    def _store_nuggets_batch(
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
                    metadatas.append(meta)

                documents = [n["detailed_analysis"] for n in nuggets_with_embeddings]

                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
            return len(nuggets_with_embeddings)
        except (
            chromadb.errors.InvalidDimensionError,
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

    def _run_numeric_verifier(
        self, nuggets: List[Dict[str, Any]], conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        source_numbers = defaultdict(list)
        for conv in conversations:
            conv_msgs = conv.get("conversation") or conv.get("messages") or []
            for m in conv_msgs:
                nvals = m.get("normalized_values") or []
                for nv in nvals:
                    if nv.get("value") is not None:
                        source_numbers[round(float(nv.get("value")), 6)].append(nv)

        for nug in nuggets:
            nug_meta = nug.setdefault("meta", {})
            nug_meta.setdefault("verification", {})
            mismatches = []
            for nv in nug.get("normalized_values", []):
                val = nv.get("value")
                if val is None:
                    mismatches.append(nv)
                    continue
                key = round(float(val), 6)
                if key not in source_numbers:
                    mismatches.append(nv)

            if mismatches:
                nug_meta["verification"]["numeric_mismatch"] = True
                nug_meta["verification"]["mismatch_count"] = len(mismatches)
                nug_meta["confidence"] = nug_meta.get("confidence", "Low")
            else:
                nug_meta["verification"]["numeric_mismatch"] = False
                nug_meta["confidence"] = nug_meta.get("confidence", "High")

        return nuggets

    def _save_progress(self, last_processed_index: int) -> None:
        with open(self.settings.paths.synthesis_progress_file, "w") as f:
            json.dump({"last_processed_index": last_processed_index}, f)

    def _load_progress(self) -> int:
        try:
            with open(self.settings.paths.synthesis_progress_file, "r") as f:
                return json.load(f).get("last_processed_index", -1)
        except (FileNotFoundError, json.JSONDecodeError):
            return -1

    def _save_failed_batch(
        self, conv_batch: List[Dict[str, Any]], error: str, response_text: str = ""
    ) -> None:
        with fail_file_lock:
            os.makedirs(os.path.dirname(self.settings.paths.failed_batches_file), exist_ok=True)
            with open(self.settings.paths.failed_batches_file, "a", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "error": error,
                        "response_text": response_text,
                        "batch": conv_batch,
                    },
                    f,
                )
                f.write("\n")

    def _batch_hash(self, batch: List[Dict[str, Any]]) -> str:
        parts = []
        for conv in batch:
            ih = conv.get("ingestion_hash")
            if not ih:
                msgs = conv.get("conversation") or conv.get("messages") or []
                joined = "".join(m.get("content", "") for m in msgs)
                ih = hashlib.md5(joined.encode("utf-8")).hexdigest()
            parts.append(ih)
        return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()

    def _load_processed_hashes(self) -> set:
        path = os.path.join(
            self.settings.paths.processed_data_dir, self.settings.paths.processed_hashes_file
        )
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def _save_processed_hashes(self, hashes: set) -> None:
        path = os.path.join(
            self.settings.paths.processed_data_dir, self.settings.paths.processed_hashes_file
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(hashes), f)
        except IOError:
            logger.error(f"Failed to save processed hashes to {path}")


def main() -> None:
    """Initializes the application and runs the knowledge synthesis pipeline."""
    settings = initialize_app()
    synthesizer = KnowledgeSynthesizer(settings)
    synthesizer.run()


if __name__ == "__main__":
    main()
