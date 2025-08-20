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

        # --- Poll Detection ---
        if hasattr(msg, "media") and msg.media and hasattr(msg.media, "poll"):
            try:
                poll = msg.media.poll
                results = msg.media.results

                if (
                    not poll
                    or not hasattr(poll, "question")
                    or not hasattr(poll, "answers")
                ):
                    return "text", content, {}

                options = []
                if results and hasattr(results, "results") and results.results:
                    try:
                        for answer, result in zip(poll.answers, results.results):
                            if not answer or not hasattr(answer, "text"):
                                continue
                            option = {
                                "text": getattr(answer.text, "text", str(answer.text)),
                                "voters": getattr(result, "voters", 0),
                            }
                            if hasattr(result, "chosen") and result.chosen:
                                option["chosen"] = True
                            if hasattr(result, "correct") and result.correct:
                                option["correct"] = True
                            options.append(option)
                    except (AttributeError, TypeError, ValueError):
                        # Fallback: create options without results
                        options = [
                            {
                                "text": getattr(answer.text, "text", str(answer.text)),
                                "voters": 0,
                            }
                            for answer in poll.answers
                            if answer and hasattr(answer, "text")
                        ]
                else:
                    # No results available
                    options = [
                        {
                            "text": getattr(answer.text, "text", str(answer.text)),
                            "voters": 0,
                        }
                        for answer in poll.answers
                        if answer and hasattr(answer, "text")
                    ]

                poll_content = {
                    "question": getattr(poll.question, "text", str(poll.question))
                    if poll.question
                    else "",
                    "options": options,
                    "total_voters": getattr(results, "total_voters", 0)
                    if results
                    else 0,
                    "is_quiz": getattr(poll, "quiz", False),
                    "is_anonymous": not getattr(poll, "public_voters", True),
                }
                return "poll", poll_content, {}

            except Exception:
                # If poll processing fails, fall back to text
                return "text", content, {}

        # Default to text message if no other type is detected
        return "text", content, {}

    except Exception:
        # Ultimate fallback for any unexpected errors
        return "text", "", {}
