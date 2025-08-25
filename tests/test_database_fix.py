#!/usr/bin/env python3
"""
Test script to verify the database fix for the extra_data serialization issue.
"""

import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch

# Add the project root directory to the path
sys.path.insert(0, os.path.dirname(__file__).replace("/tests", ""))

from src.core.app import initialize_app
from src.core.database import serialize_extra_data


def test_serialize_extra_data():
    """Test the serialize_extra_data function with various inputs."""
    print("Testing serialize_extra_data function...")

    # Test with a normal dictionary
    normal_dict = {"key1": "value1", "key2": 123, "key3": True}
    result = serialize_extra_data(normal_dict)
    print(f"Normal dict result: {result}")
    assert isinstance(result, str), "Result should be a string"

    # Test with a dictionary containing datetime
    datetime_dict = {"key1": "value1", "timestamp": datetime.now()}
    result = serialize_extra_data(datetime_dict)
    print(f"DateTime dict result: {result}")
    assert isinstance(result, str), "Result should be a string"

    # Test with None
    result = serialize_extra_data(None)
    print(f"None result: {result}")
    assert isinstance(result, str), "Result should be a string"
    assert result == "{}", "None should serialize to empty dict"

    # Test with a non-dict value
    result = serialize_extra_data("not a dict")
    print(f"String result: {result}")
    assert isinstance(result, str), "Result should be a string"

    result = serialize_extra_data(123)
    print(f"Integer result: {result}")
    assert isinstance(result, str), "Result should be a string"

    print("All serialize_extra_data tests passed!")


def test_database_insertion():
    """Test inserting messages with various extra_data values."""
    print("\nTesting database insertion...")

    # Create a temporary directory for the database
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock environment variables
        with patch.dict(
            os.environ,
            {
                "API_ID": "123456",
                "API_HASH": "test_hash",
                "PHONE": "+1234567890",
                "PASSWORD": "test_password",
                "BOT_TOKEN": "test_token",
                "DB_DIR": temp_dir,
                "LITELLM_CONFIG_JSON": '{"model_list": [{"model_name": "gemini-synthesis-model", "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "fake-key"}}, {"model_name": "gemini-embedding-model", "litellm_params": {"model": "gemini/text-embedding-004", "api_key": "fake-key"}}], "litellm_settings": {}}',
            },
        ):
            # Initialize the app
            app_context = initialize_app()
            db = app_context.db

            # Test messages with different extra_data values
            test_messages = [
                {
                    "id": 1,
                    "source_group_id": 100,
                    "topic_id": 0,
                    "date": "2023-01-01T00:00:00",
                    "sender_id": "user1",
                    "message_type": "text",
                    "content": "Test message 1",
                    "extra_data": {"key1": "value1", "key2": 123},
                    "reply_to_msg_id": None,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "ingestion_timestamp": "2023-01-01T00:00:00",
                },
                {
                    "id": 2,
                    "source_group_id": 100,
                    "topic_id": 0,
                    "date": "2023-01-01T00:01:00",
                    "sender_id": "user2",
                    "message_type": "text",
                    "content": "Test message 2",
                    "extra_data": None,
                    "reply_to_msg_id": None,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "ingestion_timestamp": "2023-01-01T00:01:00",
                },
                {
                    "id": 3,
                    "source_group_id": 100,
                    "topic_id": 0,
                    "date": "2023-01-01T00:02:00",
                    "sender_id": "user1",
                    "message_type": "text",
                    "content": "Test message 3",
                    "extra_data": "not a dict",
                    "reply_to_msg_id": None,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "ingestion_timestamp": "2023-01-01T00:02:00",
                },
                {
                    "id": 4,
                    "source_group_id": 100,
                    "topic_id": 0,
                    "date": "2023-01-01T00:03:00",
                    "sender_id": "user3",
                    "message_type": "poll",
                    "content": {
                        "question": "Test poll",
                        "options": ["Option 1", "Option 2"],
                    },
                    "extra_data": {"poll_id": "poll123", "is_quiz": True},
                    "reply_to_msg_id": None,
                    "topic_title": "General",
                    "source_name": "Test Group",
                    "ingestion_timestamp": "2023-01-01T00:03:00",
                },
            ]

            # Insert messages
            try:
                db.insert_messages(test_messages)
                print("Messages inserted successfully!")

                # Verify messages were inserted
                count = 0
                for _ in db.get_all_messages():
                    count += 1
                print(f"Retrieved {count} messages from database")
                assert count == 4, f"Expected 4 messages, got {count}"

                print("Database insertion test passed!")
            except Exception as e:
                print(f"Database insertion test failed with error: {e}")
                raise


if __name__ == "__main__":
    test_serialize_extra_data()
    test_database_insertion()
    print("\nAll tests passed! The database fix is working correctly.")
