import os
import json
import chromadb
import litellm
import logging
import uuid
import concurrent.futures
from tqdm import tqdm
from pyrate_limiter import Duration, Rate, Limiter, BucketFullException
import config

# ==============================================================================
# 1. SETUP
# ==============================================================================

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("knowledge_synthesis.log"),
        logging.StreamHandler()
    ]
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
limiter = Limiter(rate, max_delay=60000) # Allow delaying up to 60 seconds


# ==============================================================================
# 2. DATABASE & PROGRESS MANAGEMENT
# ==============================================================================

def setup_database():
    """Initializes the ChromaDB client and creates a collection."""
    logging.info(f"Setting up vector database at: {config.DB_PATH}")
    client = chromadb.PersistentClient(path=config.DB_PATH)
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)
    logging.info(f"Database collection '{COLLECTION_NAME}' is ready.")
    return collection

def save_progress(last_processed_index):
    """Saves the index of the last successfully processed conversation."""
    with open(config.PROGRESS_FILE, "w") as f:
        json.dump({"last_processed_index": last_processed_index}, f)

def load_progress():
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

def main():
    """Main function to orchestrate the knowledge base population."""
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

def load_processed_data():
    """Loads the processed conversation threads from the JSON file."""
    try:
        with open(config.PROCESSED_DATA_FILE, "r", encoding="utf-8") as f:
            logging.info(f"Loading processed data from {config.PROCESSED_DATA_FILE}")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load processed data: {e}")
        return []

def load_prompt_template():
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

def rate_limit_mapping(args):
    """
    Mapping function for the rate limiter decorator.
    Ensures all calls from all threads share the same rate limit bucket.
    """
    return "synthesis-worker", 1

@limiter_decorator(rate_limit_mapping)
def process_single_conversation(args):
    """Processes a single conversation thread. Designed to be called by a thread pool."""
    i, conv, prompt_template, collection = args
    
    try:
        formatted_conv = json.dumps(conv, indent=2)
        final_prompt = f"{prompt_template}\n\n**Input Conversation:**\n```json\n{formatted_conv}\n```"

        response = litellm.completion(
            model=config.SYNTHESIS_MODEL_PROXY,
            messages=[{"role": "user", "content": final_prompt}],
            stream=False
        )
        
        cleaned_response = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        if not cleaned_response:
            return None

        nugget_data = json.loads(cleaned_response)

        if not nugget_data or not isinstance(nugget_data, dict):
            return None

        nugget = nugget_data
        
        document_to_embed = nugget.get("topic_summary")
        if not document_to_embed:
            logging.warning(f"Nugget for conversation {i+1} missing 'topic_summary'. Skipping.")
            return None

        embedding_response = litellm.embedding(
            model=config.EMBEDDING_MODEL_PROXY,
            input=[document_to_embed]
        )
        
        metadata = nugget.copy()
        metadata.pop("topic_summary", None)

        for key in ["keywords", "source_message_ids", "user_ids_involved"]:
            if key in metadata and isinstance(metadata[key], list):
                metadata[key] = json.dumps(metadata[key])

        collection.add(
            embeddings=[embedding_response['data'][0]['embedding']],
            documents=[document_to_embed],
            metadatas=[metadata],
            ids=[nugget.get("nugget_id", str(uuid.uuid4()))]
        )
        
        return i # Return the index on success

    except json.JSONDecodeError:
        logging.warning(f"Could not decode JSON response for conversation {i+1}. Skipping.")
    except BucketFullException as err:
        # This might still be raised if the delay exceeds max_delay
        logging.warning(f"Rate limit bucket is full, and delay exceeded max_delay. Details: {err}")
    except Exception as e:
        logging.error(f"An error occurred while processing conversation {i+1}: {e}")
    
    return None


def synthesize_and_populate(conversations, prompt_template, collection):
    """Processes conversations concurrently and populates the DB."""
    start_index = load_progress() + 1
    if start_index > 0:
        logging.info(f"Resuming from conversation index {start_index}.")
    
    conversations_to_process = conversations[start_index:]
    logging.info(f"Starting to process {len(conversations_to_process)} conversations with up to {config.MAX_WORKERS} workers...")
    
    total_nuggets = 0
    
    tasks = [(i, conv, prompt_template, collection) for i, conv in enumerate(conversations_to_process, start=start_index)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        # Using tqdm for a progress bar
        results = list(tqdm(executor.map(process_single_conversation, tasks), total=len(tasks)))

    last_processed_index = start_index -1
    for result in results:
        if result is not None:
            total_nuggets += 1
            last_processed_index = max(last_processed_index, result)
    
    save_progress(last_processed_index)
    logging.info(f"Successfully synthesized and stored a total of {total_nuggets} Knowledge Nuggets.")


if __name__ == "__main__":
    main()
