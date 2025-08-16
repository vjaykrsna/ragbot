import os
import json
import chromadb
import litellm
import logging
import uuid
import concurrent.futures
import time
import re
import threading
from datetime import datetime
from functools import wraps
from tqdm import tqdm
from pyrate_limiter import Duration, Rate, Limiter
from src.utils import config
from typing import Any, Dict, List, Optional, Tuple, Callable
from litellm import (
    APIError,
    RateLimitError,
    APIConnectionError,
    ServiceUnavailableError,
    Timeout,
)
import chromadb.errors
from chromadb.api.models.Collection import Collection
from src.utils.logger import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

# Thread-safe locks
chroma_lock = threading.Lock()
fail_file_lock = threading.Lock()

# Configure litellm via environment/proxy (do not hardcode keys)
if config.LITELLM_PROXY_URL:
    litellm.api_base = config.LITELLM_PROXY_URL
litellm.api_key = os.getenv("LITELLM_API_KEY", "")
try:
    litellm.set_verbose(False)
except Exception:
    pass

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

    logging.info(f"Database collection '{config.COLLECTION_NAME}' is ready with {collection.count()} items.")
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
                        f"API Error in {func.__name__} (retriable), attempt {attempt+1}/{max_retries}. Retrying in {sleep_time}s. Error: {e}",
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
    try:
        with open(config.PROCESSED_CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            logging.info(f"Loading processed data from {config.PROCESSED_CONVERSATIONS_FILE}")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load processed data: {e}")
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
    formatted_batch = json.dumps(conv_batch, indent=2)
    final_prompt = f"{prompt_template}\n\n**Input Conversation Batch:**\n```json\n{formatted_batch}\n```"

    response = litellm.completion(
        model=config.SYNTHESIS_MODEL_PROXY,
        messages=[{"role": "user", "content": final_prompt}],
        stream=False,
        cache=True,
    )

    if not response:
        raise APIError("LLM returned an empty response.")

    if getattr(response, "cache_hit", False):
        logging.info("Completion cache hit!")

    response_content = response.choices[0].message.content or ""
    
    json_match = re.search(r"\[.*\]", response_content, re.DOTALL)
    if not json_match:
        logging.warning(f"No JSON array found in LLM response: {response_content}")
        save_failed_batch(conv_batch, "No JSON array in response", response_content)
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
            if all(
                key in nugget
                for key in [
                    "topic", "timestamp", "topic_summary", "detailed_analysis",
                    "status", "keywords", "source_message_ids", "user_ids_involved",
                ]
            ):
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
        n for n in nuggets 
        if isinstance(n.get("detailed_analysis"), str) and n["detailed_analysis"].strip()
    ]
    
    if not valid_nuggets:
        logging.warning("No valid documents to embed in the batch.")
        return []

    valid_docs = [n["detailed_analysis"] for n in valid_nuggets]

    embedding_response = litellm.embedding(model=config.EMBEDDING_MODEL_PROXY, input=valid_docs)

    if not embedding_response or not embedding_response.get("data"):
        raise APIError("Embedding response is empty or invalid")

    final_embeddings = [item["embedding"] for item in embedding_response["data"]]

    if len(final_embeddings) != len(valid_nuggets):
        logging.error("Mismatch between number of nuggets and embeddings returned.")
        return []

    for i, nugget in enumerate(valid_nuggets):
        nugget["embedding"] = final_embeddings[i]

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
                for key, value in meta.items():
                    if isinstance(value, list):
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
    except (chromadb.errors.InvalidDimensionError, chromadb.errors.DuplicateIDError) as e:
        logging.error(f"ChromaDB Error storing nuggets: {e}", exc_info=True)
        # Optionally, save the failed batch for inspection
        # save_failed_batch(nuggets_with_embeddings, str(e))
        return 0
    except Exception as e:
        logging.error(f"An unexpected error occurred while storing nuggets in ChromaDB: {e}", exc_info=True)
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

    num_stored = store_nuggets_batch(collection, nuggets_with_embeddings)
    return num_stored


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

    total_nuggets_stored = 0
    with tqdm(total=len(batches), desc="Synthesizing Knowledge") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            future_to_batch_index = {
                executor.submit(
                    process_conversation_batch, batch, prompt_template, collection
                ): i
                for i, batch in enumerate(batches)
            }

            for future in concurrent.futures.as_completed(future_to_batch_index):
                batch_index = future_to_batch_index[future]
                try:
                    num_stored = future.result()
                    if num_stored > 0:
                        total_nuggets_stored += num_stored
                        last_item_in_batch = len(batches[batch_index]) - 1
                        last_processed_index = start_index + (batch_index * config.BATCH_SIZE) + last_item_in_batch
                        save_progress(last_processed_index)
                except Exception as e:
                    logging.error(
                        f"An error occurred while processing batch index {batch_index}: {e}",
                        exc_info=True,
                    )
                pbar.update(1)
                pbar.set_postfix({"Stored": f"{total_nuggets_stored}"})

    logging.info(
        f"\n--- Knowledge Synthesis Complete ---"
        f"Total nuggets stored in this run: {total_nuggets_stored}"
    )


if __name__ == "__main__":
    main()
