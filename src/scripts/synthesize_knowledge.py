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

from src.utils import config, litellm_client
from src.utils import config as _config
from src.utils.logger import setup_logging

# Local file cache disabled by default for production.
CACHE_DIR = None


def _hash_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def completion_cache_get(key: str) -> Optional[str]:
# local completion cache intentionally disabled
    return None


def completion_cache_set(key: str, value: str) -> None:
# no-op when local caching is disabled
    return


def embedding_cache_get(key: str) -> Optional[List[float]]:
# local embedding cache intentionally disabled
    return None


def embedding_cache_set(key: str, emb: List[float]) -> None:
# no-op when local caching is disabled
    return


setup_logging()
logger = logging.getLogger(__name__)

# Thread-safe locks
chroma_lock = threading.Lock()
fail_file_lock = threading.Lock()

# Initialize litellm via centralized config helper
try:
    config.initialize_litellm_client_stub()
except Exception:
    logging.exception("Failed to initialize litellm client via config helper")

rate = Rate(config.REQUESTS_PER_MINUTE, Duration.MINUTE)
limiter = Limiter(rate, max_delay=60000)


# DATABASE & PROGRESS MANAGEMENT
def setup_database() -> Collection:
    """Initializes or connects to the vector database and collection."""
    logging.info(f"Setting up vector database at: {config.DB_PATH}")
    client = chromadb.PersistentClient(path=config.DB_PATH)

    logging.info(f"Attempting to get or create collection: '{config.COLLECTION_NAME}'")
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)

    try:
        client.get_collection(name=config.COLLECTION_NAME)
        logging.info(f"Successfully verified collection '{config.COLLECTION_NAME}'.")
    except Exception as e:
        logging.error(f"Failed to verify collection '{config.COLLECTION_NAME}': {e}")
        raise

    logging.info(
        f"Database collection '{config.COLLECTION_NAME}' is ready with {collection.count()} items."
    )
    return collection


def save_progress(last_processed_index: int) -> None:
    """Saves the last processed conversation index to a file."""
    with open(config.SYNTHESIS_PROGRESS_FILE, "w") as f:
        json.dump({"last_processed_index": last_processed_index}, f)


