import unittest
from datetime import datetime, timedelta

from src.core.config import ConversationSettings
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

    def test_groups_by_direct_reply(self):
        """Messages that are direct replies should be grouped, even with a time gap."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1"),
            create_message(2, now + timedelta(seconds=1000), "user2"),
            create_message(
                3,
                now + timedelta(seconds=1010),
                "user1",
                content="replying",
            ),
        ]
        # Manually add the reply link
        messages[2]["reply_to_msg_id"] = 1

        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(
            len(conversations), 2
        )  # The reply should merge with the first conversation
        self.assertEqual(len(conversations[0]["conversation"]), 2)
        self.assertEqual(conversations[0]["conversation"][1]["id"], 3)

    def test_flushes_expired_conversations(self):
        """Conversations should be flushed if they exceed the session window."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1"),
            create_message(
                2,
                now + timedelta(seconds=self.settings.session_window_seconds + 1),
                "user2",
            ),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 2)

    def test_handles_structured_content(self):
        """The envelope creator should correctly format structured content like polls."""
        now = datetime.now()
        poll_content = {
            "question": "Favorite Color?",
            "options": [{"text": "Blue", "voters": 1}, {"text": "Red", "voters": 2}],
            "total_voters": 3,
        }
        # Create two sets of messages: one with a poll dict, one with the expected string.
        # The goal is to ensure they produce the same ingestion hash.
        poll_content = {
            "question": "Favorite Color?",
            "options": [{"text": "Blue", "voters": 1}, {"text": "Red", "voters": 2}],
            "total_voters": 3,
        }
        messages_with_poll = [create_message(1, now, "user1", content=poll_content)]

        expected_string = (
            "Poll: Favorite Color?\n- Blue (1 votes)\n- Red (2 votes)\nTotal Voters: 3"
        )
        messages_with_string = [
            create_message(1, now, "user1", content=expected_string)
        ]

        # Process the first stream
        builder1 = ConversationBuilder(self.settings)
        conversations1 = list(builder1.process_stream(iter(messages_with_poll)))
        hash1 = conversations1[0]["ingestion_hash"]

        # Process the second stream
        builder2 = ConversationBuilder(self.settings)
        conversations2 = list(builder2.process_stream(iter(messages_with_string)))
        hash2 = conversations2[0]["ingestion_hash"]

        self.assertEqual(hash1, hash2)
        self.assertIsNotNone(hash1)

    def test_handles_empty_content(self):
        """Messages with no content should be handled gracefully."""
        now = datetime.now()
        messages = [
            create_message(1, now, "user1", content=""),
            create_message(2, now + timedelta(seconds=10), "user2", content=None),
        ]
        conversations = list(self.builder.process_stream(iter(messages)))
        self.assertEqual(len(conversations), 1)
        self.assertEqual(len(conversations[0]["conversation"]), 2)
