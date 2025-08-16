import glob
import gzip
import hashlib
import heapq
import json
import logging
import os
import re
import tempfile
from collections import OrderedDict, deque
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

from dateutil.parser import isoparse

from src.utils import config
from src.utils.logger import setup_logging

RAW_DIR = config.RAW_DATA_DIR
PROCESSED_DIR = config.PROCESSED_DATA_DIR
OUT_CONV_FILE = os.path.join(PROCESSED_DIR, config.PROCESSED_CONVERSATIONS_FILE)
OUT_USER_MAP_FILE = os.path.join(PROCESSED_DIR, config.USER_MAP_FILE)

# Tuning knobs (with safe fallbacks if missing in config)
CHUNK_SIZE = getattr(config, "STREAM_CHUNK_SIZE", 50_000)  # messages per sort-chunk
USE_GZIP = getattr(config, "STREAM_GZIP_TEMP", True)
MAX_MESSAGE_MAP_SIZE = getattr(
    config, "MAX_MESSAGE_MAP_SIZE", 200_000
)  # recent msgs we can reference by id
MAX_ACTIVE_CONVERSATIONS = getattr(config, "MAX_ACTIVE_CONVERSATIONS", 10_000)

TIME_THRESHOLD_SECONDS = getattr(config, "CONVERSATION_TIME_THRESHOLD_SECONDS", 600)
SESSION_WINDOW_SECONDS = getattr(config, "SESSION_WINDOW_SECONDS", 3600)

# Centralized logging
setup_logging()
os.makedirs(PROCESSED_DIR, exist_ok=True)

# --------------------------- Utilities ---------------------------