def load_progress() -> int:
    """Loads the last processed conversation index from a file."""
    try:
        with open(config.SYNTHESIS_PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_processed_index", -1)
    except (FileNotFoundError, json.JSONDecodeError):
        return -1


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
                    logging.warning(
                        f"API Error in {func.__name__} (retriable), attempt {attempt + 1}/{max_retries}. Retrying in {sleep_time}s. Error: {e}",
                        exc_info=True,
                    )
                    time.sleep(sleep_time)
                else:
                    logging.error(
                        f"API Error in {func.__name__} failed after {max_retries} attempts. Error: {e}",
                        exc_info=True,
                    )
                    return None
        return None

    return wrapper


def save_failed_batch(
    conv_batch: List[Dict[str, Any]], error: str, response_text: str = ""
) -> None:
    """Saves a failed conversation batch to a dead-letter queue file in a thread-safe manner."""
    with fail_file_lock:
        with open(config.FAILED_BATCHES_FILE, "a", encoding="utf-8") as f:
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


# MAIN ORCHESTRATION
def main() -> None:
    """Orchestrates the entire knowledge base population process."""
    logging.info("🚀 Starting Knowledge Base v2 Synthesis")

    collection = setup_database()
    conversations = load_processed_data()
    prompt_template = load_prompt_template()
    if not conversations or not prompt_template:
        return

    synthesize_and_populate(conversations, prompt_template, collection)

    logging.info("✅ Knowledge base synthesis complete.")


# DATA LOADING & PROCESSING
def load_processed_data() -> List[Dict[str, Any]]:
    """Loads processed conversation data from the JSON file."""
    file_path = os.path.join(
        config.PROCESSED_DATA_DIR, config.PROCESSED_CONVERSATIONS_FILE
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            logging.info(f"Loading processed data from {file_path}")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load processed data from {file_path}: {e}")
        return []


def load_prompt_template() -> Optional[str]:
    """Loads the prompt template from the markdown file."""
    try:
        with open(config.PROMPT_FILE, "r", encoding="utf-8") as f:
            logging.info(f"Loading prompt template from {config.PROMPT_FILE}")
            return f.read()
    except FileNotFoundError as e:
        logging.error(f"Could not load prompt template: {e}")
        return None


def rate_limit_mapping(*args, **kwargs) -> Tuple[str, int]:
    """Ensures all worker threads share a single rate limit bucket."""
    return "synthesis-worker", 1


@retry_with_backoff
@limiter.as_decorator()(rate_limit_mapping)
def generate_nuggets_batch(
    conv_batch: List[Dict[str, Any]], prompt_template: str
) -> List[Dict[str, Any]]:
    """Generates a batch of knowledge nuggets from a list of conversations."""
# Compact conversations to reduce token usage: keep only necessary fields
    compact_batch = []
    for conv in conv_batch:
# conv may be an envelope created earlier; extract the conversation messages
        conv_msgs = conv.get("conversation") or conv.get("messages") or conv
        compact_msgs = []
        for m in conv_msgs:
            compact_msgs.append(
                {
                    "id": m.get("id"),
                    "date": m.get("date"),
                    "sender_id": m.get("sender_id"),
                    "content": m.get("content"),
                    "normalized_values": m.get("normalized_values", []),
                }
            )
        compact_batch.append(
            {
                "ingestion_hash": conv.get("ingestion_hash"),
                "message_count": conv.get("message_count", len(compact_msgs)),
                "messages": compact_msgs,
            }
        )

    formatted_batch = json.dumps(compact_batch, separators=(",", ":"))
    prompt_payload = f"{prompt_template}\n\n**Input Conversation Batch:**\n```json\n{formatted_batch}\n```"

# Call the LLM and retry a few times if the response is malformed.
    attempts = 3
    response = None
    response_content = ""
    json_match = None
    for attempt in range(attempts):
        response = litellm_client.complete(
            [{"role": "user", "content": prompt_payload}], max_retries=1
        )
        if not response:
            logging.warning(
                "LLM returned empty response, retrying (%d/%d)", attempt + 1, attempts
            )
            time.sleep(2**attempt)
            continue

        response_content = getattr(response.choices[0].message, "content", "") or ""
        json_match = re.search(r"\[.*\]", response_content, re.DOTALL)
        if json_match:
            break
        logging.warning(
            "Malformed/incomplete LLM response on attempt %d/%d; retrying",
            attempt + 1,
            attempts,
        )
        time.sleep(2**attempt)

    if not response or not json_match:
        logging.warning(
            "LLM failed to return a valid JSON array after %d attempts.", attempts
        )
        save_failed_batch(
            conv_batch, "No JSON array in response after retries", response_content
        )
        return []

    json_str = json_match.group(0)

    try:
        response_data = json.loads(json_str)
        if not isinstance(response_data, list):
            logging.warning(f"LLM response is not a list. Response: {json_str}")
            save_failed_batch(conv_batch, "LLM response is not a list", json_str)
            return []

        validated_nuggets = []
        for nugget in response_data:
            required_keys = [
                "topic",
                "timestamp",
                "topic_summary",
                "detailed_analysis",
                "status",
                "keywords",
                "source_message_ids",
                "user_ids_involved",
            ]
# Accept additional optional fields: ingestion_timestamp, source_names, normalized_values
            if all(k in nugget for k in required_keys):
# Ensure optional normalized_values exists as list if missing
                if "normalized_values" not in nugget:
                    nugget["normalized_values"] = []
                if "ingestion_timestamp" not in nugget:
# default to now if LLM didn't add one
                    nugget["ingestion_timestamp"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                validated_nuggets.append(nugget)
            else:
                logging.warning(f"Invalid nugget structure: {nugget}")
                save_failed_batch(conv_batch, "Invalid nugget structure", str(nugget))
        return validated_nuggets
    except json.JSONDecodeError:
        logging.warning("Failed to decode JSON from LLM response.", exc_info=True)
        save_failed_batch(conv_batch, "JSONDecodeError", json_str)
        return []


@retry_with_backoff
@limiter.as_decorator()(rate_limit_mapping)
def embed_nuggets_batch(nuggets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates embeddings for a batch of knowledge nuggets."""
    valid_nuggets = [
        n
        for n in nuggets
        if isinstance(n.get("detailed_analysis"), str)
        and n["detailed_analysis"].strip()
    ]

    if not valid_nuggets:
        logging.warning("No valid documents to embed in the batch.")
        return []

# For cost savings: use an embedding cache keyed by the md5 of the document text.
    docs_to_embed = []
    doc_indices = []

    for i, n in enumerate(valid_nuggets):
        text = n["detailed_analysis"]
        docs_to_embed.append(text)
        doc_indices.append(i)

# Try embedding call with a couple retries to handle transient proxy/provider issues
    embed_attempts = 2
    embedding_response = None
    for attempt in range(embed_attempts):
        emb = litellm_client.embed(docs_to_embed, max_retries=1)
        if emb is not None:
# emulate the previous response structure
            embedding_response = {"data": [[{"embedding": e}] for e in emb]}
        else:
            embedding_response = None
        if embedding_response and embedding_response.get("data"):
            break
        logging.warning(
            "Embedding call failed or returned empty on attempt %d/%d",
            attempt + 1,
            embed_attempts,
        )
        time.sleep(1 + attempt)

    if not embedding_response or not embedding_response.get("data"):
        logging.error("Embedding response invalid after retries")
        raise APIError("Embedding response is empty or invalid")

    returned = [item.get("embedding") for item in embedding_response.get("data", [])]
    if len(returned) != len(docs_to_embed):
        logging.error(
            "Mismatch between embeddings returned and docs requested: %d vs %d",
            len(returned),
            len(docs_to_embed),
        )
        raise APIError("Embedding count mismatch")

    for idx, emb in zip(doc_indices, returned):
        valid_nuggets[idx]["embedding"] = emb
# Attach embedding metadata
        nugget = valid_nuggets[idx]
        nugget.setdefault("meta", {})
        nugget["meta"]["embedding_model"] = _config.EMBEDDING_MODEL_PROXY
        nugget["meta"]["embedding_created_at"] = datetime.utcnow().isoformat()

    return valid_nuggets


def store_nuggets_batch(
    collection: Collection, nuggets_with_embeddings: List[Dict[str, Any]]
) -> int:
    """Stores a batch of nuggets and their embeddings in ChromaDB."""
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
# flatten certain large list fields to avoid bloating Chroma metadata
                if isinstance(meta.get("normalized_values"), list):
# keep a small summary count and store full list as JSON string only if small
                    nv = meta["normalized_values"]
                    meta["normalized_values_count"] = len(nv)
                    if len(nv) <= 10:
                        meta["normalized_values"] = json.dumps(nv)
                    else:
                        meta["normalized_values"] = json.dumps(nv[:10])
                for key, value in list(meta.items()):
                    if isinstance(value, list) and key != "normalized_values":
# keep short lists small; stringify otherwise
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
        logging.error(f"ChromaDB Error storing nuggets: {e}", exc_info=True)
# Optionally, save the failed batch for inspection save_failed_batch(nuggets_with_embeddings, str(e)
        return 0
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while storing nuggets in ChromaDB: {e}",
            exc_info=True,
        )
        return 0


def process_conversation_batch(
    batch: List[Dict[str, Any]], prompt_template: str, collection: Collection
) -> int:
    """Worker function to process a batch of conversations in a thread pool."""
    nuggets = generate_nuggets_batch(batch, prompt_template)
    if not nuggets:
        return 0

    nuggets_with_embeddings = embed_nuggets_batch(nuggets)
    if not nuggets_with_embeddings:
        return 0
# Run a lightweight numeric verifier to reduce hallucinated numbers.
    verified = run_numeric_verifier(nuggets_with_embeddings, batch)

    num_stored = store_nuggets_batch(collection, verified)
    return num_stored


def run_numeric_verifier(
    nuggets: List[Dict[str, Any]], conversations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Compare numeric claims in nuggets with normalized values found in source conversations.

    This is intentionally conservative: if a numeric claim does not have a matching
    normalized value in the source, we mark its confidence as 'model-only' and
    add a flag to the nugget metadata so the UI can surface it.
    """
# Build a quick lookup of numbers from source conversations
    source_numbers = defaultdict(list)
    for conv in conversations:
# conversations may be envelopes produced by process_data
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


def synthesize_and_populate(
    conversations: List[Dict[str, Any]], prompt_template: str, collection: Collection
) -> None:
    """Processes all conversations in batches and populates the database."""
    last_processed_index = load_progress()
    start_index = last_processed_index + 1

    if start_index >= len(conversations):
        logging.info("All conversations have already been processed.")
        return

    logging.info(f"Resuming from conversation index {start_index}")

    batches = [
        conversations[i : i + config.BATCH_SIZE]
        for i in range(start_index, len(conversations), config.BATCH_SIZE)
    ]

# Compute a stable hash for each batch so we can skip work already done.
    def batch_hash(batch: List[Dict[str, Any]]) -> str:
# Use concatenation of ingestion_hashes from envelopes (or messages fallback)
        parts = []
        for conv in batch:
            ih = conv.get("ingestion_hash")
            if not ih:
# fallback: compute from concatenated messages
                msgs = conv.get("conversation") or conv.get("messages") or []
                joined = "".join(m.get("content", "") for m in msgs)
                ih = _hash_text(joined)
            parts.append(ih)
        return _hash_text("|".join(parts))

# load processed hashes to avoid re-synthesizing unchanged conversation envelopes
    processed_hashes = set()
    try:
        ph = os.path.join(config.PROCESSED_DATA_DIR, config.PROCESSED_HASHES_FILE)
        if os.path.exists(ph):
            with open(ph, "r", encoding="utf-8") as f:
                processed_hashes = set(json.load(f))
    except Exception:
        processed_hashes = set()

    total_nuggets_stored = 0
    with tqdm(total=len(batches), desc="Synthesizing Knowledge") as pbar:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.MAX_WORKERS
        ) as executor:
            future_to_batch_index = {}
            batch_index_to_hash = {}
            for i, batch in enumerate(batches):
                bh = batch_hash(batch)
                batch_index_to_hash[i] = bh
                if bh in processed_hashes:
                    logging.info(f"Skipping already-processed batch {i} (hash={bh})")
                    pbar.update(1)
                    continue
                fut = executor.submit(
                    process_conversation_batch, batch, prompt_template, collection
                )
                future_to_batch_index[fut] = i

            for future in concurrent.futures.as_completed(future_to_batch_index):
                batch_index = future_to_batch_index[future]
                try:
                    num_stored = future.result()
                    if num_stored > 0:
# mark this batch as processed by its batch hash
                        bh = batch_index_to_hash.get(batch_index)
                        if bh:
                            processed_hashes.add(bh)
                        total_nuggets_stored += num_stored
                        last_item_in_batch = len(batches[batch_index]) - 1
                        last_processed_index = (
                            start_index
                            + (batch_index * config.BATCH_SIZE)
                            + last_item_in_batch
                        )
                        save_progress(last_processed_index)
                except Exception as e:
                    logging.error(
                        f"An error occurred while processing batch index {batch_index}: {e}",
                        exc_info=True,
                    )
                pbar.update(1)
                pbar.set_postfix({"Stored": f"{total_nuggets_stored}"})

# persist processed hashes
    try:
        php = os.path.join(config.PROCESSED_DATA_DIR, config.PROCESSED_HASHES_FILE)
        with open(php, "w", encoding="utf-8") as f:
            json.dump(list(processed_hashes), f)
    except Exception:
        pass

    logging.info(
        f"\n--- Knowledge Synthesis Complete ---"
        f"Total nuggets stored in this run: {total_nuggets_stored}"
    )


if __name__ == "__main__":
    main()
