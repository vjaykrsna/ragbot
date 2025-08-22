import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List

from src.core.config import PathSettings


class Database:
    def __init__(self, settings: PathSettings):
        os.makedirs(settings.db_dir, exist_ok=True)
        self.db_path = os.path.join(settings.db_dir, "ragbot.sqlite")
        # Create the database file if it doesn't exist
        if not os.path.exists(self.db_path):
            # Create an empty file to ensure SQLite can connect
            with open(self.db_path, "w"):
                pass
        # Defer table creation until the first connection

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            # Create tables if they don't exist
            self._create_tables(conn)
            yield conn
        finally:
            conn.close()

    def _create_tables(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                date TEXT,
                sender_id TEXT,
                message_type TEXT,
                content TEXT,
                extra_data TEXT,
                reply_to_msg_id INTEGER,
                topic_id INTEGER,
                topic_title TEXT,
                source_name TEXT,
                source_group_id INTEGER,
                ingestion_timestamp TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS polls (
                message_id INTEGER PRIMARY KEY,
                question TEXT,
                total_voter_count INTEGER,
                is_quiz BOOLEAN,
                is_anonymous BOOLEAN
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS poll_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER,
                text TEXT,
                voters INTEGER,
                chosen BOOLEAN,
                correct BOOLEAN,
                FOREIGN KEY (poll_id) REFERENCES polls (message_id)
            )
            """
        )
        conn.commit()

    def insert_messages(self, messages: List[Dict[str, Any]]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for msg in messages:
                if msg["message_type"] == "poll":
                    self._insert_poll(cursor, msg)
                else:
                    self._insert_message(cursor, msg)
            conn.commit()

    def _insert_message(self, cursor, msg: Dict[str, Any]):
        cursor.execute(
            """
            INSERT OR REPLACE INTO messages (
                id, date, sender_id, message_type, content, extra_data,
                reply_to_msg_id, topic_id, topic_title, source_name,
                source_group_id, ingestion_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["id"],
                msg["date"],
                msg["sender_id"],
                msg["message_type"],
                msg["content"],
                str(msg["extra_data"]),
                msg["reply_to_msg_id"],
                msg["topic_id"],
                msg["topic_title"],
                msg["source_name"],
                msg["source_group_id"],
                msg["ingestion_timestamp"],
            ),
        )

    def _insert_poll(self, cursor, msg: Dict[str, Any]):
        poll_content = msg["content"]
        cursor.execute(
            """
            INSERT OR REPLACE INTO polls (
                message_id, question, total_voter_count, is_quiz, is_anonymous
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg["id"],
                poll_content["question"],
                poll_content["total_voter_count"],
                poll_content["is_quiz"],
                poll_content["is_anonymous"],
            ),
        )
        for option in poll_content["options"]:
            cursor.execute(
                """
                INSERT INTO poll_options (
                    poll_id, text, voters, chosen, correct
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    msg["id"],
                    option["text"],
                    option["voter_count"],
                    option.get("chosen", False),
                    option.get("correct", False),
                ),
            )
        # Also insert a reference into the messages table
        self._insert_message(cursor, {**msg, "content": poll_content["question"]})

    def get_all_messages(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages ORDER BY date")
            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                yield dict(zip(columns, row))
