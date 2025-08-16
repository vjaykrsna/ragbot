import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from src.core.rag_pipeline import RAGPipeline
from src.utils import config
from src.utils.logger import setup_logging


setup_logging()
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        "Hi! I am your RAG-powered Telegram bot. Send me a question about our chat history."
    )


async def _run_query_in_executor(rag_pipeline: RAGPipeline, text: str) -> str:
    loop = asyncio.get_running_loop()
    # Use a threadpool for blocking I/O / CPU-bound library calls
    with ThreadPoolExecutor(max_workers=1) as ex:
        return await loop.run_in_executor(ex, lambda: rag_pipeline.query(text))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and reply using the RAG pipeline.

    The RAG pipeline methods may be blocking (third-party libs), so we
    run them in a thread executor to avoid blocking the event loop.
    """
    rag_pipeline: Optional[RAGPipeline] = context.bot_data.get("rag_pipeline")
    if rag_pipeline is None:
        await update.message.reply_text(
            "The knowledge base is not available right now. Try again later."
        )
        return

    user_message = update.message.text or ""
    logger.info("Received message: %s", user_message)

    # Send "typing..." action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = await _run_query_in_executor(rag_pipeline, user_message)
    except Exception as exc:  # preserve non-fatal behaviour
        logger.exception("Error while generating response: %s", exc)
        response = "I encountered an error while trying to generate a response."

    await update.message.reply_text(response)


def main() -> None:
    """Initialize and run the Telegram bot application."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set; aborting bot startup.")
        return

    application: Application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Initialize the RAG pipeline once (blocking) and add it to bot_data
    try:
        rag_pipeline = RAGPipeline()
        application.bot_data["rag_pipeline"] = rag_pipeline
        logger.info("RAG pipeline initialized successfully.")
    except Exception:
        logger.exception("Could not initialize RAG pipeline")
        application.bot_data["rag_pipeline"] = None

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting bot...")
    application.run_polling()
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
