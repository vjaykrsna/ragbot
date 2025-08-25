import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.core.app import initialize_app
from src.rag.rag_pipeline import RAGPipeline

logger = structlog.get_logger(__name__)


def validate_user_input(text: str) -> tuple[bool, str]:
    """
    Validate and sanitize user input for security.

    Args:
        text: The user input text

    Returns:
        Tuple of (is_valid, sanitized_text)
    """
    if not text or not text.strip():
        return False, "Message is empty"

    # Remove excessive whitespace
    sanitized = re.sub(r"\s+", " ", text.strip())

    # Check length limits (reasonable for chat messages)
    if len(sanitized) > 4000:
        return False, "Message too long (max 4000 characters)"

    # Basic content filtering - reject messages with suspicious patterns
    suspicious_patterns = [
        r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:text/html",  # Data URLs
        r"vbscript:",  # VBScript
        r"onload\s*=",  # Event handlers
        r"onerror\s*=",  # Error handlers
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            return False, "Message contains potentially harmful content"

    return True, sanitized


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

    # Validate and sanitize user input
    is_valid, sanitized_message = validate_user_input(user_message)
    if not is_valid:
        logger.warning("Invalid user input: %s", sanitized_message)
        await update.message.reply_text(
            f"Sorry, I can't process that message: {sanitized_message}"
        )
        return

    logger.info("Received message: %s", sanitized_message)

    # Send "typing..." action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        response = await _run_query_in_executor(rag_pipeline, sanitized_message)
    except Exception as exc:  # preserve non-fatal behaviour
        logger.exception("Error while generating response: %s", exc)
        response = "I encountered an error while trying to generate a response."

    await update.message.reply_text(response)


def main() -> None:
    """Initialize and run the Telegram bot application."""
    try:
        app_context = initialize_app()
        settings = app_context.settings

        if not settings.telegram.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not set; aborting bot startup.")
            return

        application: Application = (
            Application.builder().token(settings.telegram.bot_token).build()
        )

        # Initialize the RAG pipeline once (blocking) and add it to bot_data
        try:
            rag_pipeline = RAGPipeline(settings, app_context.db_client)
            application.bot_data["rag_pipeline"] = rag_pipeline
            logger.info("RAG pipeline initialized successfully.")
        except Exception:
            logger.exception("Could not initialize RAG pipeline")
            application.bot_data["rag_pipeline"] = None

        application.add_handler(CommandHandler("start", start))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        logger.info("Starting bot...")
        application.run_polling()

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
    except Exception:
        logger.exception("An unexpected error occurred during bot startup or runtime.")


if __name__ == "__main__":
    main()
