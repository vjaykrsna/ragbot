from pydantic import BaseModel, Field


class ConversationSettings(BaseModel):
    """Settings for conversation grouping."""

    time_threshold_seconds: int = Field(300, env="CONVERSATION_TIME_THRESHOLD_SECONDS")
    session_window_seconds: int = Field(3600, env="SESSION_WINDOW_SECONDS")
