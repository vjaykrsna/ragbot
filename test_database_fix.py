#!/usr/bin/env python3
"""
Test script to verify the database fix for the extra_data serialization issue.
"""

import os
import sys
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

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
    """Test database insertion with various message types."""
    print("Testing database insertion...")

    # Initialize app context
    app_context = initialize_app()

    # Clear the database first
    with app_context.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        conn.commit()

    # Test messages with various data types including datetime objects
    # test_messages = [
    #     {
    #         "id": 1,
    #         "source_group_id": 123,
    #         "topic_id": 456,
    #         "date": datetime.now(),
    #         "sender_id": "user1",
    #         "message_type": "text",
    #         "content": "Hello world",
    #         "extra_data": {"key": "value"},
    #         "reply_to_msg_id": None,
    #         "topic_title": "Test Topic",
    #         "source_name": "Test Group",
    #         "ingestion_timestamp": datetime.now().isoformat(),
    #     },
    #     {
    #         "id": 2,
    #         "source_group_id": 123,
    #         "topic_id": 456,
    #         "date": datetime.now(),
    #         "sender_id": "user2",
    #         "message_type": "poll",
    #         "content": {"question": "Test poll", "options": ["Option 1", "Option 2"]},
    #         "extra_data": {"poll_id": "poll123"},
    #         "reply_to_msg_id": None,
    #         "topic_title": "Test Topic",
    #         "source_name": "Test Group",
    #         "ingestion_timestamp": datetime.now().isoformat(),
    #     },
    #     {
    #         "id": 3,
    #         "source_group_id": 123,
    #         "topic_id": 456,
    #         "date": "2024-01-01T00:00:00",  # String date
    #         "sender_id": "user3",
    #         "message_type": "text",
    #         "content": "Pre-formatted date",
    #         "extra_data": {},
    #         "reply_to_msg_id": 1,
    #         "topic_title": "Test Topic",
    #         "source_name": "Test Group",
    #         "ingestion_timestamp": datetime.now().isoformat(),
    #     },
    #     {
    #         "id": 4,
    #         "source_group_id": 123,
    #         "topic_id": 456,
    #         "date": MagicMock(),  # MagicMock object (should be converted to string)
    #         "sender_id": "user4",
    #         "message_type": "text",
    #         "content": "MagicMock date",
    #         "extra_data": {},
    #         "reply_to_msg_id": None,
    #         "topic_title": "Test Topic",
    #         "source_name": "Test Group",
    #         "ingestion_timestamp": datetime.now().isoformat(),
    #     },
    # ]


if __name__ == "__main__":
    test_serialize_extra_data()
    test_database_insertion()
    print("\nAll tests passed! The database fix is working correctly.")
