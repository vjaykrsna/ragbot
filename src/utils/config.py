# =============== CENTRALIZED CONFIGURATION ================

import os
from typing import List

from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()


# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
_group_ids_raw = os.getenv("GROUP_IDS", "")
GROUP_IDS: List[int] = []
if _group_ids_raw:
    try:
        GROUP_IDS = [
            int(gid.strip()) for gid in _group_ids_raw.split(",") if gid.strip()
        ]
    except ValueError:
        GROUP_IDS = []

SESSION_NAME: str = os.getenv("SESSION_NAME", "ragbot_session")
TELEGRAM_PHONE: str | None = os.getenv("TELEGRAM_PHONE")
TELEGRAM_PASSWORD: str | None = os.getenv("TELEGRAM_PASSWORD")


# --- LiteLLM Proxy Configuration ---
LITELLM_PROXY_URL: str | None = os.getenv("LITELLM_PROXY_URL")
# Toggle whether to enable small on-disk local caches for completions/embeddings.
USE_LOCAL_FILE_CACHE: bool = os.getenv("USE_LOCAL_FILE_CACHE", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Optional: a fallback API key to use when no proxy is configured.
FALLBACK_LITELLM_API_KEY: str | None = os.getenv("LITELLM_API_KEY")


# --- Model Configuration --- These model names are defined in the litellm_config.
SYNTHESIS_MODEL_NAME = "gemini-synthesis-model"
EMBEDDING_MODEL_NAME = "gemini-embedding-model"
SYNTHESIS_MODEL_PROXY = f"litellm_proxy/{SYNTHESIS_MODEL_NAME}"
EMBEDDING_MODEL_PROXY = f"litellm_proxy/{EMBEDDING_MODEL_NAME}"


# --- Data & File Paths ---
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed")
# Path used by chromadb.PersistentClient in code
DB_PATH = os.path.join(os.getcwd(), "knowledge_base")


# --- File Names ---
PROCESSED_CONVERSATIONS_FILE = "processed_conversations.json"
USER_MAP_FILE = "user_map.json"
SYNTHESIS_PROGRESS_FILE = "synthesis_progress.json"
TRACKING_FILE = "last_msg_ids.json"
FAILED_BATCHES_FILE = "failed_batches.jsonl"
PROCESSED_HASHES_FILE = "processed_hashes.json"


# --- Knowledge Base & Vector DB Configuration ---
COLLECTION_NAME = "telegram_knowledge_base_v2"
PROMPT_FILE = "docs/knowledge_synthesis_prompt.md"


# --- Knowledge Synthesis Script Configuration ---
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "90"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2"))


# --- RAG Pipeline Configuration --- Weights for re-ranking (should sum to 1.0)
SEMANTIC_SCORE_WEIGHT = float(os.getenv("SEMANTIC_SCORE_WEIGHT", "0.5"))
RECENCY_SCORE_WEIGHT = float(os.getenv("RECENCY_SCORE_WEIGHT", "0.3"))
STATUS_SCORE_WEIGHT = float(os.getenv("STATUS_SCORE_WEIGHT", "0.2"))


# Status weights for re-ranking
STATUS_WEIGHTS = {
    "FACT": 1.5,
    "COMMUNITY_OPINION": 1.0,
    "SPECULATION": 0.5,
    "DEFAULT": 0.1,
}


# --- Conversation Grouping ---
CONVERSATION_TIME_THRESHOLD_SECONDS = int(
    os.getenv("CONVERSATION_TIME_THRESHOLD_SECONDS", "300")
)
SESSION_WINDOW_SECONDS = int(os.getenv("SESSION_WINDOW_SECONDS", "3600"))


def initialize_litellm_client_stub():
    """A lightweight initializer kept in config for backward compatibility.

    This sets up proxy/base URL and provides a fallback API key only when a
    proxy is not configured. It intentionally does not perform rotation.
    Projects that need advanced rotation should implement a dedicated client
    wrapper.
    """
# Delayed import to avoid import cycles
    try:
        import logging
        import os as _os

        import litellm

        logger = logging.getLogger(__name__)

        if LITELLM_PROXY_URL:
            litellm.api_base = LITELLM_PROXY_URL
            logger.info("Litellm initialized to use proxy at %s", LITELLM_PROXY_URL)
        else:
            key = FALLBACK_LITELLM_API_KEY or _os.getenv("LITELLM_API_KEY", "")
            if key:
                litellm.api_key = key
                logger.info(
                    "Litellm initialized with fallback api key from env (no proxy configured)"
                )
            else:
                logger.warning(
                    "No LITELLM_PROXY_URL or LITELLM_API_KEY configured; litellm calls may fail at runtime"
                )
    except Exception:
# best-effort only; caller modules should handle missing config at runtime
        pass
