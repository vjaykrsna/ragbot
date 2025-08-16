import os
import json
import re
import logging
from dotenv import load_dotenv
import telethon
import asyncio
from telethon.errors import FloodWaitError
from telethon.sync import TelegramClient
from telethon.tl.types import PeerChannel
from datetime import datetime
from telethon.tl.functions.channels import GetForumTopicsRequest
from tqdm.asyncio import tqdm_asyncio

# Load environment variables
load_dotenv()
api_id_env = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
if not api_id_env or not api_hash:
    raise RuntimeError("API_ID and API_HASH must be set in the environment to run extraction.")
api_id = int(api_id_env)

from src.utils import config

# Use project root to store session files so they are persistent across runs
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
session_path = os.path.join(project_root, config.SESSION_NAME)
client = TelegramClient(session_path, api_id, api_hash)

os.makedirs(config.RAW_DATA_DIR, exist_ok=True)


# HELPERS
def safe_filename(s):
    """Sanitizes a string into a valid filename."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)


def normalize_title(title):
    """Converts a message title entity to a string."""
    try:
        return title.text if hasattr(title, "text") else str(title)
    except Exception:
        return "UnknownTopic"


class TelegramObjectEncoder(json.JSONEncoder):
    """Custom JSON encoder for Telegram objects (e.g., datetime)."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)


# DATA STORAGE & PROGRESS
def save_message_jsonl(chat_title, topic_id, messages):
    """Saves messages to a .jsonl file with a unique name."""
    safe_title = safe_filename(chat_title)
    # Include topic_id to prevent filename collisions for topics processed in the same second
    filename = f"{safe_title}_{topic_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = os.path.join(config.RAW_DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in messages:
            json.dump(msg, f, ensure_ascii=False, cls=TelegramObjectEncoder)
            f.write("\n")
    logging.info(f"✅ Saved {len(messages)} messages to {filepath}")


def load_last_msg_ids():
    """Loads the last processed message ID for each topic from a file."""
    if os.path.exists(config.TRACKING_FILE):
        with open(config.TRACKING_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}  # Return empty dict if file is corrupted
    return {}


def save_last_msg_ids(data):
    """Saves the last processed message ID for each topic to a file."""
    with open(config.TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2)


# CORE MESSAGE PROCESSING
def get_message_details(msg):
    """Extracts structured details (type, content, etc.) from a message."""
    content = msg.text
    extra_data = {}
    url_regex = r"https?://[^\s]+"

    # --- Poll Detection ---
    if isinstance(msg.media, telethon.tl.types.MessageMediaPoll):
        poll = msg.media.poll
        content = poll.question
        extra_data["options"] = []
        if msg.media.results and msg.media.results.results:
            for answer, result in zip(poll.answers, msg.media.results.results):
                extra_data["options"].append({"text": answer.text, "voters": result.voters})
        else:
            extra_data["options"] = [{"text": answer.text, "voters": 0} for answer in poll.answers]
        return "poll", content, extra_data

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
    if isinstance(msg.media, telethon.tl.types.MessageMediaWebPage) and msg.media.webpage.url:
        urls.add(msg.media.webpage.url)
    # 3. Fallback to regex
    if msg.text:
        urls.update(re.findall(url_regex, msg.text))

    if urls:
        content = msg.text if msg.text else next(iter(urls)) # Use first URL if no text
        extra_data["urls"] = list(urls)
        return "link", content, extra_data

    # Default to text message if no other type is detected
    return "text", content, extra_data


async def extract_from_topic(entity, topic, last_msg_ids):
    """Extracts all new messages from a specific group topic."""
    messages = []
    group_id = entity.id
    topic_id = topic.id
    topic_title = normalize_title(getattr(topic, "title", "General"))
    last_id_key = f"{group_id}_{topic_id}"
    last_id = last_msg_ids.get(last_id_key, 0)
    max_id = 0

    logging.info(
        f"  - 📥 Extracting from topic: '{topic_title}' (ID: {topic_id}) [Since message ID > {last_id}]"
    )

    iterator_kwargs = {"min_id": last_id, "reverse": True}
    if topic_id != 0:  # 0 is the 'General' topic in non-forum groups
        iterator_kwargs["reply_to"] = topic_id

    async for msg in tqdm_asyncio(
        client.iter_messages(entity, **iterator_kwargs),
        desc=f"{topic_title:20.20}",
        unit="msg",
    ):
        if isinstance(msg, telethon.tl.types.MessageService):
            continue
        if not msg.text and not msg.media:
            continue

        try:
            message_type, content, extra_data = get_message_details(msg)
        except Exception:
            logging.exception(f"Failed to process message {msg.id}. Skipping.")
            continue

        if not content:
            continue

        messages.append(
            {
                "id": msg.id,
                "date": msg.date.isoformat(),
                "sender_id": msg.sender_id,
                "message_type": message_type,
                "content": content,
                "extra_data": extra_data,
                "reply_to_msg_id": msg.reply_to_msg_id,
                "topic_id": topic_id,
                "topic_title": topic_title,
            }
        )
        max_id = max(max_id, msg.id)

    if messages:
        full_title = f"{entity.title}_{topic_title}"
        save_message_jsonl(full_title, topic_id, messages)
        last_msg_ids[last_id_key] = max_id


async def extract_from_group_id(group_id, last_msg_ids):
    try:
        entity = await client.get_entity(group_id)
        logging.info(f"\nProcessing Group: {entity.title} (ID: {group_id})")
        if entity.forum:
            try:
                topics_result = await client(GetForumTopicsRequest(channel=entity, offset_date=datetime.now(), offset_id=0, offset_topic=0, limit=100))
                if topics_result and hasattr(topics_result, "topics"):
                    logging.info(f"Found {len(topics_result.topics)} topics. Iterating through them.")
                    for topic in topics_result.topics:
                        await extract_from_topic(entity, topic, last_msg_ids)
                else:
                    logging.info("  - Forum group with no topics found. Skipping.")
            except Exception:
                logging.exception(f"  - ❌ Error fetching topics for forum '{entity.title}'")
        else:
            logging.info("  - This is a regular group. Extracting from main chat.")
            general_topic = type("obj", (object,), {"id": 0, "title": "General"})()
            await extract_from_topic(entity, general_topic, last_msg_ids)
    except FloodWaitError as fwe:
        logging.warning(f"Flood wait error for group {group_id}. Waiting for {fwe.seconds} seconds.")
        await asyncio.sleep(fwe.seconds)
        await extract_from_group_id(group_id, last_msg_ids)  # Retry
    except Exception:
        logging.exception(f"❌ Error processing group {group_id}")


# MAIN ORCHESTRATION
async def main():
    """Orchestrates the Telegram message extraction process."""
    await client.start(phone=config.TELEGRAM_PHONE, password=config.TELEGRAM_PASSWORD)

    me = await client.get_me()
    logging.info(f"👤 Logged in as: {me.first_name} (@{me.username})")

    if not config.GROUP_IDS:
        logging.warning(
            "⚠️ No GROUP_IDS found in .env file. Please add the group/channel IDs to scrape."
        )
        return

    group_ids = config.GROUP_IDS
    last_msg_ids = load_last_msg_ids()

    for gid in group_ids:
        await extract_from_group_id(gid, last_msg_ids)

    save_last_msg_ids(last_msg_ids)

    await client.disconnect()
    logging.info("\n🎉 Extraction complete. Client disconnected.")


if __name__ == "__main__":
    # Using asyncio.run() is the modern way to run an async main function.
    asyncio.run(main())
