"""
Service registration module.

This module registers all services with the DI container.
"""

from pyrate_limiter import Duration, Limiter, Rate

from src.core.config import AppSettings
from src.core.database import Database
from src.core.di.container import container
from src.core.di.interfaces import (
    ConversationOptimizerInterface,
    DatabaseClientInterface,
    DatabaseInterface,
    DataLoaderInterface,
    FailedBatchHandlerInterface,
    NuggetEmbedderInterface,
    NuggetGeneratorInterface,
    NuggetStorerInterface,
    ProgressTrackerInterface,
)
from src.synthesis.conversation_optimizer import ConversationOptimizer
from src.synthesis.data_loader import DataLoader
from src.synthesis.failed_batch_handler import FailedBatchHandler
from src.synthesis.nugget_embedder import NuggetEmbedder
from src.synthesis.nugget_generator import NuggetGenerator
from src.synthesis.nugget_store import NuggetStore
from src.synthesis.progress_tracker import ProgressTracker


def register_services(settings: AppSettings, db: Database, db_client) -> None:
    """
    Register all services with the DI container.

    Args:
        settings: The application settings
        db: The database instance
        db_client: The database client instance
    """
    # Register singleton instances
    container.register_singleton_instance(DatabaseInterface, db)
    container.register_singleton_instance(DatabaseClientInterface, db_client)

    # Register services as singletons
    container.register_singleton(DataLoaderInterface, DataLoader)
    container.register_singleton(ConversationOptimizerInterface, ConversationOptimizer)
    container.register_singleton(ProgressTrackerInterface, ProgressTracker)
    container.register_singleton(FailedBatchHandlerInterface, FailedBatchHandler)

    # Register transient services (these might need to be recreated)
    container.register_transient_factory(
        NuggetGeneratorInterface,
        lambda: NuggetGenerator(
            settings,
            Limiter(Rate(settings.synthesis.requests_per_minute, Duration.MINUTE)),
            container.resolve(ConversationOptimizerInterface),
        ),
    )
    container.register_transient_factory(
        NuggetEmbedderInterface,
        lambda: NuggetEmbedder(
            settings,
            Limiter(Rate(settings.synthesis.requests_per_minute, Duration.MINUTE)),
        ),
    )
    container.register_transient(NuggetStorerInterface, NuggetStore)

    # Register factory for DataLoader with dependencies
    container.register_transient_factory(
        DataLoaderInterface,
        lambda: DataLoader(settings, container.resolve(DatabaseInterface)),
    )

    # Register factory for ProgressTracker with settings
    container.register_transient_factory(
        ProgressTrackerInterface, lambda: ProgressTracker(settings)
    )

    # Register factory for FailedBatchHandler with settings
    container.register_transient_factory(
        FailedBatchHandlerInterface, lambda: FailedBatchHandler(settings)
    )
