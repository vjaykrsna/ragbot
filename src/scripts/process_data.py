"""
Entrypoint for the data processing pipeline.

This script initializes the application environment and runs the main data
processing pipeline to convert raw message data into structured conversations.
"""

from src.core.app import initialize_app
from src.processing.pipeline import DataProcessingPipeline


def main():
    """
    Initializes the application and runs the data processing pipeline.
    """
    app_context = initialize_app()
    pipeline = app_context.container.resolve(DataProcessingPipeline)
    pipeline.run()


if __name__ == "__main__":
    main()
