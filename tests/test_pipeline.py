import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import chromadb

from src.config.paths import PathSettings
from src.config.settings import AppSettings
from src.config.telegram import TelegramSettings
from src.scripts.process_data import main as process_data_main
from src.scripts.synthesize_knowledge import main as synthesize_main
from src.services import mock_litellm_client


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.raw_data_dir = os.path.join(self.test_dir, "data", "raw")
        self.processed_data_dir = os.path.join(self.test_dir, "data", "processed")
        self.knowledge_base_dir = os.path.join(self.test_dir, "knowledge_base")
        self.docs_dir = os.path.join(self.test_dir, "docs")
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)

        # Create dummy raw data
        self.raw_file = os.path.join(self.raw_data_dir, "data.jsonl")
        with open(self.raw_file, "w") as f:
            f.write(
                '{"id": 1, "date": "2023-01-01T12:00:00", "sender_id": "user1", "content": "Hello world"}\n'
            )
            f.write(
                '{"id": 2, "date": "2023-01-01T12:01:00", "sender_id": "user2", "content": "Hello back"}\n'
            )

        # Create dummy prompt file
        self.prompt_file = os.path.join(self.docs_dir, "knowledge_synthesis_prompt.md")
        with open(self.prompt_file, "w") as f:
            f.write("This is a test prompt.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("src.scripts.synthesize_knowledge.litellm_client", new=mock_litellm_client)
    def test_full_pipeline(self):
        # Override path settings to use temporary directories
        test_paths = PathSettings(
            root_dir=self.test_dir,
            data_dir=os.path.join(self.test_dir, "data"),
            docs_dir=self.docs_dir,
            log_dir=os.path.join(self.test_dir, "logs"),
        )
        test_settings = AppSettings(
            paths=test_paths,
            telegram=TelegramSettings(bot_token="fake_token"),
        )

        with patch("src.core.app.load_settings", return_value=test_settings):
            # 1. Run data processing pipeline
            print("Running data processing pipeline...")
            process_data_main()
            print("Data processing pipeline finished.")

            # Check that processed file was created and contains data
            processed_file = test_paths.processed_conversations_file
            self.assertTrue(os.path.exists(processed_file))
            with open(processed_file, "r") as f:
                processed_data = json.load(f)
                self.assertEqual(len(processed_data), 1)
                self.assertEqual(len(processed_data[0]["conversation"]), 2)
            print(f"Processed file created at: {processed_file}")

            # 2. Run knowledge synthesis pipeline
            print("Running knowledge synthesis pipeline...")
            synthesize_main()
            print("Knowledge synthesis pipeline finished.")

            # Check that chromadb contains the synthesized knowledge
            client = chromadb.PersistentClient(path=test_paths.db_path)
            collection = client.get_collection("telegram_knowledge_base_v2")
            self.assertEqual(collection.count(), 1)
            print(f"ChromaDB contains {collection.count()} documents.")


if __name__ == "__main__":
    unittest.main()
