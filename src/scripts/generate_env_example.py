"""
This script generates a .env.example file by statically analyzing the entire
codebase for environment variable usage.

It walks through all Python files in the 'src' directory, parses them into an
Abstract Syntax Tree (AST), and identifies all calls to `os.getenv()` and
`os.environ.get()`. It extracts the variable names and their default values.

This approach ensures that the .env.example file stays up-to-date with the
actual environment variables used in the code.

Additionally, it maintains a small list of variables for third-party libraries
that may not be explicitly accessed via `os.getenv` in our codebase.
"""

import ast
import os
from pathlib import Path
from typing import Dict

# --- Configuration ---
SRC_DIRECTORY = "src"
THIRD_PARTY_VARS = {
    # This section is for variables that may not be found by the AST scanner,
    # typically because they are used by third-party libraries called via exec
    # or not directly accessed with os.getenv in our code.
}

# --- Manual Section ---
# This content will be appended to the end of the .env.example file.
# It's used for complex variables that require detailed explanations and examples.
MANUAL_ENV_SECTION = """
# --- LiteLLM Configuration ---
# The entire LiteLLM configuration, including the model list for load balancing,
# is now defined in a single JSON object.
# IMPORTANT: This must be a single line of valid JSON.
# You will need to define your GEMINI_API_KEY_1 through GEMINI_API_KEY_21 as
# separate environment variables for LiteLLM to pick them up.
# You also need to define REDIS_HOST, REDIS_PORT, and REDIS_PASSWORD if you are using cache.

LITELLM_CONFIG_JSON={"model_list": [{"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_1"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_2"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_3"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_4"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_5"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_6"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_7"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_8"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_9"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_10"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_11"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_12"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_13"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_14"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_15"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_16"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_17"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_18"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_19"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_20"}}, {"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "os.environ/GEMINI_API_KEY_21"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_1"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_2"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_3"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_4"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_5"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_6"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_7"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_8"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_9"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_10"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_11"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_12"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_13"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_14"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_15"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_16"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_17"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_18"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_19"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_20"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "os.environ/GEMINI_API_KEY_21"}}], "router_settings": {"routing_strategy": "usage-based-routing-v2", "cache_responses": true, "cache_kwargs": {"type": "redis", "host": "os.environ/REDIS_HOST", "port": "os.environ/REDIS_PORT", "password": "os.environ/REDIS_PASSWORD", "ttl": 3600}}, "litellm_settings": {"drop_params": true, "turn_off_message_logging": true, "set_verbose": false}}

# You will also need to set the API keys and any Redis credentials in your environment:
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=
GEMINI_API_KEY_5=
GEMINI_API_KEY_6=
GEMINI_API_KEY_7=
GEMINI_API_KEY_8=
GEMINI_API_KEY_9=
GEMINI_API_KEY_10=
GEMINI_API_KEY_11=
GEMINI_API_KEY_12=
GEMINI_API_KEY_13=
GEMINI_API_KEY_14=
GEMINI_API_KEY_15=
GEMINI_API_KEY_16=
GEMINI_API_KEY_17=
GEMINI_API_KEY_18=
GEMINI_API_KEY_19=
GEMINI_API_KEY_20=
GEMINI_API_KEY_21=

REDIS_HOST=
REDIS_PORT=6379
REDIS_PASSWORD=
"""


class EnvVarVisitor(ast.NodeVisitor):
    """AST visitor to find environment variable calls."""

    def __init__(self) -> None:
        self.env_vars: Dict[str, str] = {}

    def visit_Call(self, node):
        # Look for os.getenv("VAR", "default") or os.environ.get("VAR", "default")
        if isinstance(node.func, ast.Attribute) and isinstance(
            node.func.value, (ast.Name, ast.Attribute)
        ):
            # Check for os.getenv or os.environ.get
            func_name = node.func.attr
            module_name = ""
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                module_name = "os"
            elif (
                isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"
            ):
                module_name = "os.environ"

            if (
                module_name in ["os", "os.environ"]
                and func_name in ["getenv", "get"]
                and node.args
            ):
                var_name_node = node.args[0]
                if isinstance(var_name_node, ast.Constant):
                    var_name = var_name_node.value
                    default_value = ""
                    if len(node.args) > 1:
                        default_value_node = node.args[1]
                        if isinstance(default_value_node, ast.Constant):
                            default_value = default_value_node.value
                    self.env_vars[var_name] = str(default_value)

        self.generic_visit(node)


def scan_codebase_for_env_vars(directory: str) -> Dict[str, str]:
    """Scans all Python files in a directory for env var usage."""
    visitor = EnvVarVisitor()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=str(file_path))
                        visitor.visit(tree)
                except SyntaxError as e:
                    print(f"Warning: Could not parse {file_path}. Error: {e}")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return visitor.env_vars


def generate_env_example() -> None:
    """
    Generates the .env.example file.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    env_example_path = project_root / ".env.example"

    print(f"Scanning for environment variables in '{SRC_DIRECTORY}'...")
    scanned_vars = scan_codebase_for_env_vars(str(project_root / SRC_DIRECTORY))

    # Combine scanned variables with third-party, avoiding duplicates
    combined_vars = scanned_vars.copy()
    for group, variables in THIRD_PARTY_VARS.items():
        for name, default in variables.items():
            if name not in combined_vars:
                combined_vars[name] = default

    with open(env_example_path, "w", encoding="utf-8") as f:
        f.write(
            "# This file was auto-generated by src/scripts/generate_env_example.py\n"
        )
        f.write(
            "# It contains environment variables discovered by scanning the codebase.\n\n"
        )

        f.write("# --- Discovered Settings ---\n")
        # Sort variables for consistent output
        for env_name, default_value in sorted(combined_vars.items()):
            f.write(f"{env_name}={default_value}\n")
        f.write("\n")

        # Add the manual section for complex variables
        if MANUAL_ENV_SECTION:
            f.write(MANUAL_ENV_SECTION)

    print(f"Successfully generated {env_example_path}")
    print(f"Discovered {len(scanned_vars)} application-specific variables.")


if __name__ == "__main__":
    generate_env_example()
