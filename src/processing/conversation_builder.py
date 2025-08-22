"""
Conversation building component for the data processing pipeline.

This module provides classes for grouping a stream of sorted messages into
conversations based on time, topic, and reply-to links.
"""

import hashlib
import logging
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List

from dateutil.parser import isoparse

from src.core.config import ConversationSettings


class LRUMessageMap(OrderedDict):
    """A simple LRU map to keep track of recent messages for reply linking."""

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
    """Represents a single, ongoing conversation."""

    __slots__ = ("messages", "id_set", "start", "last", "topic_id", "topic_title")

    def __init__(self, first_msg: Dict[str, Any]):
        self.messages: List[Dict[str, Any]] = [first_msg]
        self.id_set = {first_msg["id"]}
        self.start = isoparse(first_msg["date"])
        self.last = self.start
        # Use topic_id for consistency
        self.topic_id = first_msg.get("topic_id")
        self.topic_title = first_msg.get("topic_title")

    def try_attach(
        self, msg: Dict[str, Any], time_threshold: int, session_window: int
    ) -> bool:
        """Tries to attach a message to this conversation based on time and topic."""
        msg_dt = isoparse(msg["date"])
        within_gap = (msg_dt - self.last).total_seconds() < time_threshold
        within_window = (msg_dt - self.start).total_seconds() < session_window
        # Use topic_id for consistency
        same_topic = self.topic_id == msg.get("topic_id")

        if within_window and same_topic and within_gap:
            self._add_message(msg, msg_dt)
            return True
        return False

    def attach_force(self, msg: Dict[str, Any]):
        """Attaches a message regardless of time, e.g., for a direct reply."""
        self._add_message(msg, isoparse(msg["date"]))

    def is_expired(self, now_dt: datetime, session_window: int) -> bool:
        """Checks if the conversation has exceeded the maximum session window."""
        return (now_dt - self.start).total_seconds() >= session_window

    def _add_message(self, msg: Dict[str, Any], msg_dt: datetime):
        self.messages.append(msg)
        self.id_set.add(msg["id"])
        if msg_dt > self.last:
            self.last = msg_dt


class ConversationBuilder:
    """
    Groups a stream of sorted, anonymized messages into conversations.
    """

    def __init__(
        self,
        conv_settings: ConversationSettings,
        max_active: int = 10_000,
        max_msg_map: int = 200_000,
    ):
        self.settings = conv_settings
        self.max_active_conversations = max_active
        self.msg_map = LRUMessageMap(max_msg_map)
        self.active: deque[ActiveConversation] = deque()
        self.logger = logging.getLogger(__name__)

    def process_stream(
        self, message_stream: Generator[Dict[str, Any], None, None]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Processes a stream of messages and yields completed conversation envelopes.
        """
        total_msgs = 0
        for rec in message_stream:
            total_msgs += 1
            now_dt = isoparse(rec["date"])

            # First, flush any conversations that have expired relative to the current message
            while self.active and self.active[0].is_expired(
                now_dt, self.settings.session_window_seconds
            ):
                yield self._create_envelope(self.active.popleft())

            self._assign_to_conversation(rec)

            # Bound the number of active conversations to prevent memory issues
            while len(self.active) > self.max_active_conversations:
                yield self._create_envelope(self.active.popleft())

            if total_msgs % 100_000 == 0:
                self.logger.info(
                    f"Processed {total_msgs:,} msgs | active_convs={len(self.active)}"
                )

        # Flush all remaining conversations at the end of the stream
        while self.active:
            yield self._create_envelope(self.active.popleft())

    def _assign_to_conversation(self, rec: Dict[str, Any]):
        """Assigns a single message to an existing or new conversation."""
        # 1. Try to attach via direct reply
        parent_id = rec.get("reply_to_msg_id")
        parent_proxy = self.msg_map.get_recent(parent_id) if parent_id else None
        if parent_proxy and hasattr(parent_proxy, "_conv_idx"):
            try:
                conv = self.active[parent_proxy._conv_idx]
                conv.attach_force(rec)
                self._update_message_map(rec)
                return
            except IndexError:
                pass  # Conversation was already flushed, fall back to time-based

        # 2. Try to attach by time/topic to recent conversations
        for i in range(min(len(self.active), 200)):
            conv = self.active[-1 - i]
            if conv.try_attach(
                rec,
                self.settings.time_threshold_seconds,
                self.settings.session_window_seconds,
            ):
                self._update_message_map(rec)
                return

        # 3. If not attached, create a new conversation
        conv = ActiveConversation(rec)
        self.active.append(conv)
        self._update_message_map(rec)

    def _update_message_map(self, rec: Dict[str, Any]):
        """Updates the LRU message map with a proxy object for the message."""
        try:
            conv_idx = next(
                len(self.active) - 1 - i
                for i in range(min(len(self.active), 200))
                if rec["id"] in self.active[-1 - i].id_set
            )
            # Create a lightweight proxy object to store in the map
            rec_proxy = type("MsgProxy", (), {"id": rec["id"], "_conv_idx": conv_idx})()
            self.msg_map.set(rec["id"], rec_proxy)
        except (StopIteration, KeyError):
            # Fallback if something goes wrong
            rec_proxy = type("MsgProxy", (), {"id": rec["id"]})()
            self.msg_map.set(rec["id"], rec_proxy)

    def _create_envelope(self, conv: ActiveConversation) -> Dict[str, Any]:
        """Creates the final conversation envelope for persistence."""
        conv_texts = []
        for m in conv.messages:
            content = m.get("content", "")
            if isinstance(content, dict):
                # Handle structured content like polls by formatting it into a readable string
                question = content.get("question", "Poll")
                options = content.get("options", [])
                options_str = "\n".join(
                    f"- {opt.get('text', '')} ({opt.get('voters', 0)} votes)"
                    for opt in options
                )
                total_voters = content.get("total_voters", 0)
                content = (
                    f"Poll: {question}\n{options_str}\nTotal Voters: {total_voters}"
                )
            conv_texts.append(content or "")
        joined = "\n".join(conv_texts)
        ingestion_hash = hashlib.md5(joined.encode("utf-8")).hexdigest()

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

        return {
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "ingestion_hash": ingestion_hash,
            "source_files": source_files,
            "source_names": source_names,
            "conversation": conv.messages,
            "message_count": len(conv.messages),
        }
