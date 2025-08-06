import os
import json
import re
from dotenv import load_dotenv
import telethon
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


def safe_filename(s):
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)

def save_message_jsonl(chat_title, messages):
    safe_title = safe_filename(chat_title)
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in messages:
            json.dump(msg, f, ensure_ascii=False, cls=TelegramObjectEncoder)
            f.write("\n")
    print(f"✅ Saved {len(messages)} messages to {filepath}")


def load_last_msg_ids():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r") as f:
            return json.load(f)
    return {}


def save_last_msg_ids(data):
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2)


class TelegramObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return json.JSONEncoder.default(self, obj)

def normalize_title(title):
    """Safely convert a title (which may be an entity) to a string."""
    try:
        # Handles both strings and TextWithEntities objects
        return title.text if hasattr(title, 'text') else str(title)
    except Exception:
        return "UnknownTopic"

async def extract_from_topic(entity, topic, last_msg_ids):
    messages = []
    group_id = entity.id
    topic_id = topic.id
    topic_title = normalize_title(getattr(topic, "title", "Unknown"))
    last_id_key = f"{group_id}_{topic_id}"
    last_id = last_msg_ids.get(last_id_key, 0)
    max_id = 0

    print(f"  - 📥 Extracting from topic: '{topic_title}' (ID: {topic_id}) [Since message ID > {last_id}]")

    # Conditionally set the iterator to handle both topics and regular groups
    iterator_kwargs = {'min_id': last_id, 'reverse': True}
    if topic_id != 0:
        iterator_kwargs['reply_to'] = topic_id

    async for msg in tqdm_asyncio(client.iter_messages(entity, **iterator_kwargs), desc=f"{topic_title}", unit="msg"):
        if not msg.text and not msg.media:
            continue
        sender_id = msg.sender_id
        message_type = "text"
        content = msg.text
        extra_data = {}
        url_regex = r'https?://[^\s]+'
        if isinstance(msg.media, telethon.tl.types.MessageMediaPoll):
            message_type = "poll"
            poll = msg.media.poll
            content = poll.question # Keep the TextWithEntities object
            extra_data["options"] = [answer.text for answer in poll.answers]
        elif msg.entities or re.search(url_regex, msg.text or ''):
            urls = []
            if msg.entities:
                for message_entity in msg.entities:
                    if isinstance(message_entity, telethon.tl.types.MessageEntityTextUrl):
                        urls.append(message_entity.url)
                    elif isinstance(message_entity, telethon.tl.types.MessageEntityUrl):
                        offset, length = message_entity.offset, message_entity.length
                        urls.append(msg.text[offset:offset+length])
            if not urls:
                urls.extend(re.findall(url_regex, msg.text or ''))
            if urls:
                message_type = "link"
                content = msg.text if msg.text else urls[0]
                extra_data["urls"] = list(set(urls))
        # Only handle WebPage media (links), ignore others like photos/videos
        elif isinstance(msg.media, telethon.tl.types.MessageMediaWebPage):
            message_type = "link" # Treat it as a link
            content = msg.text
            # The URL is already captured by the regex logic above,
            # so we just need to ensure it's classified correctly.
        else:
            # This will now ignore all other media types
            pass

        if not content:
            continue
        messages.append({
            "id": msg.id,
            "date": msg.date.isoformat(),
            "sender_id": sender_id,
            "message_type": message_type,
            "content": content,
            "extra_data": extra_data,
            "reply_to_msg_id": msg.reply_to_msg_id,
            "topic_id": topic_id,
            "topic_title": topic_title
        })
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
                topics_result = await client(GetForumTopicsRequest(
                    channel=entity,
                    offset_date=datetime.now(),
                    offset_id=0,
                    offset_topic=0,
                    limit=100
                ))
                if topics_result and hasattr(topics_result, 'topics'):
                    print(f"Found {len(topics_result.topics)} topics. Iterating through them.")
                    for topic in topics_result.topics:
                        await extract_from_topic(entity, topic, last_msg_ids)
                else:
                     print("  - Forum group with no topics found. Skipping.")
            except Exception as topic_error:
                print(f"  - ❌ Error fetching topics for forum '{entity.title}': {topic_error}")
        else:
            # This is a regular group, not a forum.
            print("  - This is a regular group. Extracting from main chat.")
            general_topic = type('obj', (object,), {'id' : 0, 'title' : 'General'})()
            await extract_from_topic(entity, general_topic, last_msg_ids)
    except Exception as e:
        print(f"❌ Error processing group {group_id}: {e}")


async def main():
    me = await client.get_me()
    print(f"👤 Logged in as: {me.first_name} (@{me.username})")

    group_ids = [int(gid.strip()) for gid in os.getenv("GROUP_IDS", "").split(",") if gid.strip()]
    if not group_ids:
        print("⚠️ No GROUP_IDS found in .env")
        return

    last_msg_ids = load_last_msg_ids()

    for gid in group_ids:
        await extract_from_group_id(gid, last_msg_ids)

    save_last_msg_ids(last_msg_ids)


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
