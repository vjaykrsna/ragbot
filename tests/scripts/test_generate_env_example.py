import ast
from pathlib import Path
from unittest.mock import mock_open, patch

from src.scripts.generate_env_example import (
    EnvVarVisitor,
    generate_env_example,
    scan_codebase_for_env_vars,
)


def test_env_var_visitor():
    """Test the EnvVarVisitor to ensure it finds environment variables."""
    source_code = """
import os

api_key = os.getenv("API_KEY", "default_value")
secret = os.environ.get("SECRET")
no_env_var = "just a string"
"""
    tree = ast.parse(source_code)
    visitor = EnvVarVisitor()
    visitor.visit(tree)

    assert "API_KEY" in visitor.env_vars
    assert visitor.env_vars["API_KEY"] == "default_value"
    assert "SECRET" in visitor.env_vars
    assert visitor.env_vars["SECRET"] == ""
    assert "NO_ENV_VAR" not in visitor.env_vars


@patch("os.walk")
@patch("builtins.open", new_callable=mock_open)
def test_scan_codebase_for_env_vars(mock_file, mock_walk):
    """Test scanning a directory for environment variables."""
    mock_walk.return_value = [
        ("/fake_dir", [], ["fake_module.py"]),
    ]
    mock_file.return_value.read.return_value = 'import os\nkey = os.getenv("SCAN_KEY")'

    env_vars = scan_codebase_for_env_vars("/fake_dir")

    assert "SCAN_KEY" in env_vars
    assert env_vars["SCAN_KEY"] == ""


@patch("src.scripts.generate_env_example.scan_codebase_for_env_vars")
@patch("builtins.open", new_callable=mock_open)
def test_generate_env_example(mock_file, mock_scan):
    """Test the generation of the .env.example file."""
    mock_scan.return_value = {
        "VAR1": "value1",
        "VAR2": "",
    }

    # Since the script uses Path.resolve(), we need to mock it
    with patch.object(Path, "resolve") as mock_resolve:
        # Make resolve() return a predictable path
        mock_resolve.return_value = Path("/fake_project_root/src/scripts/script.py")

        generate_env_example()

        # Check that .env.example was written correctly
        handle = mock_file()
        handle.write.assert_any_call("VAR1=value1\n")
        handle.write.assert_any_call("VAR2=\n")
        # Check that the manual section is included
        # Get all the calls to write()
        write_calls = handle.write.call_args_list
        # Flatten the list of calls into a single string
        written_content = "".join(call[0][0] for call in write_calls)
        # Check that the manual section is included
        assert "\n# --- LiteLLM Configuration ---\n" in written_content
