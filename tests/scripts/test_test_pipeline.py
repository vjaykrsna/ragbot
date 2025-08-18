import unittest
from unittest.mock import MagicMock, patch

from src.scripts.test_pipeline import main


class TestTestPipelineScript(unittest.TestCase):
    @patch("src.scripts.test_pipeline.initialize_app")
    @patch("src.scripts.test_pipeline.DataProcessingPipeline")
    def test_main(self, mock_pipeline, mock_initialize_app):
        """
        Test that the main function correctly initializes the app and runs the pipeline.
        """
        # Arrange
        mock_context = MagicMock()
        mock_initialize_app.return_value = mock_context
        mock_pipeline_instance = MagicMock()
        mock_context.container.resolve.return_value = mock_pipeline_instance

        # Act
        main()

        # Assert
        mock_initialize_app.assert_called_once()
        mock_context.container.resolve.assert_called_once_with(mock_pipeline)
        mock_pipeline_instance.run.assert_called_once()
