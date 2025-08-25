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
    container.register_singleton_instance(DatabaseInterface, db)  # type: ignore[type-abstract]
    container.register_singleton_instance(DatabaseClientInterface, db_client)

    # Register services as singletons
    container.register_singleton(DataLoaderInterface, DataLoader)  # type: ignore[type-abstract]
    container.register_singleton(ConversationOptimizerInterface, ConversationOptimizer)  # type: ignore[type-abstract]
    container.register_singleton(ProgressTrackerInterface, ProgressTracker)  # type: ignore[type-abstract]
    container.register_singleton(FailedBatchHandlerInterface, FailedBatchHandler)  # type: ignore[type-abstract]

    # Register transient services (these might need to be recreated)
    container.register_transient_factory(
        NuggetGeneratorInterface,  # type: ignore[type-abstract]
        lambda: NuggetGenerator(
            settings,
            Limiter(Rate(settings.synthesis.requests_per_minute, Duration.MINUTE)),
            container.resolve(ConversationOptimizerInterface),  # type: ignore[type-abstract]
        ),
    )
    container.register_transient_factory(
        NuggetEmbedderInterface,  # type: ignore[type-abstract]
        lambda: NuggetEmbedder(
            settings,
            Limiter(Rate(settings.synthesis.requests_per_minute, Duration.MINUTE)),
        ),
    )
    container.register_transient(NuggetStorerInterface, NuggetStore)  # type: ignore[type-abstract]

    # Register factory for DataLoader with dependencies
    container.register_transient_factory(
        DataLoaderInterface,  # type: ignore[type-abstract]
        lambda: DataLoader(settings, container.resolve(DatabaseInterface)),  # type: ignore[type-abstract]
    )

    # Register factory for ProgressTracker with settings
    container.register_transient_factory(
        ProgressTrackerInterface,  # type: ignore[type-abstract]
        lambda: ProgressTracker(settings),
    )

    # Register factory for FailedBatchHandler with settings
    container.register_transient_factory(
        FailedBatchHandlerInterface,  # type: ignore[type-abstract]
        lambda: FailedBatchHandler(settings),
    )
