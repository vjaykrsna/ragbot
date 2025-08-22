from typing import Any, Dict, Tuple


def get_message_details(msg) -> Tuple[str, Any, Dict[str, Any]]:
    """
    Extracts structured details (type, content, etc.) from a message.

    Args:
        msg: The message object to process.

    Returns:
        A tuple containing the message type, content, and extra data.
    """
    try:
        # Handle empty/invalid messages
        if not msg:
            return "text", "", {}

        # Extract text content safely
        content = getattr(msg, "text", "") or ""

        # Prepare extra data with common message attributes
        extra_data = {
            "has_protected_content": getattr(msg, "has_protected_content", False),
            "edit_date": getattr(msg, "edit_date", None),
            "views": getattr(msg, "views", None),
            "forwards": getattr(msg, "forwards", None),
            "message_thread_id": getattr(msg, "message_thread_id", None),
            "sender_chat_id": getattr(msg.sender_chat, "id", None)
            if getattr(msg, "sender_chat", None)
            else None,
            "sender_chat_title": getattr(msg.sender_chat, "title", None)
            if getattr(msg, "sender_chat", None)
            else None,
        }

        # --- Poll Detection for Pyrogram ---
        if hasattr(msg, "poll") and msg.poll:
            try:
                poll = msg.poll

                # Extract poll options
                options = []
                for option in getattr(poll, "options", []):
                    option_dict = {
                        "text": getattr(option, "text", ""),
                        "voter_count": getattr(option, "voter_count", 0),
                    }
                    # Add other option attributes if available
                    if hasattr(option, "correct"):
                        option_dict["correct"] = getattr(option, "correct", False)
                    options.append(option_dict)

                poll_content = {
                    "question": getattr(poll, "question", ""),
                    "options": options,
                    "total_voter_count": getattr(poll, "total_voter_count", 0),
                    "is_quiz": getattr(poll, "is_quiz", False),
                    "is_anonymous": getattr(poll, "is_anonymous", True),
                    "close_period": getattr(poll, "close_period", None),
                    "close_date": getattr(poll, "close_date", None),
                }

                # Add poll-specific data to extra_data
                extra_data["poll_id"] = getattr(poll, "id", None)

                return "poll", poll_content, extra_data

            except Exception:
                # If poll processing fails, fall back to text but keep extra_data
                return "text", content, extra_data

        # Default to text message if no other type is detected
        return "text", content, extra_data

    except Exception as e:
        # Ultimate fallback for any unexpected errors
        return "text", "", {"error": str(e)}
