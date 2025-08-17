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

        from src.core.app import AppContext
        from src.database import Database

        # Create dummy raw data
        self.db = Database(PathSettings(root_dir=self.test_dir))
        self.db.insert_messages(
            [
                {
                    "id": 1,
                    "date": "2023-01-01T12:00:00",
                    "sender_id": "user1",
                    "message_type": "text",
                    "content": "Hello world",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 1,
                    "topic_title": "Test Topic",
                    "source_name": "Test Group",
                    "source_group_id": 123,
                    "source_topic_id": 1,
                    "source_saved_file": None,
                    "ingestion_timestamp": "2023-01-01T12:00:00",
                },
                {
                    "id": 2,
                    "date": "2023-01-01T12:01:00",
                    "sender_id": "user2",
                    "message_type": "text",
                    "content": "Hello back",
                    "extra_data": {},
                    "reply_to_msg_id": None,
                    "topic_id": 1,
                    "topic_title": "Test Topic",
                    "source_name": "Test Group",
                    "source_group_id": 123,
                    "source_topic_id": 1,
                    "source_saved_file": None,
                    "ingestion_timestamp": "2023-01-01T12:01:00",
                },
            ]
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
        test_paths = PathSettings(root_dir=self.test_dir)
        from src.config.conversation import ConversationSettings
        from src.config.litellm import LiteLLMSettings
        from src.config.rag import RAGSettings
        from src.config.synthesis import SynthesisSettings

        test_settings = AppSettings(
            paths=test_paths,
            telegram=TelegramSettings(
                bot_token="fake_token",
                group_ids=[],
                session_name="test_session",
                phone=None,
                password=None,
            ),
            litellm=LiteLLMSettings(),
            synthesis=SynthesisSettings(),
            rag=RAGSettings(),
            conversation=ConversationSettings(),
            console_log_level="INFO",
        )

        from src.core.app import AppContext

        mock_app_context = AppContext(test_settings)
        mock_app_context.db = self.db

        with patch("src.scripts.process_data.initialize_app", return_value=mock_app_context), patch(
            "src.scripts.synthesize_knowledge.initialize_app", return_value=mock_app_context
        ):
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
            collection = mock_app_context.db_client.get_collection(
                "telegram_knowledge_base_v2"
            )
            self.assertEqual(collection.count(), 1)
            print(f"ChromaDB contains {collection.count()} documents.")


if __name__ == "__main__":
    unittest.main()
