"""
Entrypoint for the data processing pipeline.

This script initializes the application environment and runs the main data
processing pipeline to convert raw message data into structured conversations.
"""

from src.core.app import initialize_app
from src.processing.anonymizer import Anonymizer
from src.processing.conversation_builder import ConversationBuilder
from src.processing.data_source import DataSource
from src.processing.external_sorter import ExternalSorter
from src.processing.pipeline import DataProcessingPipeline


def main():
    """
    Initializes the application and runs the data processing pipeline.
    """
    app_context = initialize_app()
    settings = app_context.settings

    # Manually wire dependencies
    data_source = DataSource(app_context.db)
    sorter = ExternalSorter()
    anonymizer = Anonymizer(settings.paths)
    conv_builder = ConversationBuilder(settings.conversation)

    pipeline = DataProcessingPipeline(
        settings=settings,
        data_source=data_source,
        sorter=sorter,
        anonymizer=anonymizer,
        conv_builder=conv_builder,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
