import unittest

from src.synthesis.data_transformer import DataTransformer


class TestDataTransformer(unittest.TestCase):
    def setUp(self):
        self.transformer = DataTransformer()

    def test_transform_database_messages_empty_list(self):
        """Test transforming an empty list of messages."""
        result = self.transformer.transform_database_messages([])
        self.assertEqual(result, [])

    def test_transform_database_messages_single_message(self):
        """Test transforming a single message."""
        messages = [
            {
                "id": 1,
                "source_group_id": 100,
                "topic_id": 0,
                "date": "2024-01-01T10:00:00",
                "sender_id": "user1",
                "message_type": "text",
                "content": "Hello world",
                "extra_data": "{}",
                "reply_to_msg_id": None,
                "topic_title": "General",
                "source_name": "Test Group",
                "ingestion_timestamp": "2024-01-01T10:00:00",
            }
        ]

        result = self.transformer.transform_database_messages(messages)

        expected_result = [
            {
                "ingestion_timestamp": "2024-01-01T10:00:00",
                "ingestion_hash": "100_0",
                "source_files": ["Test Group"],
                "source_names": ["Test Group"],
                "conversation": [
                    {
                        "id": 1,
                        "date": "2024-01-01T10:00:00",
                        "sender_id": "user1",
                        "content": "Hello world",
                        "normalized_values": [],
                    }
                ],
                "message_count": 1,
            }
        ]

        self.assertEqual(result, expected_result)

    def test_transform_database_messages_multiple_messages_same_conversation(self):
        """Test transforming multiple messages from the same conversation."""
        messages = [
            {
                "id": 1,
                "source_group_id": 100,
                "topic_id": 0,
                "date": "2024-01-01T10:00:00",
                "sender_id": "user1",
                "message_type": "text",
                "content": "Hello world",
                "extra_data": "{}",
                "reply_to_msg_id": None,
                "topic_title": "General",
                "source_name": "Test Group",
                "ingestion_timestamp": "2024-01-01T10:00:00",
            },
            {
                "id": 2,
                "source_group_id": 100,
                "topic_id": 0,
                "date": "2024-01-01T10:01:00",
                "sender_id": "user2",
                "message_type": "text",
                "content": "Hi there",
                "extra_data": "{}",
                "reply_to_msg_id": 1,
                "topic_title": "General",
                "source_name": "Test Group",
                "ingestion_timestamp": "2024-01-01T10:01:00",
            },
        ]

        result = self.transformer.transform_database_messages(messages)

        expected_result = [
            {
                "ingestion_timestamp": "2024-01-01T10:00:00",
                "ingestion_hash": "100_0",
                "source_files": ["Test Group"],
                "source_names": ["Test Group"],
                "conversation": [
                    {
                        "id": 1,
                        "date": "2024-01-01T10:00:00",
                        "sender_id": "user1",
                        "content": "Hello world",
                        "normalized_values": [],
                    },
                    {
                        "id": 2,
                        "date": "2024-01-01T10:01:00",
                        "sender_id": "user2",
                        "content": "Hi there",
                        "normalized_values": [],
                    },
                ],
                "message_count": 2,
            }
        ]

        # Sort conversations by ingestion_hash for consistent comparison
        result.sort(key=lambda x: x["ingestion_hash"])
        expected_result.sort(key=lambda x: x["ingestion_hash"])

        self.assertEqual(result, expected_result)

    def test_transform_database_messages_multiple_conversations(self):
        """Test transforming messages from multiple conversations."""
        messages = [
            {
                "id": 1,
                "source_group_id": 100,
                "topic_id": 0,
                "date": "2024-01-01T10:00:00",
                "sender_id": "user1",
                "message_type": "text",
                "content": "Hello world",
                "extra_data": "{}",
                "reply_to_msg_id": None,
                "topic_title": "General",
                "source_name": "Test Group",
                "ingestion_timestamp": "2024-01-01T10:00:00",
            },
            {
                "id": 2,
                "source_group_id": 100,
                "topic_id": 1,
                "date": "2024-01-01T10:01:00",
                "sender_id": "user2",
                "message_type": "text",
                "content": "Topic message",
                "extra_data": "{}",
                "reply_to_msg_id": None,
                "topic_title": "Topic 1",
                "source_name": "Test Group",
                "ingestion_timestamp": "2024-01-01T10:01:00",
            },
        ]

        result = self.transformer.transform_database_messages(messages)

        expected_result = [
            {
                "ingestion_timestamp": "2024-01-01T10:00:00",
                "ingestion_hash": "100_0",
                "source_files": ["Test Group"],
                "source_names": ["Test Group"],
                "conversation": [
                    {
                        "id": 1,
                        "date": "2024-01-01T10:00:00",
                        "sender_id": "user1",
                        "content": "Hello world",
                        "normalized_values": [],
                    }
                ],
                "message_count": 1,
            },
            {
                "ingestion_timestamp": "2024-01-01T10:01:00",
                "ingestion_hash": "100_1",
                "source_files": ["Test Group"],
                "source_names": ["Test Group"],
                "conversation": [
                    {
                        "id": 2,
                        "date": "2024-01-01T10:01:00",
                        "sender_id": "user2",
                        "content": "Topic message",
                        "normalized_values": [],
                    }
                ],
                "message_count": 1,
            },
        ]

        # Sort conversations by ingestion_hash for consistent comparison
        result.sort(key=lambda x: x["ingestion_hash"])
        expected_result.sort(key=lambda x: x["ingestion_hash"])

        self.assertEqual(result, expected_result)

    def test_normalize_numbers_with_values(self):
        """Test normalizing numbers from text content."""
        from src.core.text_utils import normalize_numbers

        text = "The price is 100 rs and distance is 5.5 km"
        result = normalize_numbers(text)

        expected_result = [
            {"span": "100 rs", "value": 100.0, "unit": "rs", "confidence": "medium"},
            {"span": "5.5 km", "value": 5.5, "unit": "km", "confidence": "medium"},
        ]

        self.assertEqual(result, expected_result)

    def test_normalize_numbers_no_values(self):
        """Test normalizing text with no numeric values."""
        from src.core.text_utils import normalize_numbers

        text = "Hello world"
        result = normalize_numbers(text)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
