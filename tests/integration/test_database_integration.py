import os
import tempfile
import unittest
from unittest.mock import patch

import chromadb

from src.core.app import initialize_app


class TestDatabaseIntegration(unittest.TestCase):
    def setUp(self):
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()

        # Mock environment variables to avoid dependency on actual config
        with patch.dict(
            os.environ,
            {
                "API_ID": "123456",
                "API_HASH": "test_hash",
                "PHONE": "+1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_token",
                "DB_DIR": self.temp_dir,  # Override to use temp directory
                "LITELLM_CONFIG_JSON": '{"model_list": [{"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "fake-key"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "fake-key"}}], "litellm_settings": {}}',
            },
        ):
            self.app_context = initialize_app()
            # Override paths settings to use temp directory
            self.app_context.settings.paths.data_dir = self.temp_dir
            self.app_context.settings.paths.db_dir = os.path.join(
                self.temp_dir, "knowledge_base"
            )
            self.db_path = self.app_context.settings.paths.db_dir
            self.collection_name = self.app_context.settings.rag.collection_name
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name
            )

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_insert_and_get(self):
        """
        Test that we can insert and retrieve data from the database.
        """
        # Arrange
        test_id = "test_id_1"
        test_embedding = [1.0, 2.0, 3.0]
        test_metadata = {"test_key": "test_value"}
        test_document = "This is a test document."

        # Act
        self.collection.add(
            ids=[test_id],
            embeddings=[test_embedding],
            metadatas=[test_metadata],
            documents=[test_document],
        )

        # Assert
        retrieved = self.collection.get(ids=[test_id])
        self.assertEqual(len(retrieved["ids"]), 1)
        self.assertEqual(retrieved["ids"][0], test_id)
        self.assertEqual(retrieved["metadatas"][0], test_metadata)
        self.assertEqual(retrieved["documents"][0], test_document)
