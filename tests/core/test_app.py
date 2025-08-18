from unittest.mock import MagicMock, patch

from src.core.app import AppContext, initialize_app


class TestAppContext:
    @patch("src.core.app.get_settings")
    def test_create(self, mock_get_settings):
        """Test the create method of AppContext."""
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings

        with patch("src.core.app.AppContext.__init__", return_value=None) as mock_init:
            app_context = AppContext.create()
            mock_init.assert_called_once_with(mock_settings)
            assert isinstance(app_context, AppContext)

    @patch("src.core.app.setup_logging")
    @patch("src.core.app.Database")
    @patch("chromadb.PersistentClient")
    def test_init(self, mock_chromadb, mock_database, mock_setup_logging):
        """Test the __init__ method of AppContext."""
        mock_settings = MagicMock()
        mock_settings.paths.db_path = "/fake/db/path"

        app_context = AppContext(mock_settings)

        mock_setup_logging.assert_called_once_with(mock_settings)
        mock_database.assert_called_once_with(mock_settings.paths)
        mock_chromadb.assert_called_once()
        assert app_context.settings == mock_settings


@patch("src.core.app.AppContext.create")
def test_initialize_app(mock_create):
    """Test the initialize_app function."""
    initialize_app()
    mock_create.assert_called_once()
