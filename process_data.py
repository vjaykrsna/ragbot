import os
import json
import glob
import logging
from datetime import datetime

# ==============================================================================
# 1. SETUP
# ==============================================================================

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[logging.FileHandler("processing.log"), logging.StreamHandler()],
)

# --- Constants ---
INPUT_DIR = "extracted_data"
OUTPUT_DIR = "processed_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==============================================================================
# 2. DATA LOADING
# ==============================================================================


def load_raw_data(input_dir):
    """Loads all .jsonl files from the input directory."""
    all_messages = []
    jsonl_files = glob.glob(os.path.join(input_dir, "*.jsonl"))

    if not jsonl_files:
        logging.warning(
            f"No .jsonl files found in '{input_dir}'. Please run the extraction script first."
        )
        return []

    logging.info(f"Found {len(jsonl_files)} data files to process.")

    for filepath in jsonl_files:
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                try:
                    all_messages.append(json.loads(line))
                except json.JSONDecodeError:
                    logging.warning(
                        f"Skipping corrupted JSON on line {i} in {filepath}"
                    )

    # --- Data Validation ---
    initial_count = len(all_messages)
    # Remove messages that don't have a date for sorting
    all_messages = [m for m in all_messages if "date" in m and m["date"]]
    if len(all_messages) < initial_count:
        logging.warning(
            f"Removed {initial_count - len(all_messages)} messages with missing dates."
        )

    all_messages.sort(key=lambda x: x["date"])
    logging.info(f"Loaded and sorted a total of {len(all_messages)} messages.")
    return all_messages


# ==============================================================================
# 3. CORE PROCESSING FUNCTIONS
# ==============================================================================


def anonymize_and_clean(messages):
    """Anonymizes sender IDs and performs initial cleaning."""
    anonymized_messages = []
    user_map = {}
    user_counter = 1
    dropped_count = 0

    logging.info("Anonymizing user IDs and performing initial cleaning...")

    for msg in messages:
        if not msg.get("sender_id") or not msg.get("content"):
            dropped_count += 1
            continue

        sender_id = msg["sender_id"]
        if sender_id not in user_map:
            user_map[sender_id] = f"User_{user_counter}"
            user_counter += 1

        new_msg = msg.copy()
        new_msg["sender_id"] = user_map[sender_id]
        anonymized_messages.append(new_msg)

    logging.info(
        f"Dropped {dropped_count} messages during cleaning (missing sender or content)."
    )
    return anonymized_messages, user_map


def group_into_conversations(messages, time_threshold_seconds=300):
    """Groups messages into conversation threads."""
    logging.info("Grouping messages into conversation threads...")

    threads = {}
    message_map = {msg["id"]: msg for msg in messages}

    for msg in messages:
        reply_id = msg.get("reply_to_msg_id")
        if reply_id and reply_id in message_map:
            root_id = reply_id
            while (
                message_map[root_id].get("reply_to_msg_id")
                and message_map[root_id].get("reply_to_msg_id") in message_map
            ):
                root_id = message_map[root_id]["reply_to_msg_id"]

            if root_id not in threads:
                threads[root_id] = {message_map[root_id]["id"]}  # Use a set for IDs
            threads[root_id].add(msg["id"])

    conversations = []
    replied_ids = set()
    for root_id, message_ids in threads.items():
        thread_messages = [
            message_map[mid] for mid in message_ids if mid in message_map
        ]
        thread_messages.sort(key=lambda x: x["date"])
        conversations.append(thread_messages)
        replied_ids.update(message_ids)

    standalone_messages = [msg for msg in messages if msg["id"] not in replied_ids]

    if standalone_messages:
        current_conversation = [standalone_messages[0]]
        for i in range(1, len(standalone_messages)):
            prev_msg = standalone_messages[i - 1]
            current_msg = standalone_messages[i]

            try:
                time_diff = (
                    datetime.fromisoformat(current_msg["date"])
                    - datetime.fromisoformat(prev_msg["date"])
                ).total_seconds()
                if (
                    prev_msg["sender_id"] == current_msg["sender_id"]
                    and time_diff < time_threshold_seconds
                ):
                    current_conversation.append(current_msg)
                else:
                    conversations.append(current_conversation)
                    current_conversation = [current_msg]
            except (ValueError, TypeError) as e:
                logging.warning(
                    f"Could not calculate time difference for message {current_msg.get('id')}. Error: {e}"
                )
                conversations.append(current_conversation)
                current_conversation = [current_msg]

        conversations.append(current_conversation)

    conversations.sort(key=lambda conv: conv[0]["date"])
    logging.info(f"Grouped messages into {len(conversations)} conversations.")
    return conversations


# ==============================================================================
# 4. DATA SAVING
# ==============================================================================


def save_processed_data(conversations, user_map):
    """Saves the processed data and the user map."""
    # Save conversations
    conv_path = os.path.join(OUTPUT_DIR, "processed_conversations.json")
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved {len(conversations)} conversation threads to {conv_path}")

    # Save user map
    map_path = os.path.join(OUTPUT_DIR, "user_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(user_map, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved user map with {len(user_map)} users to {map_path}")


# ==============================================================================
# 5. MAIN ORCHESTRATION
# ==============================================================================


def main():
    """Main function to orchestrate the data processing."""
    logging.info("🚀 Starting Phase 2: Data Processing & Knowledge Base Creation")

    try:
        raw_messages = load_raw_data(INPUT_DIR)
        if not raw_messages:
            return

        cleaned_messages, user_map = anonymize_and_clean(raw_messages)
        conversations = group_into_conversations(cleaned_messages)
        save_processed_data(conversations, user_map)

        logging.info("✅ Data processing complete.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
