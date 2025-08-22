import unittest
from unittest.mock import MagicMock

from src.history_extractor.message_processor import get_message_details


class TestMessageProcessor(unittest.TestCase):
    def test_get_message_details_text(self):
        """
        Test processing a simple text message.
        """
        # Arrange
        mock_msg = MagicMock()
        mock_msg.text = "hello"
        mock_msg.media = None
        mock_msg.poll = None
        mock_msg.service = False

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "text")
        self.assertEqual(content, "hello")
        self.assertIsInstance(extra_data, dict)

    def test_get_message_details_empty_message(self):
        """
        Test processing an empty or invalid message.
        """
        # Arrange
        mock_msg = MagicMock()
        mock_msg.text = ""
        mock_msg.media = None
        mock_msg.poll = None
        mock_msg.service = False

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "text")
        self.assertEqual(content, "")
        self.assertIsInstance(extra_data, dict)

    def test_get_message_details_none_message(self):
        """
        Test processing a None message.
        """
        # Act
        msg_type, content, extra_data = get_message_details(None)

        # Assert
        self.assertEqual(msg_type, "text")
        self.assertEqual(content, "")
        self.assertEqual(extra_data, {})

    def test_get_message_details_poll(self):
        """
        Test processing a poll message.
        """
        # Arrange
        mock_msg = MagicMock()
        mock_msg.text = ""
        mock_msg.media = None
        mock_msg.service = False

        # Create a mock poll object with Pyrogram structure
        mock_poll = MagicMock()
        mock_poll.question = "What is your favorite color?"
        mock_poll.options = [
            MagicMock(text="Red", voter_count=10),
            MagicMock(text="Blue", voter_count=20),
        ]
        mock_poll.total_voter_count = 30
        mock_poll.is_quiz = False
        mock_poll.is_anonymous = True
        mock_poll.close_period = None
        mock_poll.close_date = None
        mock_poll.id = 12345

        mock_msg.poll = mock_poll

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "poll")
        self.assertEqual(content["question"], "What is your favorite color?")
        self.assertEqual(len(content["options"]), 2)
        self.assertEqual(content["total_voter_count"], 30)
        self.assertEqual(extra_data["poll_id"], 12345)
