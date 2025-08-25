"""
Service interfaces for the application.

This module defines abstract base classes for key services used throughout
the application, enabling dependency injection and easier testing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from chromadb.api.models.Collection import Collection


class DataLoaderInterface(ABC):
    """Interface for data loading services."""

    @abstractmethod
    def load_processed_data(self) -> List[Dict[str, Any]]:
        """Load processed data from storage."""
        pass

    @abstractmethod
    def load_prompt_template(self) -> str:
        """Load the prompt template for nugget generation."""
        pass


class NuggetGeneratorInterface(ABC):
    """Interface for nugget generation services."""

    @abstractmethod
    def generate_nuggets_batch(
        self, conv_batch: List[Dict[str, Any]], prompt_template: str
    ) -> List[Dict[str, Any]]:
        """Generate knowledge nuggets from a batch of conversations."""
        pass


class NuggetEmbedderInterface(ABC):
    """Interface for nugget embedding services."""

    @abstractmethod
    def embed_nuggets_batch(
        self, nuggets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate embeddings for a batch of nuggets."""
        pass


class NuggetStorerInterface(ABC):
    """Interface for nugget storage services."""

    @abstractmethod
    def store_nuggets_batch(
        self, collection: Collection, nuggets: List[Dict[str, Any]]
    ) -> int:
        """Store a batch of nuggets in the database."""
        pass


class ConversationOptimizerInterface(ABC):
    """Interface for conversation optimization services."""

    @abstractmethod
    def optimize_conversations(
        self, conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Optimize a list of conversations."""
        pass


class ProgressTrackerInterface(ABC):
    """Interface for progress tracking services."""

    @abstractmethod
    def save_progress(self, last_processed_index: int) -> None:
        """Save the last processed index."""
        pass

    @abstractmethod
    def load_progress(self) -> int:
        """Load the last processed index."""
        pass

    @abstractmethod
    def load_processed_hashes(self) -> set:
        """Load the set of processed hashes."""
        pass

    @abstractmethod
    def save_processed_hashes(self, hashes: set) -> None:
        """Save the set of processed hashes."""
        pass


class FailedBatchHandlerInterface(ABC):
    """Interface for failed batch handling services."""

    @abstractmethod
    def save_failed_batch(
        self, conv_batch: List[Dict[str, Any]], error: str, response_text: str = ""
    ) -> None:
        """Save a failed batch for later retry."""
        pass


class DatabaseInterface(ABC):
    """Interface for database services."""

    @abstractmethod
    def get_all_messages(self):
        """Get all messages from the database."""
        pass

    @abstractmethod
    def insert_messages(self, messages: List[Dict[str, Any]]):
        """Insert messages into the database."""
        pass


class DatabaseClientInterface(ABC):
    """Interface for database client services."""

    @abstractmethod
    def get_or_create_collection(self, name: str) -> Collection:
        """Get or create a collection."""
        pass

    @abstractmethod
    def get_collection(self, name: str) -> Collection:
        """Get a collection."""
        pass
