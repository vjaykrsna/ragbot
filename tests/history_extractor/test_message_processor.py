import unittest
from unittest.mock import MagicMock

import telethon

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
        mock_msg.entities = None

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "text")
        self.assertEqual(content, "hello")
        self.assertEqual(extra_data, {})

    def test_get_message_details_link(self):
        """
        Test processing a message with a link.
        """
        # Arrange
        mock_msg = MagicMock()
        mock_msg.text = "check out this link: https://example.com"
        mock_msg.media = None
        mock_msg.entities = [telethon.tl.types.MessageEntityUrl(offset=21, length=19)]

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "link")
        self.assertEqual(content, "check out this link: https://example.com")
        self.assertEqual(extra_data, {"urls": ["https://example.com"]})

    def test_get_message_details_poll(self):
        """
        Test processing a poll message.
        """
        # Arrange
        mock_msg = MagicMock()
        mock_msg.text = ""
        mock_poll = MagicMock()
        mock_poll.question.text = "What is your favorite color?"
        mock_poll.answers = [
            MagicMock(),
            MagicMock(),
        ]
        mock_poll.answers[0].text.text = "Red"
        mock_poll.answers[1].text.text = "Blue"
        mock_poll.quiz = False
        mock_poll.public_voters = True
        mock_results = MagicMock()
        mock_results.results = [
            MagicMock(voters=10),
            MagicMock(voters=20),
        ]
        mock_results.total_voters = 30
        mock_media = MagicMock(spec=telethon.tl.types.MessageMediaPoll)
        mock_media.poll = mock_poll
        mock_media.results = mock_results
        mock_msg.media = mock_media

        # Act
        msg_type, content, extra_data = get_message_details(mock_msg)

        # Assert
        self.assertEqual(msg_type, "poll")
        self.assertEqual(content["question"], "What is your favorite color?")
        self.assertEqual(len(content["options"]), 2)
        self.assertEqual(content["total_voters"], 30)
