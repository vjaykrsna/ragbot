"""
Standardized message data model.

This module defines the structure and validation for message objects
used throughout the application.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    Standardized message model representing a single message in a conversation.
    """

    id: int = Field(..., description="Unique identifier for the message")
    source_group_id: int = Field(..., description="ID of the source group")
    topic_id: int = Field(..., description="ID of the topic")
    date: datetime = Field(..., description="Timestamp when the message was sent")
    sender_id: str = Field(..., description="ID of the sender")
    message_type: str = Field(
        ..., description="Type of the message (text, photo, etc.)"
    )
    content: str = Field(..., description="Content of the message")
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional data related to the message"
    )
    reply_to_msg_id: Optional[int] = Field(
        None, description="ID of the message this message is replying to"
    )
    topic_title: Optional[str] = Field(None, description="Title of the topic")
    source_name: Optional[str] = Field(None, description="Name of the source")
    ingestion_timestamp: Optional[datetime] = Field(
        None, description="Timestamp when the message was ingested"
    )
    normalized_values: Optional[List[Dict[str, Any]]] = Field(
        None, description="Normalized numeric values extracted from the message"
    )


class ProcessedMessage(BaseModel):
    """
    Message model after processing, used in the synthesis pipeline.
    """

    id: int = Field(..., description="Unique identifier for the message")
    date: datetime = Field(..., description="Timestamp when the message was sent")
    sender_id: str = Field(..., description="ID of the sender")
    content: str = Field(..., description="Content of the message")
    normalized_values: Optional[List[Dict[str, Any]]] = Field(
        None, description="Normalized numeric values extracted from the message"
    )


class Conversation(BaseModel):
    """
    Standardized conversation model representing a group of related messages.
    """

    ingestion_timestamp: datetime = Field(
        ..., description="Timestamp when the conversation was ingested"
    )
    ingestion_hash: str = Field(
        ..., description="Hash identifying the conversation content"
    )
    source_files: List[str] = Field(
        ..., description="List of source files associated with the conversation"
    )
    source_names: List[str] = Field(
        ..., description="List of source names associated with the conversation"
    )
    conversation: List[ProcessedMessage] = Field(
        ..., description="List of messages in the conversation"
    )
    message_count: int = Field(
        ..., description="Number of messages in the conversation"
    )


class KnowledgeNugget(BaseModel):
    """
    Standardized knowledge nugget model representing a piece of structured knowledge.
    """

    topic: str = Field(
        ..., description="Short descriptive title for the conversation topic"
    )
    timestamp: datetime = Field(
        ..., description="Timestamp of the last message in the conversation"
    )
    topic_summary: str = Field(
        ..., description="Concise summary of the core topic or question"
    )
    detailed_analysis: str = Field(
        ..., description="Comprehensive explanation derived from the conversation"
    )
    status: str = Field(
        ...,
        description="Reliability of the information (FACT, SPECULATION, COMMUNITY_OPINION)",
    )
    keywords: List[str] = Field(
        ..., description="Key terms and entities to aid in search"
    )
    source_message_ids: List[int] = Field(
        ..., description="Array of message IDs from the source conversation"
    )
    user_ids_involved: List[str] = Field(
        ..., description="Anonymized user IDs of the participants"
    )
    normalized_values: Optional[List[Dict[str, Any]]] = Field(
        None, description="Numeric/date facts detected in the conversation"
    )
    ingestion_timestamp: Optional[datetime] = Field(
        None, description="Timestamp when the nugget was synthesized"
    )