def safe_json_loads(line: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def parse_dt(dt: str) -> datetime:
# RFC/ISO strings supported by isoparse
    return isoparse(dt)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def open_temp(path: str, mode: str):
    if USE_GZIP:
        return gzip.open(path, mode + "t", encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def temp_suffix() -> str:
    return ".jsonl.gz" if USE_GZIP else ".jsonl"


# ------------- Anonymization map (stable across runs) ----------


def load_user_map() -> Tuple[Dict[str, str], int]:
    if os.path.exists(OUT_USER_MAP_FILE):
        try:
            with open(OUT_USER_MAP_FILE, "r", encoding="utf-8") as f:
                m = json.load(f)
# derive next counter from existing
                max_n = 0
                for v in m.values():
                    if isinstance(v, str) and v.startswith("User_"):
                        try:
                            n = int(v.split("_", 1)[1])
                            if n > max_n:
                                max_n = n
                        except Exception:
                            pass
                return m, max_n + 1
        except Exception:
            logging.warning("User map file corrupted; starting fresh.")
    return {}, 1


def persist_user_map(user_map: Dict[str, str]) -> None:
    with open(OUT_USER_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(user_map, f, ensure_ascii=False, indent=2)


# ---------------- Streaming readers ------------------------


def iter_jsonl_files(raw_dir: str) -> List[str]:
    files = sorted(glob.glob(os.path.join(raw_dir, "*.jsonl")))
    if not files:
        logging.warning(f"No .jsonl files found in '{raw_dir}'. Run extraction first.")
    else:
        logging.info(f"Found {len(files)} raw files.")
    return files


def iter_messages_from_file(path: str) -> Generator[Dict[str, Any], None, None]:
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            rec = safe_json_loads(line)
            if not rec:
                logging.warning(f"Skipping corrupted JSON on line {i} in {path}")
                continue
            if not rec.get("date"):
                continue
            yield rec


# ------------- External sort in chunks ------------------


def write_sorted_chunks(files: List[str]) -> List[str]:
    """
    Read all raw files in streaming mode, collect up to CHUNK_SIZE messages,
    sort by date, write to a temp chunk file (optionally gzipped). Return paths.
    """
    chunk_paths: List[str] = []
    buf: List[Tuple[str, str]] = []  # (date_iso, json_line)
    total = 0

    def flush_chunk() -> None:
        nonlocal buf
        if not buf:
            return
        buf.sort(key=lambda x: x[0])  # sort by date string
        fd, tmp_path = tempfile.mkstemp(suffix=temp_suffix(), prefix="chunk_")
        os.close(fd)
        with open_temp(tmp_path, "w") as w:
            for _, line in buf:
                w.write(line)
                if not line.endswith("\n"):
                    w.write("\n")
        chunk_paths.append(tmp_path)
        logging.info(f"Wrote sorted chunk with {len(buf)} msgs -> {tmp_path}")
        buf = []

    for fp in files:
        for rec in iter_messages_from_file(fp):
            try:
                dt = parse_dt(rec["date"])
            except Exception:
                continue
            buf.append((iso(dt), json.dumps(rec, ensure_ascii=False)))
            total += 1
            if len(buf) >= CHUNK_SIZE:
                flush_chunk()
    flush_chunk()
    logging.info(f"Prepared {len(chunk_paths)} sorted chunk(s) from {total} messages.")
    return chunk_paths


# ------------ Merge stage (k-way merge of sorted chunks) ------


def iter_sorted_records(
    chunk_paths: List[str],
) -> Generator[Dict[str, Any], None, None]:
    """
    K-way merge of sorted chunk files without loading them fully.
    """
    iters = []
    for p in chunk_paths:
        f = open_temp(p, "r")
        iters.append((p, f))

    def gen(fh):
        for line in fh:
            rec = safe_json_loads(line)
            if rec and rec.get("date"):
                yield (rec["date"], rec)

# Build a heap of (date, idx, record, iterator)
    heap = []
    generators = [gen(fh) for _, fh in iters]

    for idx, g in enumerate(generators):
        try:
            d, rec = next(g)
            heap.append((d, idx, rec, g))
        except StopIteration:
            pass
    heapq.heapify(heap)

    try:
        while heap:
            d, idx, rec, g = heapq.heappop(heap)
            yield rec
            try:
                nd, nrec = next(g)
                heapq.heappush(heap, (nd, idx, nrec, g))
            except StopIteration:
                pass
    finally:
        for _, fh in iters:
            fh.close()
# Cleanup temp chunks
        for p, _ in iters:
            try:
                os.remove(p)
            except Exception:
                pass


# -------------- Conversation builder (streaming) ----------------


class LRUMessageMap(OrderedDict):
    def __init__(self, maxlen: int):
        super().__init__()
        self.maxlen = maxlen

    def set(self, key, value):
        if key in self:
            self.move_to_end(key)
        self[key] = value
        if len(self) > self.maxlen:
            self.popitem(last=False)

    def get_recent(self, key):
        v = self.get(key)
        if v is not None:
            self.move_to_end(key)
        return v


class ActiveConversation:
    __slots__ = ("messages", "id_set", "start", "last", "topic_id", "topic_title")

    def __init__(self, first_msg: Dict[str, Any]):
        self.messages: List[Dict[str, Any]] = [first_msg]
        self.id_set = {first_msg["id"]}
        self.start = parse_dt(first_msg["date"])
        self.last = self.start
        self.topic_id = first_msg.get("topic_id")
        self.topic_title = first_msg.get("topic_title")

    def try_attach(
        self, msg: Dict[str, Any], time_threshold: int, session_window: int
    ) -> bool:
        msg_dt = parse_dt(msg["date"])
        within_gap = (msg_dt - self.last).total_seconds() < time_threshold
        within_window = (msg_dt - self.start).total_seconds() < session_window
        same_topic = self.topic_id == msg.get("topic_id")
# Relaxed: Prefer topic consistency if available
        if within_window and same_topic and within_gap:
            self.messages.append(msg)
            self.id_set.add(msg["id"])
            self.last = msg_dt
            return True
        return False

    def attach_force(self, msg: Dict[str, Any]):
        msg_dt = parse_dt(msg["date"])
        self.messages.append(msg)
        self.id_set.add(msg["id"])
        if msg_dt > self.last:
            self.last = msg_dt

    def is_expired(self, now_dt: datetime, session_window: int) -> bool:
        return (now_dt - self.start).total_seconds() >= session_window


def save_conversation_stream(fh, conv: ActiveConversation):
# Write a conversation as a JSON envelope
    conv_texts = []
    for m in conv.messages:
        content = m.get("content", "")
        if isinstance(content, dict):
# Handle cases where content is a dict, like in poll messages
            content = content.get("text", "")
        conv_texts.append(content or "")
    joined = "\n".join(conv_texts)
    ingestion_hash = hashlib.md5(joined.encode("utf-8")).hexdigest()
# Collect unique source files and source names if present
    source_files = list(
        {
            m.get("source_saved_file")
            for m in conv.messages
            if m.get("source_saved_file")
        }
    )
    source_names = list(
        {m.get("source_name") for m in conv.messages if m.get("source_name")}
    )

    envelope = {
        "ingestion_timestamp": iso(datetime.utcnow()),
        "ingestion_hash": ingestion_hash,
        "source_files": source_files,
        "source_names": source_names,
        "conversation": conv.messages,
# small derived summary fields to help synthesis without heavy processing
        "message_count": len(conv.messages),
    }

    fh.write(json.dumps(envelope, ensure_ascii=False))
    fh.write("\n")


# ----------- Lightweight numeric/date normalization ---------
NUMBER_RE = re.compile(
    r"(?P<number>\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\b)\s*(?P<unit>%|percent|rs|inr|₹|km|m|kg|k|lakh|crore|million|billion)?",
    re.IGNORECASE,
)


def normalize_numbers(text: str) -> List[Dict[str, Any]]:
    """Extract simple numeric facts from text into normalized records.

    This is intentionally lightweight: it extracts numbers and common units.
    """
    results = []
    for m in NUMBER_RE.finditer(text):
        num = m.group("number")
        unit = (m.group("unit") or "").lower()
# normalize 1,234.56 or 1.234,56 -> 1234.56
        norm = num.replace(",", "")
        try:
            val = float(norm)
        except Exception:
            try:
                val = float(norm.replace(".", ""))
            except Exception:
                val = None
        results.append(
            {
                "span": m.group(0),
                "value": val,
                "unit": unit,
                "confidence": "low" if val is None else "medium",
            }
        )
    return results


# ------------------ Main pipeline ------------------------


def main():
    logging.info("🚀 Starting Phase 2: Streaming Data Processing & KB Creation")

    raw_files = iter_jsonl_files(RAW_DIR)
    if not raw_files:
        return

# Step 1: chunked external sort
    chunk_paths = write_sorted_chunks(raw_files)
    if not chunk_paths:
        logging.warning("No data after chunking. Exiting.")
        return

# Step 2: iterate sorted records, anonymize on the fly, build conversations
    user_map, next_user_num = load_user_map()

# Output: write conversations as JSONL-of-arrays to keep memory low
    tmp_out_fd, tmp_out_path = tempfile.mkstemp(
        prefix="conversations_", suffix=".jsonl"
    )
    os.close(tmp_out_fd)
    conv_out = open(tmp_out_path, "w", encoding="utf-8")

    msg_map = LRUMessageMap(MAX_MESSAGE_MAP_SIZE)  # id -> minimal msg
    active: deque[ActiveConversation] = deque()  # a bounded set of in-flight convs

    total_msgs = 0
    total_convs = 0
    dropped = 0

    for rec in iter_sorted_records(chunk_paths):
        total_msgs += 1

# sanitize/anonymize
        sender_id = rec.get("sender_id")
        content = rec.get("content")
        if not sender_id or not content:
            dropped += 1
            continue

# stable anonymization
        sid = str(sender_id)
        if sid not in user_map:
            user_map[sid] = f"User_{next_user_num}"
            next_user_num += 1
        rec["sender_id"] = user_map[sid]

# Lightweight numeric/date normalization per message to support later verification
        try:
            rec["normalized_values"] = normalize_numbers(content)
        except Exception:
            rec["normalized_values"] = []

# minimal record normalization (keep fields used downstream)
        try:
            _ = parse_dt(rec["date"])
        except Exception:
            dropped += 1
            continue

# Thread-first: if reply_to is present and we still have its parent, attach to that conversation
        attached = False
        parent_id = rec.get("reply_to_msg_id")
        parent = msg_map.get_recent(parent_id) if parent_id else None
        if parent is not None and hasattr(parent, "_conv_idx"):
# attach to parent's conversation directly
            conv_idx = parent._conv_idx  # type: ignore[attr-defined]
            try:
                conv = active[conv_idx]
                conv.attach_force(rec)
                attached = True
            except IndexError:
# conversation might have been flushed; fall back to time-based attach
                pass

# Try to attach by time/topic to the latest few active conversations
        if not attached:
# iterate from right (most recent)
            for i in range(
                min(len(active), 200)
            ):  # check last 200 active convs to stay cheap
                conv = active[-1 - i]
                if conv.try_attach(rec, TIME_THRESHOLD_SECONDS, SESSION_WINDOW_SECONDS):
                    attached = True
                    break

# If still not attached, start a new conversation
        if not attached:
            conv = ActiveConversation(rec)
            active.append(conv)

# Track message in LRU for potential thread linking
        try:
            conv_idx = (
                len(active) - 1
                if not attached
                else next(
                    (
                        len(active) - 1 - i
                        for i in range(min(len(active), 200))
                        if rec["id"] in active[-1 - i].id_set
                    ),
                    None,
                )
            )
# augment record proxy with conversation index (only stored in map, not persisted)
            rec_proxy = type("MsgProxy", (), {})()
            rec_proxy.id = rec["id"]
            rec_proxy._conv_idx = conv_idx
            msg_map.set(rec["id"], rec_proxy)
        except Exception:
# if anything odd, still keep id in map without index
            rec_proxy = type("MsgProxy", (), {})()
            rec_proxy.id = rec["id"]
            msg_map.set(rec["id"], rec_proxy)

# Flush expired conversations to disk to keep memory bounded
        now_dt = parse_dt(rec["date"])
        while active and active[0].is_expired(now_dt, SESSION_WINDOW_SECONDS):
            save_conversation_stream(conv_out, active.popleft())
            total_convs += 1

# Bound number of active conversations
        while len(active) > MAX_ACTIVE_CONVERSATIONS:
            save_conversation_stream(conv_out, active.popleft())
            total_convs += 1

        if total_msgs % 100_000 == 0:
            logging.info(
                f"Processed {total_msgs:,} msgs | active_convs={len(active)} | total_convs_flushed={total_convs:,}"
            )

# Flush remaining conversations
    while active:
        save_conversation_stream(conv_out, active.popleft())
        total_convs += 1

    conv_out.close()
    persist_user_map(user_map)

    logging.info(
        f"Stream processing complete: msgs={total_msgs:,}, convs={total_convs:,}, dropped={dropped:,}"
    )
    logging.info(
        f"Conversations written (JSONL, one conversation per line): {tmp_out_path}"
    )
    logging.info(f"User map saved: {OUT_USER_MAP_FILE}")

# OPTIONAL: Convert JSONL-of-arrays -> single pretty JSON list file expected by downstream
    logging.info(
        f"Rewriting conversations JSONL -> pretty JSON array at {OUT_CONV_FILE}"
    )
    with (
        open(tmp_out_path, "r", encoding="utf-8") as src,
        open(OUT_CONV_FILE, "w", encoding="utf-8") as dest,
    ):
        dest.write("[\n")
        first = True
        for line in src:
            line = line.strip()
            if not line:
                continue
            if not first:
                dest.write(",\n")
            dest.write(line)
            first = False
        dest.write("\n]\n")
    try:
        os.remove(tmp_out_path)
    except Exception:
        pass

    logging.info("✅ Data processing complete.")


if __name__ == "__main__":
    main()
