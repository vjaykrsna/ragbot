import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.scripts.synthesize_knowledge import KnowledgeSynthesizer


class TestKnowledgeSynthesizer(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.paths.processed_data_dir = "/fake/processed"
        self.mock_settings.paths.processed_conversations_file = "convos.json"
        self.mock_settings.paths.prompt_file = "/fake/prompt.md"
        self.mock_settings.synthesis.requests_per_minute = 10

        self.mock_db = MagicMock()
        self.mock_db_client = MagicMock()

        self.synthesizer = KnowledgeSynthesizer(
            settings=self.mock_settings, db=self.mock_db, db_client=self.mock_db_client
        )

    def test_load_processed_data_success(self):
        """
        Test successfully loading conversation data from a JSON file.
        """
        mock_data = [{"id": 1, "conversation": "hello"}]
        m_open = mock_open(read_data=json.dumps(mock_data))
        with patch("builtins.open", m_open):
            result = self.synthesizer._load_processed_data()
            self.assertEqual(result, mock_data)
            m_open.assert_called_once_with(
                "/fake/processed/convos.json", "r", encoding="utf-8"
            )

    def test_load_processed_data_file_not_found(self):
        """
        Test handling of a missing conversation file.
        """
        m_open = mock_open()
        m_open.side_effect = FileNotFoundError
        with patch("builtins.open", m_open):
            result = self.synthesizer._load_processed_data()
            self.assertEqual(result, [])

    def test_load_processed_data_json_decode_error(self):
        """
        Test handling of a corrupted/empty conversation file.
        """
        m_open = mock_open(read_data="not json")
        with patch("builtins.open", m_open):
            result = self.synthesizer._load_processed_data()
            self.assertEqual(result, [])

    def test_load_prompt_template_success(self):
        """
        Test successfully loading the prompt template.
        """
        prompt_content = "This is the prompt."
        m_open = mock_open(read_data=prompt_content)
        with patch("builtins.open", m_open):
            result = self.synthesizer._load_prompt_template()
            self.assertEqual(result, prompt_content)
            m_open.assert_called_once_with("/fake/prompt.md", "r", encoding="utf-8")

    def test_load_prompt_template_file_not_found(self):
        """
        Test handling of a missing prompt file.
        """
        m_open = mock_open()
        m_open.side_effect = FileNotFoundError
        with patch("builtins.open", m_open):
            result = self.synthesizer._load_prompt_template()
            self.assertIsNone(result)

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_generate_nuggets_happy_path(self, mock_litellm_client):
        """
        Test the happy path for generating knowledge nuggets from a conversation batch.
        """
        # Arrange
        mock_nugget = {
            "topic": "Test",
            "timestamp": "2023-01-01T00:00:00Z",
            "topic_summary": "Summary",
            "detailed_analysis": "Analysis",
            "status": "Complete",
            "keywords": [],
            "source_message_ids": [1],
            "user_ids_involved": ["u1"],
        }
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = f"```json\n[{json.dumps(mock_nugget)}]\n```"
        mock_litellm_client.complete.return_value = mock_response

        conv_batch = [{"conversation": [{"id": 1, "content": "Hello"}]}]
        prompt = "test prompt"

        # Act
        result = self.synthesizer._generate_nuggets_batch(conv_batch, prompt)

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topic"], "Test")
        mock_litellm_client.complete.assert_called_once()

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_generate_nuggets_llm_returns_malformed_json(self, mock_litellm_client):
        """
        Test that a malformed JSON response from the LLM is handled correctly.
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is not json"
        mock_litellm_client.complete.return_value = mock_response

        conv_batch = [{"conversation": [{"id": 1, "content": "Hello"}]}]
        prompt = "test prompt"

        with patch.object(self.synthesizer, "_save_failed_batch") as mock_save_failed:
            # Act
            result = self.synthesizer._generate_nuggets_batch(conv_batch, prompt)

            # Assert
            self.assertEqual(result, [])
            mock_save_failed.assert_called_once()

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_generate_nuggets_llm_returns_not_a_list(self, mock_litellm_client):
        """
        Test that a valid JSON response that is not a list is handled.
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"key": "value"}'
        mock_litellm_client.complete.return_value = mock_response

        conv_batch = [{"conversation": [{"id": 1, "content": "Hello"}]}]
        prompt = "test prompt"

        with patch.object(self.synthesizer, "_save_failed_batch") as mock_save_failed:
            # Act
            result = self.synthesizer._generate_nuggets_batch(conv_batch, prompt)

            # Assert
            self.assertEqual(result, [])
            mock_save_failed.assert_called_once()

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_generate_nuggets_llm_returns_invalid_structure(self, mock_litellm_client):
        """
        Test that nuggets with missing required keys are filtered out.
        """
        # Arrange
        invalid_nugget = {"topic": "Test"}  # Missing other keys
        valid_nugget = {
            "topic": "Test2",
            "timestamp": "2023-01-01T00:00:00Z",
            "topic_summary": "Summary",
            "detailed_analysis": "Analysis",
            "status": "Complete",
            "keywords": [],
            "source_message_ids": [1],
            "user_ids_involved": ["u1"],
        }
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = (
            f"[{json.dumps(invalid_nugget)}, {json.dumps(valid_nugget)}]"
        )
        mock_litellm_client.complete.return_value = mock_response

        conv_batch = [{"conversation": [{"id": 1, "content": "Hello"}]}]
        prompt = "test prompt"

        with patch.object(self.synthesizer, "_save_failed_batch") as mock_save_failed:
            # Act
            result = self.synthesizer._generate_nuggets_batch(conv_batch, prompt)

            # Assert
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["topic"], "Test2")
            mock_save_failed.assert_called_once()

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_embed_nuggets_happy_path(self, mock_litellm_client):
        """
        Test the happy path for embedding a batch of nuggets.
        """
        # Arrange
        nuggets = [
            {"detailed_analysis": "analysis 1"},
            {"detailed_analysis": "analysis 2"},
        ]
        mock_embeddings = [[0.1], [0.2]]
        mock_litellm_client.embed.return_value = mock_embeddings

        # Act
        result = self.synthesizer._embed_nuggets_batch(nuggets)

        # Assert
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["embedding"], [0.1])
        self.assertEqual(result[1]["embedding"], [0.2])
        mock_litellm_client.embed.assert_called_once_with(
            ["analysis 1", "analysis 2"], max_retries=1
        )

    @patch("src.scripts.synthesize_knowledge.litellm_client")
    def test_embed_nuggets_api_error(self, mock_litellm_client):
        """
        Test that an APIError is raised after retries if embedding fails.
        """
        # Arrange
        nuggets = [{"detailed_analysis": "analysis 1"}]
        mock_litellm_client.embed.return_value = None  # Simulate failure

        # Act & Assert
        with self.assertRaises(
            Exception
        ):  # The decorator re-raises APIError as a generic Exception
            self.synthesizer._embed_nuggets_batch(nuggets)

        # 2 attempts are hardcoded in the method
        self.assertEqual(mock_litellm_client.embed.call_count, 2)

    def test_store_nuggets_happy_path(self):
        """
        Test the happy path for storing a batch of nuggets in ChromaDB.
        """
        # Arrange
        mock_collection = MagicMock()
        nuggets = [
            {
                "detailed_analysis": "analysis 1",
                "embedding": [0.1],
                "some_list": [1, 2],
                "none_value": None,
            }
        ]

        # Act
        num_stored = self.synthesizer._store_nuggets_batch(mock_collection, nuggets)

        # Assert
        self.assertEqual(num_stored, 1)
        mock_collection.add.assert_called_once()

        # Check that metadata was sanitized correctly
        call_args = mock_collection.add.call_args
        metadatas = call_args.kwargs["metadatas"]
        self.assertEqual(len(metadatas), 1)
        self.assertNotIn("embedding", metadatas[0])
        self.assertNotIn("none_value", metadatas[0])
        self.assertEqual(
            metadatas[0]["some_list"], "[1, 2]"
        )  # Check list serialization

    def test_store_nuggets_chroma_error(self):
        """
        Test that ChromaDB errors are handled gracefully.
        """
        # Arrange
        mock_collection = MagicMock()
        mock_collection.add.side_effect = ValueError("DB error")
        nuggets = [{"detailed_analysis": "analysis 1", "embedding": [0.1]}]

        # Act
        num_stored = self.synthesizer._store_nuggets_batch(mock_collection, nuggets)

        # Assert
        self.assertEqual(num_stored, 0)
