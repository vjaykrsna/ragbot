import os
import json
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import PeerChannel
from datetime import datetime
from tqdm.asyncio import tqdm_asyncio

# Load environment variables
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("ragbot_session", api_id, api_hash)

OUTPUT_DIR = "extracted_data"
TRACKING_FILE = "last_msg_ids.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_message_jsonl(chat_title, messages):
    filename = f"{chat_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in messages:
            json.dump(msg, f, ensure_ascii=False)
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


async def extract_from_group_id(group_id, last_msg_ids):
    messages = []
    try:
        # Let Telethon resolve the entity type automatically
        entity = await client.get_entity(group_id)
        title = entity.title or f"group_{group_id}"
        last_id = last_msg_ids.get(str(group_id), 0)
        max_id = 0  # Track max message ID in this run

        print(f"📥 Extracting from: {title} (ID: {group_id}) [Since message ID > {last_id}]")

        async for msg in tqdm_asyncio(client.iter_messages(entity, min_id=last_id, reverse=True), desc=f"{title}", unit="msg"):
            # Skip messages without text content
            if not msg.text:
                continue
            
            # Safely get sender ID
            sender_id = None
            if msg.sender:
                sender_id = msg.sender.id

            messages.append({
                "id": msg.id,
                "date": msg.date.isoformat(),
                "sender_id": sender_id,
                "text": msg.text,
                "reply_to_msg_id": msg.reply_to_msg_id
            })
            max_id = max(max_id, msg.id)

        if messages:
            save_message_jsonl(title, messages)
            last_msg_ids[str(group_id)] = max_id

    except Exception as e:
        print(f"❌ Error extracting from group {group_id}: {e}")


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
