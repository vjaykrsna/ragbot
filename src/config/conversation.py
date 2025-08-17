from dataclasses import dataclass


@dataclass
class ConversationSettings:
    """Settings for conversation grouping."""

    time_threshold_seconds: int = 300
    session_window_seconds: int = 3600
