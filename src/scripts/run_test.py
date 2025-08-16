import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.scripts.process_data import main as process_data_main
from src.scripts.synthesize_knowledge import main as synthesize_main
from src.services import mock_litellm_client
from src.config.settings import AppSettings
from src.config.paths import PathSettings
from src.config.telegram import TelegramSettings

class TestPipeline(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.raw_data_dir = os.path.join(self.test_dir, "raw")
        self.processed_data_dir = os.path.join(self.test_dir, "processed")
        self.knowledge_base_dir = os.path.join(self.test_dir, "knowledge_base")
        self.docs_dir = os.path.join(self.test_dir, "docs")
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)

        # Create dummy raw data
        self.raw_file = os.path.join(self.raw_data_dir, "data.jsonl")
        with open(self.raw_file, "w") as f:
            f.write('{"id": 1, "date": "2023-01-01T12:00:00", "sender_id": "user1", "content": "Hello world"}\\n')
            f.write('{"id": 2, "date": "2023-01-01T12:01:00", "sender_id": "user2", "content": "Hello back"}\\n')

        # Create dummy prompt file
        self.prompt_file = os.path.join(self.docs_dir, "prompt.md")
        with open(self.prompt_file, "w") as f:
            f.write("This is a test prompt.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.scripts.synthesize_knowledge.litellm_client', new=mock_litellm_client)
    def test_full_pipeline(self):

        test_settings = AppSettings(
            paths=PathSettings(
                data_dir=self.test_dir,
                raw_data_dir=self.raw_data_dir,
                processed_data_dir=self.processed_data_dir,
                db_path=self.knowledge_base_dir,
                prompt_file=self.prompt_file,
            ),
            telegram=TelegramSettings(bot_token="fake_token"),
        )

        with patch('src.core.app.load_settings', return_value=test_settings):
            # 1. Run data processing pipeline
            print("Running data processing pipeline...")
            process_data_main()
            print("Data processing pipeline finished.")

            # Check that processed file was created
            processed_file = os.path.join(self.processed_data_dir, "processed_conversations.json")
            self.assertTrue(os.path.exists(processed_file))
            print(f"Processed file created at: {processed_file}")

            # 2. Run knowledge synthesis pipeline
            print("Running knowledge synthesis pipeline...")
            synthesize_main()
            print("Knowledge synthesis pipeline finished.")

            # Check that chromadb files were created
            chroma_db_file = os.path.join(self.knowledge_base_dir, "chroma.sqlite3")
            self.assertTrue(os.path.exists(chroma_db_file))
            print(f"ChromaDB file created at: {chroma_db_file}")


if __name__ == "__main__":
    unittest.main()
