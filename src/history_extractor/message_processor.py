import re
from typing import Any, Dict, Tuple

import telethon


def get_message_details(msg) -> Tuple[str, Any, Dict[str, Any]]:
    """
    Extracts structured details (type, content, etc.) from a message.

    Args:
        msg: The message object to process.

    Returns:
        A tuple containing the message type, content, and extra data.
    """
    print(f"msg.media: {msg.media}")
    content = msg.text
    extra_data = {}
    url_regex = r"https?://[^\s]+"

    # --- Poll Detection ---
    if isinstance(msg.media, telethon.tl.types.MessageMediaPoll):
        poll = msg.media.poll
        results = msg.media.results

        options = []
        if results and results.results:
            for answer, result in zip(poll.answers, results.results):
                option = {"text": answer.text, "voters": result.voters}
                if hasattr(result, "chosen") and result.chosen:
                    option["chosen"] = True
                if hasattr(result, "correct") and result.correct:
                    option["correct"] = True
                options.append(option)
        else:
            options = [{"text": answer.text, "voters": 0} for answer in poll.answers]

        content = {
            "question": str(poll.question.text),
            "options": [
                {"text": str(o["text"].text), "voters": o["voters"]} for o in options
            ],
            "total_voters": results.total_voters if results else 0,
            "is_quiz": poll.quiz,
            "is_anonymous": not poll.public_voters,
        }
        return "poll", content, {}

    # --- Unified Link Detection ---
    urls = set()
    # 1. From entities
    if msg.entities:
        for entity in msg.entities:
            if isinstance(entity, telethon.tl.types.MessageEntityTextUrl):
                urls.add(entity.url)
            elif isinstance(entity, telethon.tl.types.MessageEntityUrl):
                offset, length = entity.offset, entity.length
                urls.add(msg.text[offset : offset + length])
    # 2. From WebPage media
    if (
        isinstance(msg.media, telethon.tl.types.MessageMediaWebPage)
        and msg.media.webpage.url
    ):
        urls.add(msg.media.webpage.url)
    # 3. Fallback to regex
    if msg.text:
        urls.update(re.findall(url_regex, msg.text))

    if urls:
        content = msg.text if msg.text else next(iter(urls))  # Use first URL if no text
        extra_data["urls"] = list(urls)
        return "link", content, extra_data

    # Default to text message if no other type is detected
    return "text", content, extra_data
