# ==============================================================================
# CENTRALIZED CONFIGURATION
# ==============================================================================
# This file contains all the configuration constants for the RAG Telegram Bot.
# By centralizing them here, we can ensure consistency and ease of maintenance.
# ==============================================================================

import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_IDS = [int(gid.strip()) for gid in os.getenv("GROUP_IDS", "").split(',') if gid]

# --- LiteLLM Proxy Configuration ---
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL")

# --- Model Configuration ---
# These model names are defined in the litellm_config.yaml file.
# The 'litellm_proxy/' prefix is used by the synthesis script.
SYNTHESIS_MODEL_NAME = "gemini-synthesis-model"
EMBEDDING_MODEL_NAME = "gemini-embedding-model"
SYNTHESIS_MODEL_PROXY = f"litellm_proxy/{SYNTHESIS_MODEL_NAME}"
EMBEDDING_MODEL_PROXY = f"litellm_proxy/{EMBEDDING_MODEL_NAME}"


# --- Knowledge Base & Vector DB Configuration ---
DB_PATH = "vector_database"
COLLECTION_NAME = "telegram_knowledge_base_v2"
PROMPT_FILE = "knowledge_synthesis_prompt.md"
PROCESSED_DATA_FILE = "processed_data/processed_conversations.json"
PROGRESS_FILE = "synthesis_progress.json"

# --- Knowledge Synthesis Script Configuration ---
MAX_WORKERS = 5  # Number of parallel threads for synthesis
REQUESTS_PER_MINUTE = 60  # Client-side rate limit for the synthesis script
