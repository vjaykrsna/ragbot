from datetime import datetime

import pytest

from src.core.data_models.messages import (
    Conversation,
    KnowledgeNugget,
    Message,
    ProcessedMessage,
)


def test_message_model():
    """Test the Message model validation."""
    # Create a valid message
    message_data = {
        "id": 12345,
        "source_group_id": 67890,
        "topic_id": 11111,
        "date": "2025-08-25T10:30:00Z",
        "sender_id": "user_123",
        "message_type": "text",
        "content": "Hello, world!",
        "extra_data": {"file_id": "file_456"},
        "reply_to_msg_id": 12344,
        "topic_title": "General Discussion",
        "source_name": "Telegram Group",
        "ingestion_timestamp": "2025-08-25T10:31:00Z",
        "normalized_values": [{"value": 42, "unit": "GB"}],
    }

    message = Message(**message_data)

    # Verify the model was created correctly
    assert message.id == 12345
    assert message.source_group_id == 67890
    assert message.topic_id == 11111
    assert isinstance(message.date, datetime)
    assert message.sender_id == "user_123"
    assert message.message_type == "text"
    assert message.content == "Hello, world!"
    assert message.extra_data == {"file_id": "file_456"}
    assert message.reply_to_msg_id == 12344
    assert message.topic_title == "General Discussion"
    assert message.source_name == "Telegram Group"
    assert isinstance(message.ingestion_timestamp, datetime)
    assert message.normalized_values == [{"value": 42, "unit": "GB"}]


def test_processed_message_model():
    """Test the ProcessedMessage model validation."""
    # Create a valid processed message
    processed_message_data = {
        "id": 12345,
        "date": "2025-08-25T10:30:00Z",
        "sender_id": "user_123",
        "content": "Hello, world!",
        "normalized_values": [{"value": 42, "unit": "GB"}],
    }

    processed_message = ProcessedMessage(**processed_message_data)

    # Verify the model was created correctly
    assert processed_message.id == 12345
    assert isinstance(processed_message.date, datetime)
    assert processed_message.sender_id == "user_123"
    assert processed_message.content == "Hello, world!"
    assert processed_message.normalized_values == [{"value": 42, "unit": "GB"}]


def test_conversation_model():
    """Test the Conversation model validation."""
    # Create a valid conversation
    conversation_data = {
        "ingestion_timestamp": "2025-08-25T10:30:00Z",
        "ingestion_hash": "abc123def456",
        "source_files": ["file1.txt", "file2.txt"],
        "source_names": ["Group A", "Group B"],
        "conversation": [
            {
                "id": 12345,
                "date": "2025-08-25T10:30:00Z",
                "sender_id": "user_123",
                "content": "Hello, world!",
                "normalized_values": [{"value": 42, "unit": "GB"}],
            }
        ],
        "message_count": 1,
    }

    conversation = Conversation(**conversation_data)

    # Verify the model was created correctly
    assert isinstance(conversation.ingestion_timestamp, datetime)
    assert conversation.ingestion_hash == "abc123def456"
    assert conversation.source_files == ["file1.txt", "file2.txt"]
    assert conversation.source_names == ["Group A", "Group B"]
    assert len(conversation.conversation) == 1
    assert isinstance(conversation.conversation[0], ProcessedMessage)
    assert conversation.message_count == 1


def test_knowledge_nugget_model():
    """Test the KnowledgeNugget model validation."""
    # Create a valid knowledge nugget
    nugget_data = {
        "topic": "Setting up Oracle Cloud",
        "timestamp": "2025-08-25T10:30:00Z",
        "topic_summary": "How to configure Oracle Cloud Free Tier",
        "detailed_analysis": "Users confirmed that the best approach is to use an 'Always Free' Ampere A1 Compute instance...",
        "status": "FACT",
        "keywords": ["oracle cloud", "free tier", "deployment"],
        "source_message_ids": [101, 102, 105, 110],
        "user_ids_involved": ["User_1", "User_5", "User_12"],
        "normalized_values": [
            {"span": "2GB RAM", "value": 2, "unit": "GB", "confidence": "High"}
        ],
        "ingestion_timestamp": "2025-08-25T10:31:00Z",
    }

    nugget = KnowledgeNugget(**nugget_data)

    # Verify the model was created correctly
    assert nugget.topic == "Setting up Oracle Cloud"
    assert isinstance(nugget.timestamp, datetime)
    assert nugget.topic_summary == "How to configure Oracle Cloud Free Tier"
    assert (
        nugget.detailed_analysis
        == "Users confirmed that the best approach is to use an 'Always Free' Ampere A1 Compute instance..."
    )
    assert nugget.status == "FACT"
    assert nugget.keywords == ["oracle cloud", "free tier", "deployment"]
    assert nugget.source_message_ids == [101, 102, 105, 110]
    assert nugget.user_ids_involved == ["User_1", "User_5", "User_12"]
    assert nugget.normalized_values == [
        {"span": "2GB RAM", "value": 2, "unit": "GB", "confidence": "High"}
    ]
    assert isinstance(nugget.ingestion_timestamp, datetime)


def test_message_model_missing_required_fields():
    """Test that Message model validation fails when required fields are missing."""
    # Try to create a message with missing required fields
    incomplete_message_data = {
        "id": 12345,
        # Missing other required fields
    }

    with pytest.raises(ValueError):
        Message(**incomplete_message_data)


def test_conversation_model_with_empty_conversation():
    """Test the Conversation model with an empty conversation list."""
    # Create a conversation with no messages
    conversation_data = {
        "ingestion_timestamp": "2025-08-25T10:30:00Z",
        "ingestion_hash": "abc123def456",
        "source_files": [],
        "source_names": [],
        "conversation": [],
        "message_count": 0,
    }

    conversation = Conversation(**conversation_data)

    # Verify the model was created correctly
    assert conversation.conversation == []
    assert conversation.message_count == 0
