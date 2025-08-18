import argparse
from unittest.mock import MagicMock, patch

from src.scripts.inspect_db import (
    delete_collection,
    display_nugget_details,
    inspect_database,
)


@patch("src.scripts.inspect_db.Console")
def test_display_nugget_details(mock_console):
    """Test the display of nugget details."""
    nuggets = {
        "metadatas": [
            {"timestamp": "2023-01-01T00:00:00Z", "topic": "Topic 1", "status": "new"},
            {"timestamp": "2023-01-02T00:00:00Z", "topic": "Topic 2", "status": "old"},
        ],
        "documents": ["Summary 1", "Summary 2"],
    }
    display_nugget_details(nuggets)
    mock_console.return_value.print.assert_called()


@patch("src.scripts.inspect_db.chromadb.PersistentClient")
@patch("src.scripts.inspect_db.display_nugget_details")
@patch("src.scripts.inspect_db.get_app_context")
def test_inspect_database(mock_get_app_context, mock_display, mock_client):
    """Test the database inspection function."""
    mock_app_context = MagicMock()
    mock_app_context.settings.paths.db_path = "/fake/db"
    mock_app_context.settings.rag.collection_name = "fake_collection"
    mock_get_app_context.return_value = mock_app_context

    mock_collection = MagicMock()
    mock_collection.count.return_value = 2
    mock_collection.get.return_value = "some_nuggets"
    mock_client.return_value.get_collection.return_value = mock_collection

    inspect_database(limit=5)

    mock_client.assert_called_with(path="/fake/db")
    mock_display.assert_called_with("some_nuggets")


@patch("src.scripts.inspect_db.chromadb.PersistentClient")
@patch("src.scripts.inspect_db.get_app_context")
def test_delete_collection(mock_get_app_context, mock_client):
    """Test the collection deletion function."""
    mock_app_context = MagicMock()
    mock_app_context.settings.paths.db_path = "/fake/db"
    mock_get_app_context.return_value = mock_app_context

    mock_client_instance = mock_client.return_value
    delete_collection("test_collection")
    mock_client_instance.delete_collection.assert_called_with(name="test_collection")


@patch("argparse.ArgumentParser.parse_args")
@patch("src.scripts.inspect_db.delete_collection")
@patch("builtins.input", return_value="y")
def test_main_delete(mock_input, mock_delete, mock_parse_args):
    """Test the main function with the --delete argument."""
    mock_parse_args.return_value = argparse.Namespace(delete="test_collection", limit=5)
    with patch("src.scripts.inspect_db.__name__", "__main__"):
        from src.scripts import inspect_db

        inspect_db.delete_collection("test_collection")
        mock_delete.assert_called_with("test_collection")

@patch("argparse.ArgumentParser.parse_args")
@patch("src.scripts.inspect_db.inspect_database")
def test_main_inspect(mock_inspect, mock_parse_args):
    """Test the main function without the --delete argument."""
    mock_parse_args.return_value = argparse.Namespace(delete=None, limit=10)
    with patch("src.scripts.inspect_db.__name__", "__main__"):
        from src.scripts import inspect_db

        inspect_db.inspect_database(10)
        mock_inspect.assert_called_with(10)
