import os
from dataclasses import dataclass, field
from functools import lru_cache


@lru_cache(maxsize=1)
def get_project_root() -> str:
    """Returns the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass
class PathSettings:
    """
    Path and filename settings.
    All paths are absolute and constructed from a few base directories.
    """

    # Base Directories
    root_dir: str = field(default_factory=get_project_root)
    data_dir: str = field(init=False)
    log_dir: str = field(init=False)
    docs_dir: str = field(init=False)

    # Computed Paths
    raw_data_dir: str = field(init=False)
    processed_data_dir: str = field(init=False)
    db_dir: str = field(init=False)
    processed_conversations_file: str = field(init=False)
    user_map_file: str = field(init=False)
    synthesis_progress_file: str = field(init=False)
    tracking_file: str = field(init=False)
    failed_batches_file: str = field(init=False)
    processed_hashes_file: str = field(init=False)
    prompt_file: str = field(init=False)

    def __post_init__(self):
        self.data_dir = os.path.join(self.root_dir, "data")
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.docs_dir = os.path.join(self.root_dir, "docs")
        self.raw_data_dir = os.path.join(self.data_dir, "raw")
        self.processed_data_dir = os.path.join(self.data_dir, "processed")
        self.db_dir = os.path.join(self.data_dir, "knowledge_base")
        self.processed_conversations_file = os.path.join(
            self.processed_data_dir, "processed_conversations.json"
        )
        self.user_map_file = os.path.join(self.processed_data_dir, "user_map.json")
        self.synthesis_progress_file = os.path.join(
            self.processed_data_dir, "synthesis_progress.json"
        )
        self.tracking_file = os.path.join(self.data_dir, "last_msg_ids.json")
        self.failed_batches_file = os.path.join(self.data_dir, "failed_batches.jsonl")
        self.processed_hashes_file = os.path.join(
            self.processed_data_dir, "processed_hashes.json"
        )
        self.prompt_file = os.path.join(self.docs_dir, "knowledge_synthesis_prompt.md")
