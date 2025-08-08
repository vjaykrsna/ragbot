import os
import json
import chromadb
import litellm
import logging
import uuid
import concurrent.futures
import time
from tqdm import tqdm
from pyrate_limiter import Duration, Rate, Limiter, BucketFullException
import config
from typing import Any, Dict, List, Optional, Tuple
from litellm import (
    APIError,
    RateLimitError,
    APIConnectionError,
    ServiceUnavailableError,
    Timeout,
)
import chromadb.errors
from chromadb.api.models.Collection import Collection

# ==============================================================================
# 1. SETUP
# ==============================================================================

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[logging.FileHandler("knowledge_synthesis.log"), logging.StreamHandler()],
)

# --- LiteLLM Setup ---
# LiteLLM will automatically pick up keys from the environment via the config
litellm.api_base = config.LITELLM_PROXY_URL
# Set a dummy key for the proxy itself, as it's required by default
litellm.api_key = "test-key"

# --- Rate Limiter Setup ---
# Define a rate of 50 requests per minute.
# This will be shared across all worker threads.
rate = Rate(config.REQUESTS_PER_MINUTE, Duration.MINUTE)
limiter = Limiter(rate, max_delay=60000)  # Allow delaying up to 60 seconds


# ==============================================================================
# 2. DATABASE & PROGRESS MANAGEMENT
# ==============================================================================


def setup_database() -> Collection:
    """Initializes the ChromaDB client and creates a collection."""
    logging.info(f"Setting up vector database at: {config.DB_PATH}")
    client = chromadb.PersistentClient(path=config.DB_PATH)
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)
    logging.info(f"Database collection '{COLLECTION_NAME}' is ready.")
    return collection


def save_progress(last_processed_index: int) -> None:
    """Saves the index of the last successfully processed conversation."""
    with open(config.PROGRESS_FILE, "w") as f:
        json.dump({"last_processed_index": last_processed_index}, f)


