import punq

from src.config.settings import AppSettings
from src.processing.anonymizer import Anonymizer
from src.processing.conversation_builder import ConversationBuilder
from src.processing.data_source import DataSource
from src.processing.external_sorter import ExternalSorter
from src.processing.pipeline import DataProcessingPipeline


def create_container(settings: AppSettings) -> punq.Container:
    """
    Creates and configures the dependency injection container.
    """
    container = punq.Container()

    # Register settings
    container.register(AppSettings, instance=settings)

    # Register pipeline components
    container.register(DataSource, factory=lambda: DataSource(settings.paths))
    container.register(ExternalSorter)
    container.register(Anonymizer, factory=lambda: Anonymizer(settings.paths))
    container.register(
        ConversationBuilder, factory=lambda: ConversationBuilder(settings.conversation)
    )
    container.register(DataProcessingPipeline)

    return container
