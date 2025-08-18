import os
import socket
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml

from src.scripts.check_litellm_setup import (
    check_redis_connection,
    count_api_keys,
    main,
    parse_litellm_yaml,
)


def test_parse_litellm_yaml_success():
    """Test parsing a valid YAML file."""
    yaml_content = """
    model_list:
      - model_name: gpt-3.5-turbo
        litellm_params:
          api_key: "test_key"
    """
    with patch("builtins.open", mock_open(read_data=yaml_content)) as mock_file:
        cfg = parse_litellm_yaml("dummy_path.yaml")
        assert cfg is not None
        assert "model_list" in cfg
        mock_file.assert_called_once_with("dummy_path.yaml", "r")


def test_parse_litellm_yaml_failure():
    """Test handling of a missing or invalid YAML file."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        cfg = parse_litellm_yaml("non_existent_path.yaml")
        assert cfg is None


def test_count_api_keys():
    """Test counting API keys in the config."""
    cfg_with_keys = {
        "model_list": [
            {"litellm_params": {"api_key": "key1"}},
            {"litellm_params": {"api_key": "key2"}},
            {"litellm_params": {}},
        ]
    }
    assert count_api_keys(cfg_with_keys) == 2
    assert count_api_keys({}) == 0
    assert count_api_keys({"model_list": []}) == 0


@patch("socket.create_connection")
def test_check_redis_connection_success(mock_socket):
    """Test successful Redis connection."""
    assert check_redis_connection("localhost", 6379) is True


@patch("socket.create_connection", side_effect=socket.error)
def test_check_redis_connection_failure(mock_socket):
    """Test failed Redis connection."""
    assert check_redis_connection("localhost", 6379) is False


@patch("src.scripts.check_litellm_setup.initialize_app")
@patch("src.scripts.check_litellm_setup.parse_litellm_yaml")
@patch("src.scripts.check_litellm_setup.check_redis_connection")
@patch.dict(
    os.environ,
    {
        "LITELLM_PROXY_URL": "http://localhost:8000",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
    },
)
def test_main_with_redis(
    mock_check_redis, mock_parse_yaml, mock_initialize_app
):
    """Test the main function with Redis configured."""
    yaml_config = {
        "model_list": [
            {
                "model_name": "gpt-3.5-turbo",
                "litellm_params": {"api_key": "test_key", "rpm": 10},
            }
        ],
        "router_settings": {
            "cache_kwargs": {
                "type": "redis",
                "host": "os.environ/REDIS_HOST",
                "port": "os.environ/REDIS_PORT",
            }
        },
    }
    mock_parse_yaml.return_value = yaml_config
    mock_check_redis.return_value = True

    with patch("logging.Logger.info") as mock_log_info, patch(
        "logging.Logger.warning"
    ) as mock_log_warning:
        main()
        mock_parse_yaml.assert_called_once()
        mock_check_redis.assert_called_once_with("localhost", 6379)
        assert mock_log_warning.call_count == 0


@patch("src.scripts.check_litellm_setup.initialize_app")
@patch("src.scripts.check_litellm_setup.parse_litellm_yaml")
@patch("src.scripts.check_litellm_setup.check_redis_connection")
@patch.dict(os.environ, {}, clear=True)
def test_main_no_redis(
    mock_check_redis, mock_parse_yaml, mock_initialize_app
):
    """Test the main function without Redis configured."""
    yaml_config = {
        "model_list": [
            {
                "model_name": "gpt-3.5-turbo",
                "litellm_params": {"api_key": "test_key"},
            }
        ],
    }
    mock_parse_yaml.return_value = yaml_config

    with patch("logging.Logger.info") as mock_log_info:
        main()
        mock_parse_yaml.assert_called_once()
        mock_check_redis.assert_not_called()
        assert any(
            "No redis cache configured" in call[0][0]
            for call in mock_log_info.call_args_list
        )
