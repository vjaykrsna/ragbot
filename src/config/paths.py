import os
from pydantic import BaseModel

class PathSettings(BaseModel):
    """Path and filename settings."""
    data_dir: str = "data"
    raw_data_dir: str = os.path.join("data", "raw")
    processed_data_dir: str = os.path.join("data", "processed")
    db_path: str = os.path.join(os.getcwd(), "knowledge_base")
    log_dir: str = "logs"

    processed_conversations_file: str = "processed_conversations.json"
    user_map_file: str = "user_map.json"
    synthesis_progress_file: str = "synthesis_progress.json"
    tracking_file: str = os.path.join("data", "last_msg_ids.json")
    failed_batches_file: str = os.path.join("data", "failed_batches.jsonl")
    processed_hashes_file: str = "processed_hashes.json"
    prompt_file: str = "docs/knowledge_synthesis_prompt.md"