def load_progress() -> int:
    """Loads the index of the last successfully processed conversation."""
    try:
        with open(config.PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_processed_index", -1)
    except (FileNotFoundError, json.JSONDecodeError):
        return -1


# ==============================================================================
# 3. MAIN ORCHESTRATION
# ==============================================================================


def main() -> None:
    """
    Main function to orchestrate the knowledge base population.

    This function initializes the database, loads the processed conversation data
    and the prompt template, and then starts the synthesis and population process.
    """
    logging.info("🚀 Starting Knowledge Base v2 Synthesis")

    collection = setup_database()
    conversations = load_processed_data()
    prompt_template = load_prompt_template()
    if not conversations or not prompt_template:
        return

    synthesize_and_populate(conversations, prompt_template, collection)

    logging.info("✅ Knowledge base synthesis complete.")


# ==============================================================================
# 4. DATA LOADING & PROCESSING
# ==============================================================================


def load_processed_data() -> List[Dict[str, Any]]:
    """Loads the processed conversation threads from the JSON file."""
    try:
        with open(config.PROCESSED_DATA_FILE, "r", encoding="utf-8") as f:
            logging.info(f"Loading processed data from {config.PROCESSED_DATA_FILE}")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load processed data: {e}")
        return []


def load_prompt_template() -> Optional[str]:
    """Loads the master prompt template."""
    try:
        with open(config.PROMPT_FILE, "r", encoding="utf-8") as f:
            logging.info(f"Loading prompt template from {config.PROMPT_FILE}")
            return f.read()
    except FileNotFoundError as e:
        logging.error(f"Could not load prompt template: {e}")
        return None


# Create a decorator from the limiter instance
limiter_decorator = limiter.as_decorator()


def rate_limit_mapping(args: Tuple[int, Dict[str, Any], str, Collection]) -> Tuple[str, int]:
    """
    Mapping function for the rate limiter decorator.
    Ensures all calls from all threads share the same rate limit bucket.
    """
    return "synthesis-worker", 1


@limiter_decorator(rate_limit_mapping)
def generate_nugget(conv: Dict[str, Any], prompt_template: str) -> Optional[Dict[str, Any]]:
    """
    Generates a knowledge nugget from a single conversation using a LiteLLM model.

    Args:
        conv (Dict[str, Any]): The conversation data.
        prompt_template (str): The prompt template to use for generation.

    Returns:
        Optional[Dict[str, Any]]: The generated knowledge nugget, or None if an error occurs.
    """
    formatted_conv = json.dumps(conv, indent=2)
    final_prompt = (
        f"{prompt_template}\n\n**Input Conversation:**\n```json\n{formatted_conv}\n```"
    )

    max_retries = 3
    backoff_factor = 2

    for attempt in range(max_retries):
        try:
            response = litellm.completion(
                model=config.SYNTHESIS_MODEL_PROXY,
                messages=[{"role": "user", "content": final_prompt}],
                stream=False,
            )
            cleaned_response = (
                response.choices[0]
                .message.content.strip()
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )
            return json.loads(cleaned_response) if cleaned_response else None
        except (
            RateLimitError,
            APIConnectionError,
            ServiceUnavailableError,
            Timeout,
        ) as e:
            if attempt < max_retries - 1:
                sleep_time = backoff_factor**attempt
                logging.warning(
                    f"API Error (retriable), attempt {attempt+1}/{max_retries}. Retrying in {sleep_time}s. Error: {e}"
                )
                time.sleep(sleep_time)
            else:
                logging.error(
                    f"API Error failed after {max_retries} attempts. Error: {e}"
                )
                raise


def embed_nugget(nugget: Dict[str, Any]) -> Optional[List[float]]:
    """
    Generates an embedding for the knowledge nugget's summary.

    Args:
        nugget (Dict[str, Any]): The knowledge nugget.

    Returns:
        Optional[List[float]]: The generated embedding, or None if an error occurs.
    """
    document_to_embed = nugget.get("topic_summary")
    if not document_to_embed:
        return None

    embedding_response = litellm.embedding(
        model=config.EMBEDDING_MODEL_PROXY, input=[document_to_embed]
    )
    return embedding_response["data"][0]["embedding"]


def store_nugget(collection: Collection, nugget: Dict[str, Any], embedding: List[float]) -> None:
    """
    Stores the knowledge nugget and its embedding in the ChromaDB collection.

    Args:
        collection (Collection): The ChromaDB collection.
        nugget (Dict[str, Any]): The knowledge nugget.
        embedding (List[float]): The embedding of the nugget's summary.
    """
    document_to_embed = nugget.get("topic_summary")
    metadata = nugget.copy()
    metadata.pop("topic_summary", None)

    for key in ["keywords", "source_message_ids", "user_ids_involved"]:
        if key in metadata and isinstance(metadata[key], list):
            metadata[key] = json.dumps(metadata[key])

    collection.add(
        embeddings=[embedding],
        documents=[document_to_embed],
        metadatas=[metadata],
        ids=[nugget.get("nugget_id", str(uuid.uuid4()))],
    )


@limiter_decorator(rate_limit_mapping)
def process_single_conversation(args: Tuple[int, Dict[str, Any], str, Collection]) -> Optional[int]:
    """Processes a single conversation thread. Designed to be called by a thread pool."""
    i, conv, prompt_template, collection = args

    try:
        nugget = generate_nugget(conv, prompt_template)
        if not nugget or not isinstance(nugget, dict):
            return None

        embedding = embed_nugget(nugget)
        if not embedding:
            logging.warning(
                f"Nugget for conversation {i+1} missing 'topic_summary'. Skipping."
            )
            return None

        store_nugget(collection, nugget, embedding)

        return i  # Return the index on success

    except json.JSONDecodeError:
        logging.warning(
            f"Could not decode JSON response for conversation {i+1}. Skipping."
        )
    except BucketFullException as err:
        logging.warning(
            f"Rate limit bucket is full, and delay exceeded max_delay. Details: {err}"
        )
    except (RateLimitError, APIConnectionError, ServiceUnavailableError, Timeout) as e:
        logging.error(f"API Error (retriable) for conversation {i+1}: {e}")
    except APIError as e:
        logging.error(f"API Error (non-retriable) for conversation {i+1}: {e}")
    except chromadb.errors.ChromaError as e:
        logging.error(f"Database error for conversation {i+1}: {e}")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while processing conversation {i+1}: {e}"
        )

    return None


def synthesize_and_populate(
    conversations: List[Dict[str, Any]], prompt_template: str, collection: Collection
) -> None:
    """
    Processes conversations concurrently and populates the ChromaDB collection.

    This function manages the concurrent processing of conversation threads using a
    ThreadPoolExecutor. It also handles resuming from the last saved progress point
    and saves progress upon completion.

    Args:
        conversations (List[Dict[str, Any]]): A list of conversation data to process.
        prompt_template (str): The master prompt template for nugget generation.
        collection (Collection): The ChromaDB collection to populate.
    """
    start_index = load_progress() + 1
    if start_index > 0:
        logging.info(f"Resuming from conversation index {start_index}.")

    conversations_to_process = conversations[start_index:]
    logging.info(
        f"Starting to process {len(conversations_to_process)} conversations with up to {config.MAX_WORKERS} workers..."
    )

    total_nuggets = 0

    tasks = [
        (i, conv, prompt_template, collection)
        for i, conv in enumerate(conversations_to_process, start=start_index)
    ]

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=config.MAX_WORKERS
    ) as executor:
        # Using tqdm for a progress bar
        results = list(
            tqdm(executor.map(process_single_conversation, tasks), total=len(tasks))
        )

    last_processed_index = start_index - 1
    for result in results:
        if result is not None:
            total_nuggets += 1
            last_processed_index = max(last_processed_index, result)

    save_progress(last_processed_index)
    logging.info(
        f"Successfully synthesized and stored a total of {total_nuggets} Knowledge Nuggets."
    )


if __name__ == "__main__":
    main()
