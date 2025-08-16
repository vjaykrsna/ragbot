import os
from functools import lru_cache

from pydantic import BaseModel, computed_field


@lru_cache(maxsize=1)
def get_project_root() -> str:
    """Returns the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class PathSettings(BaseModel):
    """
    Path and filename settings.
    All paths are absolute and constructed from a few base directories.
    """

    # Base Directories
    # These can be overridden by environment variables if needed
    root_dir: str = get_project_root()
    data_dir: str = os.path.join(get_project_root(), "data")
    log_dir: str = os.path.join(get_project_root(), "logs")
    docs_dir: str = os.path.join(get_project_root(), "docs")

    # Computed Paths (read-only properties)
    @computed_field
    @property
    def raw_data_dir(self) -> str:
        return os.path.join(self.data_dir, "raw")

    @computed_field
    @property
    def processed_data_dir(self) -> str:
        return os.path.join(self.data_dir, "processed")

    @computed_field
    @property
    def db_path(self) -> str:
        return os.path.join(self.root_dir, "knowledge_base")

    @computed_field
    @property
    def processed_conversations_file(self) -> str:
        return os.path.join(self.processed_data_dir, "processed_conversations.json")

    @computed_field
    @property
    def user_map_file(self) -> str:
        return os.path.join(self.processed_data_dir, "user_map.json")

    @computed_field
    @property
    def synthesis_progress_file(self) -> str:
        return os.path.join(self.processed_data_dir, "synthesis_progress.json")

    @computed_field
    @property
    def tracking_file(self) -> str:
        return os.path.join(self.data_dir, "last_msg_ids.json")

    @computed_field
    @property
    def failed_batches_file(self) -> str:
        return os.path.join(self.data_dir, "failed_batches.jsonl")

    @computed_field
    @property
    def processed_hashes_file(self) -> str:
        return os.path.join(self.processed_data_dir, "processed_hashes.json")

    @computed_field
    @property
    def prompt_file(self) -> str:
        return os.path.join(self.docs_dir, "knowledge_synthesis_prompt.md")
