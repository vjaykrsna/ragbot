import json
import os
import unittest
from unittest.mock import patch

from src.core.config import get_settings


class TestConfig(unittest.TestCase):
    def setUp(self):
        """Clear the settings cache before each test."""
        get_settings.cache_clear()

    @patch("src.core.config.load_dotenv")
    def test_get_settings_happy_path(self, mock_load_dotenv):
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
                }
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
            self.assertEqual(settings.telegram.api_id, 12345)
            self.assertEqual(settings.telegram.group_ids, [100, 200])
            self.assertTrue(settings.litellm.set_verbose)
            self.assertEqual(
                settings.litellm.router_settings.routing_strategy, "simple-shuffle"
            )
            self.assertEqual(len(settings.litellm.model_list), 1)
            self.assertEqual(
                settings.litellm.embedding_model_name, "text-embedding-ada-002"
            )
            self.assertEqual(
                settings.litellm.embedding_model_proxy, "azure-embedding-model"
            )

    @patch("src.core.config.load_dotenv")
    def test_missing_required_env_vars(self, mock_load_dotenv):
        """
        Test that a RuntimeError is raised if a required environment variable is missing.
        """
        required_vars = [
            "API_ID",
            "API_HASH",
            "PHONE",
            "PASSWORD",
            "BOT_TOKEN",
            "LITELLM_CONFIG_JSON",
        ]

        base_env = {
            "API_ID": "12345",
            "API_HASH": "fake_hash",
            "PHONE": "15551234567",
            "PASSWORD": "fake_password",
            "BOT_TOKEN": "fake_bot_token",
            "LITELLM_CONFIG_JSON": '{"model_list": []}',
        }

        for var in required_vars:
            with self.subTest(missing_var=var):
                test_env = base_env.copy()
                del test_env[var]

                with self.assertRaises(RuntimeError) as cm:
                    with patch.dict(os.environ, test_env, clear=True):
                        get_settings()

                self.assertIn(f"'{var}' must be set", str(cm.exception))

    @patch("src.core.config.load_dotenv")
    def test_default_values(self, mock_load_dotenv):
        """
        Test that default values are correctly applied for optional settings.
        """
        minimal_env = {
            "API_ID": "12345",
            "API_HASH": "fake_hash",
            "PHONE": "15551234567",
            "PASSWORD": "fake_password",
            "BOT_TOKEN": "fake_bot_token",
            "LITELLM_CONFIG_JSON": '{"model_list": []}',
        }

        with patch.dict(os.environ, minimal_env, clear=True):
            settings = get_settings()

            # Assertions for default values
            self.assertEqual(settings.telegram.session_name, "telegram_session")
            self.assertEqual(settings.console_log_level, "INFO")
            self.assertEqual(settings.synthesis.max_workers, 4)
            self.assertEqual(settings.rag.collection_name, "telegram_knowledge_base_v2")
            self.assertEqual(settings.conversation.time_threshold_seconds, 300)
