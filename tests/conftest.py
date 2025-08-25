import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor


@pytest.fixture(scope="function", autouse=True)
def set_test_environment(monkeypatch):
    """
    Sets up a consistent, mock environment for the entire test session.
    This prevents tests from failing due to missing environment variables
    when importing modules that call get_settings() at the module level.
    """
    monkeypatch.setenv("API_ID", "12345")
    monkeypatch.setenv("API_HASH", "test_hash")
    monkeypatch.setenv("PHONE", "1234567890")
    monkeypatch.setenv("PASSWORD", "test_password")
    monkeypatch.setenv("BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("GROUP_IDS", "1,2,3")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("LITELLM_API_KEY", "test_litellm_key")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv(
        "LITELLM_CONFIG_JSON",
        '{"model_list": [{"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "fake-key"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "fake-key"}}], "litellm_settings": {}}',
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def mock_app_context(temp_db_dir):
    """Create a mock application context for testing."""
    with patch.dict(
        os.environ,
        {
            "API_ID": "12345",
            "API_HASH": "test_hash",
            "PHONE": "1234567890",
            "PASSWORD": "test_password",
            "BOT_TOKEN": "test_bot_token",
            "GROUP_IDS": "1,2,3",
            "DB_DIR": temp_db_dir,  # Use temp directory
            "LITELLM_CONFIG_JSON": '{"model_list": [{"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "fake-key"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "fake-key"}}], "litellm_settings": {}}',
        },
    ):
        app_context = initialize_app()
        yield app_context


@pytest.fixture(scope="function")
def mock_telegram_client():
    """Create a mock Telegram client for testing."""
    client = AsyncMock()
    client.get_chat = AsyncMock()
    client.get_chat_history = MagicMock()
    client.invoke = AsyncMock()
    return client


@pytest.fixture(scope="function")
def mock_extractor(mock_telegram_client, mock_app_context):
    """Create a mock TelegramExtractor for testing."""
    storage = Storage(mock_app_context)
    extractor = TelegramExtractor(mock_telegram_client, storage)
    return extractor


@pytest.fixture(scope="function")
def temp_db_dir():
    """Create a temporary directory for database testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil

    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def sample_message():
    """Create a sample message for testing."""
    return {
        "id": 1,
        "date": "2024-01-01T12:00:00",
        "sender_id": "user1",
        "message_type": "text",
        "content": "Test message content",
        "extra_data": {},
        "reply_to_msg_id": None,
        "topic_id": 101,
        "topic_title": "General",
        "source_name": "Test Group",
        "source_group_id": 202,
        "ingestion_timestamp": "2024-01-01T12:00:01",
    }


@pytest.fixture(scope="function")
def sample_message_batch():
    """Create a batch of sample messages for testing."""
    messages = []
    for i in range(10):
        messages.append(
            {
                "id": i + 1,
                "date": "2024-01-01T12:00:00",
                "sender_id": f"user{i % 3 + 1}",
                "message_type": "text",
                "content": f"Test message {i + 1} content",
                "extra_data": {},
                "reply_to_msg_id": None,
                "topic_id": 101,
                "topic_title": "General",
                "source_name": "Test Group",
                "source_group_id": 202,
                "ingestion_timestamp": "2024-01-01T12:00:01",
            }
        )
    return messages


@pytest.fixture(scope="function")
def mock_entity():
    """Create a mock Telegram entity for testing."""
    entity = MagicMock()
    entity.id = 123
    entity.title = "Test Group"
    entity.username = "testgroup"
    entity.is_forum = False
    entity.access_hash = 456789
    return entity


@pytest.fixture(scope="function")
def mock_topic():
    """Create a mock Telegram topic for testing."""
    topic = MagicMock()
    topic.id = 456
    topic.title = "Test Topic"
    return topic


@pytest.fixture(scope="function")
def mock_forum_entity():
    """Create a mock forum entity for testing."""
    entity = MagicMock()
    entity.id = 123
    entity.title = "Test Forum"
    entity.username = "testforum"
    entity.is_forum = True
    entity.access_hash = 456789
    return entity


@pytest.fixture(scope="function")
def mock_forum_topics():
    """Create mock forum topics for testing."""
    topics = []
    for i in range(3):
        topic = MagicMock()
        topic.id = 100 + i
        topic.title = f"Forum Topic {i + 1}"
        topics.append(topic)
    return topics


class MockAsyncIterator:
    """Mock async iterator for testing async generators."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.items:
            return self.items.pop(0)
        raise StopAsyncIteration


@pytest.fixture(scope="function")
def mock_message():
    """Create a mock Telegram message for testing."""
    msg = MagicMock()
    msg.id = 1
    msg.text = "Test message"
    msg.date = MagicMock()
    msg.date.isoformat.return_value = "2024-01-01T00:00:00"
    msg.from_user = MagicMock()
    msg.from_user.id = "user1"
    msg.sender_chat = None
    msg.message_thread_id = 456
    msg.reply_to_message_id = None
    msg.service = False
    msg.media = None
    return msg


@pytest.fixture(scope="function")
def mock_message_batch():
    """Create a batch of mock Telegram messages for testing."""
    messages = []
    for i in range(5):
        msg = MagicMock()
        msg.id = i + 1
        msg.text = f"Test message {i + 1}"
        msg.date = MagicMock()
        msg.date.isoformat.return_value = "2024-01-01T00:00:00"
        msg.from_user = MagicMock()
        msg.from_user.id = f"user{i % 3 + 1}"
        msg.sender_chat = None
        msg.message_thread_id = 456
        msg.reply_to_message_id = None
        msg.service = False
        msg.media = None
        messages.append(msg)
    return messages


@pytest.fixture(scope="function")
def production_like_config():
    """Create production-like configuration for testing."""
    return {
        "TELEGRAM_CONCURRENT_GROUPS": "3",
        "TELEGRAM_MESSAGES_PER_REQUEST": "100",
        "TELEGRAM_BUFFER_SIZE": "500",
        "TELEGRAM_UI_UPDATE_INTERVAL": "2",
        "TELEGRAM_BATCH_SIZE": "200",
        "TELEGRAM_PROGRESS_UPDATE_MESSAGES": "50",
    }


@pytest.fixture(scope="function")
def performance_test_config():
    """Create performance testing configuration."""
    return {
        "max_extraction_time_per_message": 0.01,  # 10ms
        "max_memory_usage_percent": 85.0,
        "max_concurrent_operations": 10,
        "performance_timeout": 30.0,
    }


# Test markers for better organization
pytest.mark.critical = pytest.mark.critical
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.error_resilience = pytest.mark.error_resilience
pytest.mark.migration = pytest.mark.migration
pytest.mark.production = pytest.mark.production
