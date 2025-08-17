import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.main import handle_message, start


class TestBotHandlers(unittest.IsolatedAsyncioTestCase):
    async def test_start_command(self):
        """
        Test that the /start command replies with a welcome message.
        """
        # Arrange
        update = MagicMock()
        update.message = AsyncMock()
        context = MagicMock()

        # Act
        await start(update, context)

        # Assert
        update.message.reply_text.assert_awaited_once_with(
            "Hi! I am your RAG-powered Telegram bot. Send me a question about our chat history."
        )

    async def test_handle_message_happy_path(self):
        """
        Test the main message handler's successful execution path.
        """
        # Arrange
        mock_rag_pipeline = MagicMock()
        mock_rag_pipeline.query.return_value = "This is the RAG response."

        update = MagicMock()
        update.message = AsyncMock()
        update.message.text = "What is the meaning of life?"
        update.effective_chat.id = 12345

        context = MagicMock()
        context.bot_data = {"rag_pipeline": mock_rag_pipeline}
        context.bot = AsyncMock()

        # Act
        with patch(
            "src.bot.main._run_query_in_executor", new_callable=AsyncMock
        ) as mock_run_query:
            mock_run_query.return_value = "This is the RAG response."
            await handle_message(update, context)

        # Assert
        # 1. Check that the "typing" action was sent
        context.bot.send_chat_action.assert_awaited_once_with(
            chat_id=12345, action="typing"
        )

        # 2. Check that the RAG pipeline was queried
        mock_run_query.assert_awaited_once_with(
            mock_rag_pipeline, "What is the meaning of life?"
        )

        # 3. Check that the final response was sent
        update.message.reply_text.assert_awaited_once_with("This is the RAG response.")

    async def test_handle_message_no_rag_pipeline(self):
        """
        Test the message handler when the RAG pipeline is not available.
        """
        # Arrange
        update = MagicMock()
        update.message = AsyncMock()
        context = MagicMock()
        context.bot_data = {}  # No rag_pipeline

        # Act
        await handle_message(update, context)

        # Assert
        update.message.reply_text.assert_awaited_once_with(
            "The knowledge base is not available right now. Try again later."
        )

    async def test_handle_message_rag_query_fails(self):
        """
        Test the message handler when the RAG pipeline query raises an exception.
        """
        # Arrange
        mock_rag_pipeline = MagicMock()

        update = MagicMock()
        update.message = AsyncMock()
        update.message.text = "A failing question"
        update.effective_chat.id = 12345

        context = MagicMock()
        context.bot_data = {"rag_pipeline": mock_rag_pipeline}
        context.bot = AsyncMock()

        # Act
        with patch(
            "src.bot.main._run_query_in_executor", new_callable=AsyncMock
        ) as mock_run_query:
            mock_run_query.side_effect = Exception("RAG pipeline failed")
            await handle_message(update, context)

        # Assert
        update.message.reply_text.assert_awaited_once_with(
            "I encountered an error while trying to generate a response."
        )
