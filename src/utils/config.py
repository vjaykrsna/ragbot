# ==============================================================================
# CENTRALIZED CONFIGURATION
# ==============================================================================
# This file contains all the configuration constants for the RAG Telegram Bot.
# By centralizing them here, we can ensure consistency and ease of maintenance.
# ==============================================================================

import os
from dotenv import load_dotenv
from typing import List


# --- Load environment variables ---
load_dotenv()


# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
_group_ids_raw = os.getenv("GROUP_IDS", "")
GROUP_IDS: List[int] = []
if _group_ids_raw:
    try:
        GROUP_IDS = [int(gid.strip()) for gid in _group_ids_raw.split(",") if gid.strip()]
    except ValueError:
        GROUP_IDS = []

SESSION_NAME: str = os.getenv("SESSION_NAME", "ragbot_session")
TELEGRAM_PHONE: str | None = os.getenv("TELEGRAM_PHONE")
TELEGRAM_PASSWORD: str | None = os.getenv("TELEGRAM_PASSWORD")


# --- LiteLLM Proxy Configuration ---
LITELLM_PROXY_URL: str | None = os.getenv("LITELLM_PROXY_URL")


# --- Model Configuration ---
# These model names are defined in the litellm_config.yaml file.
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


# --- Knowledge Base & Vector DB Configuration ---
COLLECTION_NAME = "telegram_knowledge_base_v2"
PROMPT_FILE = "docs/knowledge_synthesis_prompt.md"


# --- Knowledge Synthesis Script Configuration ---
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "90"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2"))


# --- RAG Pipeline Configuration ---
# Weights for re-ranking (should sum to 1.0)
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
CONVERSATION_TIME_THRESHOLD_SECONDS = int(os.getenv("CONVERSATION_TIME_THRESHOLD_SECONDS", "300"))
SESSION_WINDOW_SECONDS = int(os.getenv("SESSION_WINDOW_SECONDS", "3600"))
