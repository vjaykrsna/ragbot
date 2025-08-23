from unittest.mock import patch

from src.cli import run_cli


@patch("src.cli.extract_history.main")
def test_extract_command(mock_extract_main):
    """Test that the 'extract' command calls the correct function."""
    run_cli(["extract"])
    mock_extract_main.assert_called_once()


@patch("src.cli.synthesize_knowledge.main")
def test_synthesize_command(mock_synthesize_main):
    """Test that the 'synthesize' command calls the correct function."""
    run_cli(["synthesize"])
    mock_synthesize_main.assert_called_once()


@patch("src.cli.asyncio.run")
@patch("src.cli.extract_history.main")
def test_async_function_call(mock_extract_main, mock_asyncio_run):
    """Test that asyncio.run is used for async functions."""
    # In Python 3.8+, iscoroutinefunction is used directly.
    # For broader compatibility, we can patch inspect.iscoroutinefunction
    with patch("src.cli.inspect.iscoroutinefunction", return_value=True):
        run_cli(["extract"])

    mock_asyncio_run.assert_called_once()
    # We can't easily assert the argument to run, as it's a coroutine object
    # but we can confirm it was called.
