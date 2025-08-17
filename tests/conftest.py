import pytest


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
