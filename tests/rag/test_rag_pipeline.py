import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

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


@pytest.fixture
def rag_pipeline_setup():
    """Set up common test fixtures for RAGPipeline tests."""
    test_dir = tempfile.mkdtemp()

    # Create a dummy AppSettings object for the test
    settings = AppSettings(
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
    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()
    mock_litellm_client = MagicMock()

    # Set up the return values for the mocks
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_collection.query.return_value = {
        "metadatas": [
            [
                {"full_text": "This is a context about apples."},
                {"full_text": "This is a context about oranges."},
            ]
        ],
        "distances": [[0.1, 0.2]],
    }
    mock_litellm_client.embed.return_value = [[0.1, 0.2, 0.3]]

    # Mock the LLM completion response
    mock_completion_response = MagicMock()
    mock_completion_response.choices = [MagicMock()]
    mock_completion_response.choices[0].message.content = "Apples are red."
    mock_litellm_client.complete.return_value = mock_completion_response

    yield {
        "test_dir": test_dir,
        "settings": settings,
        "mock_chroma_client": mock_chroma_client,
        "mock_collection": mock_collection,
        "mock_litellm_client": mock_litellm_client,
    }

    # Cleanup
    shutil.rmtree(test_dir)


@patch("src.rag.rag_pipeline.chromadb.PersistentClient")
def test_chromadb_connection_error(mock_chromadb_client_patch, rag_pipeline_setup):
    """Test that an exception during collection creation is raised."""
    rag_pipeline_setup[
        "mock_chroma_client"
    ].get_or_create_collection.side_effect = Exception("DB connection failed")
    mock_chromadb_client_patch.return_value = rag_pipeline_setup["mock_chroma_client"]

    with pytest.raises(Exception, match="DB connection failed"):
        RAGPipeline(
            rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
        )


@patch("src.rag.rag_pipeline.litellm_client")
def test_embedding_failure(mock_litellm_client_patch, rag_pipeline_setup):
    """Test that the pipeline handles embedding failures gracefully."""
    mock_litellm_client_patch.embed.return_value = None
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )

    with pytest.raises(Exception, match="Embedding generation failed"):
        rag_pipeline.embed_query("test query")


@patch("src.rag.rag_pipeline.litellm_client")
def test_retrieval_failure(mock_litellm_client_patch, rag_pipeline_setup):
    """Test that the pipeline handles retrieval failures gracefully."""
    rag_pipeline_setup["mock_collection"].query.side_effect = Exception(
        "DB query failed"
    )
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )

    result = rag_pipeline.retrieve_context([0.1, 0.2])
    assert result == []


def test_rerank_with_empty_nuggets(rag_pipeline_setup):
    """Test re-ranking with no nuggets returns an empty list."""
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )
    result = rag_pipeline.rerank_and_filter_nuggets([], [])
    assert result == []


def test_generate_response_with_no_context(rag_pipeline_setup):
    """Test response generation with no context nuggets."""
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )
    response = rag_pipeline.generate_response("test query", [])
    assert "couldn't find any relevant information" in response


@patch("src.rag.rag_pipeline.litellm_client")
def test_llm_completion_failure(mock_litellm_client_patch, rag_pipeline_setup):
    """Test that the pipeline handles LLM completion failures."""
    mock_litellm_client_patch.complete.return_value = None
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )

    response = rag_pipeline.generate_response(
        "test query", [{"full_text": "some context"}]
    )
    assert "encountered an error" in response


def test_rerank_with_invalid_timestamp(rag_pipeline_setup):
    """Test that re-ranking handles invalid timestamps gracefully."""
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )
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
    assert reranked[0]["last_message_timestamp"] == "2023-01-01T00:00:00Z"


@patch("src.rag.rag_pipeline.chromadb.PersistentClient")
@patch("src.rag.rag_pipeline.litellm_client")
def test_query_pipeline(
    mock_litellm_client_patch, mock_chromadb_client_patch, rag_pipeline_setup
):
    """Test the full RAG query pipeline with mocked dependencies."""
    # Assign our mocks to the patched objects
    mock_chromadb_client_patch.return_value = rag_pipeline_setup["mock_chroma_client"]
    mock_litellm_client_patch.embed = rag_pipeline_setup["mock_litellm_client"].embed
    mock_litellm_client_patch.complete = rag_pipeline_setup[
        "mock_litellm_client"
    ].complete

    # Initialize the RAG pipeline
    rag_pipeline = RAGPipeline(
        rag_pipeline_setup["settings"], rag_pipeline_setup["mock_chroma_client"]
    )

    # Call the query method
    query = "What color are apples?"
    response = rag_pipeline.query(query)

    # Assertions
    # 1. Assert that the embedding function was called for the query
    rag_pipeline_setup["mock_litellm_client"].embed.assert_called_once_with([query])

    # 2. Assert that the database was queried
    rag_pipeline_setup["mock_collection"].query.assert_called_once()

    # 3. Assert that the LLM was called to generate a response
    rag_pipeline_setup["mock_litellm_client"].complete.assert_called_once()
    call_args = rag_pipeline_setup["mock_litellm_client"].complete.call_args
    system_prompt = call_args[0][0][0]["content"]
    assert "This is a context about apples." in system_prompt
    assert "This is a context about oranges." in system_prompt

    # 4. Assert that the final response is correct
    assert response == "Apples are red."


@patch("src.rag.rag_pipeline.litellm_client")
def test_embedding_function_wrapper(mock_litellm_client):
    """Test the LiteLLMEmbeddingFunction wrapper."""
    mock_litellm_client.embed.return_value = [[0.1, 0.2]]

    embed_func = LiteLLMEmbeddingFunction("test-model")

    # Test __call__
    result = embed_func(["test input"])
    mock_litellm_client.embed.assert_called_once_with(["test input"])
    assert result == [[0.1, 0.2]]

    # Test name
    assert embed_func.name() == "test-model"
