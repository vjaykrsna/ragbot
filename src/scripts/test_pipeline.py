import structlog

from src.core.app import initialize_app
from src.processing.pipeline import DataProcessingPipeline

_logger = structlog.get_logger(__name__)


def main():
    """
    Initializes the application and runs the data processing pipeline.

    This script serves as an integration test to ensure that all components
    are wired together correctly and the pipeline can be executed.
    """
    _logger.info("Initializing application for pipeline test...")
    app_context = initialize_app()

    _logger.info("Resolving data processing pipeline from container...")
    pipeline = app_context.container.resolve(DataProcessingPipeline)

    _logger.info("Running the data processing pipeline...")
    pipeline.run()

    _logger.info("Pipeline test completed successfully.")


if __name__ == "__main__":
    main()
