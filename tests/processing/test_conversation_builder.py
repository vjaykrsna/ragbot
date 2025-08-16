import unittest
from datetime import datetime, timedelta

from src.config.conversation import ConversationSettings
from src.processing.conversation_builder import ConversationBuilder


def create_message(msg_id, timestamp, sender, topic=None, content="..."):
    """Helper function to create a message dictionary."""
    msg = {
        "id": msg_id,
        "date": timestamp.isoformat(),
        "sender_id": sender,
        "content": content,
    }
    if topic:
        msg["topic_id"] = topic
    return msg


class TestConversationBuilder(unittest.TestCase):
    def setUp(self):
        self.settings = ConversationSettings(
            time_threshold_seconds=600,  # 10 minutes
            session_window_seconds=3600,  # 1 hour
        )
        self.builder = ConversationBuilder(self.settings)

    def test_groups_messages_by_time(self):
        """Messages close in time without a topic should be in one conversation."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1"),
            create_message(2, now + timedelta(seconds=10), "user2"),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 1)
        self.assertEqual(len(conversations[0]["conversation"]), 2)

    def test_separates_by_time_gap(self):
        """A long time gap should create a new conversation."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1"),
            create_message(2, now + timedelta(seconds=1000), "user2"),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 2)

    def test_groups_by_topic(self):
        """Messages with the same topic ID should be grouped."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1", topic=101),
            create_message(2, now + timedelta(seconds=10), "user2", topic=101),
            create_message(3, now + timedelta(seconds=20), "user1", topic=101),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 1)
        self.assertEqual(len(conversations[0]["conversation"]), 3)

    def test_separates_by_topic(self):
        """Messages with different topic IDs should be in separate conversations."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1", topic=101),
            create_message(2, now + timedelta(seconds=10), "user2", topic=102),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 2)


if __name__ == "__main__":
    unittest.main()
