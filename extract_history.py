import os
import json
import re
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
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("ragbot_session", api_id, api_hash)

OUTPUT_DIR = "extracted_data"
TRACKING_FILE = "last_msg_ids.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==============================================================================
# 1. HELPER FUNCTIONS & CLASSES
# ==============================================================================


def safe_filename(s):
    """Sanitizes a string to be a valid filename."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)


def normalize_title(title):
    """Safely convert a title (which may be an entity) to a string."""
    try:
        return title.text if hasattr(title, "text") else str(title)
    except Exception:
        return "UnknownTopic"


class TelegramObjectEncoder(json.JSONEncoder):
    """A custom JSON encoder for handling Telegram-specific objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)


# ==============================================================================
# 2. DATA STORAGE & PROGRESS TRACKING
# ==============================================================================


def save_message_jsonl(chat_title, messages):
    """Saves a list of messages to a .jsonl file."""
    safe_title = safe_filename(chat_title)
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in messages:
            json.dump(msg, f, ensure_ascii=False, cls=TelegramObjectEncoder)
            f.write("\n")
    print(f"✅ Saved {len(messages)} messages to {filepath}")


def load_last_msg_ids():
    """Loads the last processed message IDs from the tracking file."""
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}  # Return empty dict if file is corrupted
    return {}


def save_last_msg_ids(data):
    """Saves the last processed message IDs to the tracking file."""
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ==============================================================================
# 3. CORE MESSAGE PROCESSING LOGIC
# ==============================================================================


def get_message_details(msg):
    """
    Analyzes a message and extracts its type, content, and any extra data.
    Returns a tuple: (message_type, content, extra_data)
    """
    # Default to text message
    message_type = "text"
    content = msg.text
    extra_data = {}
    url_regex = r"https?://[^\s]+"

    # --- Poll Detection ---
    if isinstance(msg.media, telethon.tl.types.MessageMediaPoll):
        message_type = "poll"
        poll = msg.media.poll
        content = poll.question
        extra_data["options"] = []
        if msg.media.results and msg.media.results.results:
            for answer, result in zip(poll.answers, msg.media.results.results):
                extra_data["options"].append(
                    {"text": answer.text, "voters": result.voters}
                )
        else:
            extra_data["options"] = [
                {"text": answer.text, "voters": 0} for answer in poll.answers
            ]
        return message_type, content, extra_data

    # --- Link Detection (from entities or regex) ---
    urls = []
    if msg.entities:
        for entity in msg.entities:
            if isinstance(entity, telethon.tl.types.MessageEntityTextUrl):
                urls.append(entity.url)
            elif isinstance(entity, telethon.tl.types.MessageEntityUrl):
                offset, length = entity.offset, entity.length
                urls.append(msg.text[offset : offset + length])

    # Fallback to regex search if no entities found
    if not urls and msg.text:
        urls.extend(re.findall(url_regex, msg.text))

    if urls:
        message_type = "link"
        content = msg.text if msg.text else urls[0]
        extra_data["urls"] = list(set(urls))
        return message_type, content, extra_data

    # --- Link Detection (from WebPage media) ---
    if isinstance(msg.media, telethon.tl.types.MessageMediaWebPage):
        message_type = "link"
        # Content is already msg.text, no extra data needed as URL is in the text
        return message_type, content, extra_data

    # If no specific type is detected, return the default text type
    return message_type, content, extra_data


async def extract_from_topic(entity, topic, last_msg_ids):
    """Extracts messages from a specific topic within a group."""
    messages = []
    group_id = entity.id
    topic_id = topic.id
    topic_title = normalize_title(getattr(topic, "title", "General"))
    last_id_key = f"{group_id}_{topic_id}"
    last_id = last_msg_ids.get(last_id_key, 0)
    max_id = 0

    print(
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
        # Skip empty messages
        if not msg.text and not msg.media:
            continue

        message_type, content, extra_data = get_message_details(msg)

        # Skip messages that ended up with no content after processing
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
        save_message_jsonl(full_title, messages)
        last_msg_ids[last_id_key] = max_id


async def extract_from_group_id(group_id, last_msg_ids):
    try:
        entity = await client.get_entity(group_id)
        print(f"\nProcessing Group: {entity.title} (ID: {group_id})")
        # Check if the group is a forum
        if entity.forum:
            try:
                topics_result = await client(
                    GetForumTopicsRequest(
                        channel=entity,
                        offset_date=datetime.now(),
                        offset_id=0,
                        offset_topic=0,
                        limit=100,
                    )
                )
                if topics_result and hasattr(topics_result, "topics"):
                    print(
                        f"Found {len(topics_result.topics)} topics. Iterating through them."
                    )
                    for topic in topics_result.topics:
                        await extract_from_topic(entity, topic, last_msg_ids)
                else:
                    print("  - Forum group with no topics found. Skipping.")
            except Exception as topic_error:
                print(
                    f"  - ❌ Error fetching topics for forum '{entity.title}': {topic_error}"
                )
        else:
            # This is a regular group, not a forum.
            print("  - This is a regular group. Extracting from main chat.")
            general_topic = type("obj", (object,), {"id": 0, "title": "General"})()
            await extract_from_topic(entity, general_topic, last_msg_ids)
    except Exception as e:
        print(f"❌ Error processing group {group_id}: {e}")


# ==============================================================================
# 4. MAIN ORCHESTRATION
# ==============================================================================


async def main():
    """Main function to connect the client and orchestrate the extraction."""
    await client.start()

    me = await client.get_me()
    print(f"👤 Logged in as: {me.first_name} (@{me.username})")

    group_ids_str = os.getenv("GROUP_IDS")
    if not group_ids_str:
        print(
            "⚠️ No GROUP_IDS found in .env file. Please add the group/channel IDs to scrape."
        )
        return

    group_ids = [int(gid.strip()) for gid in group_ids_str.split(",") if gid.strip()]
    last_msg_ids = load_last_msg_ids()

    for gid in group_ids:
        await extract_from_group_id(gid, last_msg_ids)

    save_last_msg_ids(last_msg_ids)

    await client.disconnect()
    print("\n🎉 Extraction complete. Client disconnected.")


if __name__ == "__main__":
    # Using asyncio.run() is the modern way to run an async main function.
    asyncio.run(main())
