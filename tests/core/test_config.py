import json
import os
from unittest.mock import patch

import pytest

from src.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the settings cache before each test."""
    get_settings.cache_clear()


@patch("src.core.config.loader.load_dotenv")
def test_get_settings_happy_path(mock_load_dotenv):
    """
    Test that settings are loaded correctly when all environment variables are set.
    """
    litellm_config = {
        "model_list": [
            {
                "model_name": "azure-embedding-model",
                "litellm_params": {
                    "model": "text-embedding-ada-002",
                    "api_key": "fake-key",
                },
            },
            {
                "model_name": "gemini-synthesis-model",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": "fake-key",
                },
            },
        ],
        "router_settings": {"routing_strategy": "simple-shuffle"},
        "litellm_settings": {"set_verbose": True},
    }

    test_env = {
        "API_ID": "12345",
        "API_HASH": "fake_hash",
        "PHONE": "15551234567",
        "PASSWORD": "fake_password",
        "BOT_TOKEN": "fake_bot_token",
        "GROUP_IDS": "100, 200",
        "LITELLM_CONFIG_JSON": json.dumps(litellm_config),
    }

    with patch.dict(os.environ, test_env):
        settings = get_settings()

        # Assertions
        assert settings.telegram.api_id == 12345
        assert settings.telegram.group_ids == [100, 200]
        assert settings.litellm.set_verbose is True
        assert settings.litellm.router_settings.routing_strategy == "simple-shuffle"
        assert len(settings.litellm.model_list) == 2
        assert settings.litellm.embedding_model_name == "text-embedding-ada-002"
        assert settings.litellm.embedding_model_proxy == "azure-embedding-model"


@pytest.mark.parametrize(
    "missing_var",
    [
        "API_ID",
        "API_HASH",
        "PHONE",
        "PASSWORD",
        "BOT_TOKEN",
        "LITELLM_CONFIG_JSON",
    ],
)
@patch("src.core.config.loader.load_dotenv")
def test_missing_required_env_vars(mock_load_dotenv, missing_var):
    """
    Test that a RuntimeError is raised if a required environment variable is missing.
    """
    base_env = {
        "API_ID": "12345",
        "API_HASH": "fake_hash",
        "PHONE": "15551234567",
        "PASSWORD": "fake_password",
        "BOT_TOKEN": "fake_bot_token",
        "LITELLM_CONFIG_JSON": '{"model_list": []}',
    }

    test_env = base_env.copy()
    del test_env[missing_var]

    with pytest.raises(RuntimeError) as exc_info:
        with patch.dict(os.environ, test_env, clear=True):
            get_settings()

    assert f"'{missing_var}' must be set" in str(exc_info.value)


@patch("src.core.config.loader.load_dotenv")
def test_default_values(mock_load_dotenv):
    """
    Test that default values are correctly applied for optional settings.
    """
    litellm_config = {
        "model_list": [
            {
                "model_name": "gemini-synthesis-model",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": "fake-key",
                },
            },
            {
                "model_name": "gemini-embedding-model",
                "litellm_params": {
                    "model": "gemini/text-embedding-004",
                    "api_key": "fake-key",
                },
            },
        ],
        "litellm_settings": {},
    }
    minimal_env = {
        "API_ID": "12345",
        "API_HASH": "fake_hash",
        "PHONE": "15551234567",
        "PASSWORD": "fake_password",
        "BOT_TOKEN": "fake_bot_token",
        "LITELLM_CONFIG_JSON": json.dumps(litellm_config),
    }

    with patch.dict(os.environ, minimal_env, clear=True):
        settings = get_settings()

        # Assertions for default values
        assert settings.telegram.session_name == "telegram_session"
        assert settings.console_log_level == "INFO"
        assert settings.synthesis.max_workers == 4
        assert settings.rag.collection_name == "telegram_knowledge_base"
        assert settings.conversation.time_threshold_seconds == 300
