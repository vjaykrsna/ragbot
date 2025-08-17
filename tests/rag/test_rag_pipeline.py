import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.config import (
    AppSettings,
    ConversationSettings,
    LiteLLMSettings,
    PathSettings,
    RAGSettings,
    SynthesisSettings,
    TelegramSettings,
)
from src.rag.rag_pipeline import LiteLLMEmbeddingFunction, RAGPipeline


class TestRAGPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create a dummy AppSettings object for the test
        self.settings = AppSettings(
            telegram=TelegramSettings(
                api_id=12345,
                api_hash="fake_hash",
                bot_token="fake_token",
                group_ids=[],
                session_name="test_session",
                phone=None,
                password=None,
            ),
            litellm=LiteLLMSettings(),
            paths=PathSettings(),
            synthesis=SynthesisSettings(),
            rag=RAGSettings(),
            conversation=ConversationSettings(),
            console_log_level="INFO",
        )

        # Mock the dependencies
        self.mock_chroma_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_litellm_client = MagicMock()

        # Set up the return values for the mocks
        self.mock_chroma_client.get_or_create_collection.return_value = (
            self.mock_collection
        )
        self.mock_collection.query.return_value = {
            "metadatas": [
                [
                    {"full_text": "This is a context about apples."},
                    {"full_text": "This is a context about oranges."},
                ]
            ],
            "distances": [[0.1, 0.2]],
        }
        self.mock_litellm_client.embed.return_value = [[0.1, 0.2, 0.3]]

        # Mock the LLM completion response
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [MagicMock()]
        mock_completion_response.choices[0].message.content = "Apples are red."
        self.mock_litellm_client.complete.return_value = mock_completion_response

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("src.rag.rag_pipeline.chromadb.PersistentClient")
    def test_chromadb_connection_error(self, mock_chromadb_client_patch):
        """Test that an exception during collection creation is raised."""
        self.mock_chroma_client.get_or_create_collection.side_effect = Exception(
            "DB connection failed"
        )
        mock_chromadb_client_patch.return_value = self.mock_chroma_client

        with self.assertRaisesRegex(Exception, "DB connection failed"):
            RAGPipeline(self.settings, self.mock_chroma_client)

    @patch("src.rag.rag_pipeline.litellm_client")
    def test_embedding_failure(self, mock_litellm_client_patch):
        """Test that the pipeline handles embedding failures gracefully."""
        mock_litellm_client_patch.embed.return_value = None
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)

        with self.assertRaisesRegex(Exception, "Embedding failed"):
            rag_pipeline.embed_query("test query")

    @patch("src.rag.rag_pipeline.litellm_client")
    def test_retrieval_failure(self, mock_litellm_client_patch):
        """Test that the pipeline handles retrieval failures gracefully."""
        self.mock_collection.query.side_effect = Exception("DB query failed")
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)

        result = rag_pipeline.retrieve_context([0.1, 0.2])
        self.assertEqual(result, [])

    def test_rerank_with_empty_nuggets(self):
        """Test re-ranking with no nuggets returns an empty list."""
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)
        result = rag_pipeline.rerank_and_filter_nuggets([], [])
        self.assertEqual(result, [])

    def test_generate_response_with_no_context(self):
        """Test response generation with no context nuggets."""
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)
        response = rag_pipeline.generate_response("test query", [])
        self.assertIn("couldn't find any relevant information", response)

    @patch("src.rag.rag_pipeline.litellm_client")
    def test_llm_completion_failure(self, mock_litellm_client_patch):
        """Test that the pipeline handles LLM completion failures."""
        mock_litellm_client_patch.complete.return_value = None
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)

        response = rag_pipeline.generate_response(
            "test query", [{"full_text": "some context"}]
        )
        self.assertIn("encountered an error", response)

    def test_rerank_with_invalid_timestamp(self):
        """Test that re-ranking handles invalid timestamps gracefully."""
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)
        nuggets = [
            {"status": "Complete", "last_message_timestamp": "not-a-date"},
            {
                "status": "Complete",
                "last_message_timestamp": "2023-01-01T00:00:00Z",
            },
        ]
        distances = [0.1, 0.2]

        # This should run without raising an exception
        reranked = rag_pipeline.rerank_and_filter_nuggets(nuggets, distances)

        # The nugget with the valid date should be ranked first (higher recency score)
        self.assertEqual(reranked[0]["last_message_timestamp"], "2023-01-01T00:00:00Z")

    @patch("src.rag.rag_pipeline.chromadb.PersistentClient")
    @patch("src.rag.rag_pipeline.litellm_client")
    def test_query_pipeline(
        self, mock_litellm_client_patch, mock_chromadb_client_patch
    ):
        """Test the full RAG query pipeline with mocked dependencies."""
        # Assign our mocks to the patched objects
        mock_chromadb_client_patch.return_value = self.mock_chroma_client
        mock_litellm_client_patch.embed = self.mock_litellm_client.embed
        mock_litellm_client_patch.complete = self.mock_litellm_client.complete

        # Initialize the RAG pipeline
        rag_pipeline = RAGPipeline(self.settings, self.mock_chroma_client)

        # Call the query method
        query = "What color are apples?"
        response = rag_pipeline.query(query)

        # Assertions
        # 1. Assert that the embedding function was called for the query
        self.mock_litellm_client.embed.assert_called_once_with([query])

        # 2. Assert that the database was queried
        self.mock_collection.query.assert_called_once()

        # 3. Assert that the LLM was called to generate a response
        self.mock_litellm_client.complete.assert_called_once()
        call_args = self.mock_litellm_client.complete.call_args
        system_prompt = call_args[0][0][0]["content"]
        self.assertIn("This is a context about apples.", system_prompt)
        self.assertIn("This is a context about oranges.", system_prompt)

        # 4. Assert that the final response is correct
        self.assertEqual(response, "Apples are red.")


class TestLiteLLMEmbeddingFunction(unittest.TestCase):
    @patch("src.rag.rag_pipeline.litellm_client")
    def test_embedding_function_wrapper(self, mock_litellm_client):
        """Test the LiteLLMEmbeddingFunction wrapper."""
        mock_litellm_client.embed.return_value = [[0.1, 0.2]]

        embed_func = LiteLLMEmbeddingFunction("test-model")

        # Test __call__
        result = embed_func(["test input"])
        mock_litellm_client.embed.assert_called_once_with(["test input"])
        self.assertEqual(result, [[0.1, 0.2]])

        # Test name
        self.assertEqual(embed_func.name(), "test-model")


if __name__ == "__main__":
    unittest.main()
