import os
import unittest
from unittest.mock import patch

import chromadb

from src.core.app import initialize_app


class TestDatabaseIntegration(unittest.TestCase):
    def setUp(self):
        # Mock environment variables to avoid dependency on actual config
        with patch.dict(
            os.environ,
            {
                "API_ID": "123456",
                "API_HASH": "test_hash",
                "PHONE": "+1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_token",
                "LITELLM_CONFIG_JSON": '{"model_list": [], "litellm_settings": {}}',
            },
        ):
            self.app_context = initialize_app()
            self.db_path = self.app_context.settings.paths.db_dir
            self.collection_name = self.app_context.settings.rag.collection_name
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name
            )

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
