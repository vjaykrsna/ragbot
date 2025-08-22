import os
import sqlite3
import threading
from contextlib import contextmanager
from queue import Queue
from typing import Any, Dict, List

from src.core.config import PathSettings


class Database:
    def __init__(self, settings: PathSettings, pool_size: int = 5):
        os.makedirs(settings.db_dir, exist_ok=True)
        self.db_path = os.path.join(settings.db_dir, "ragbot.sqlite")
        # Create the database file if it doesn't exist
        if not os.path.exists(self.db_path):
            # Create an empty file to ensure SQLite can connect
            with open(self.db_path, "w"):
                pass
        # Initialize connection pool
        self.connection_pool = Queue(maxsize=pool_size)
        self.pool_lock = threading.Lock()
        # Pre-populate the pool with connections
        for _ in range(pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._create_tables(conn)
            self.connection_pool.put(conn)

    @contextmanager
    def _get_connection(self):
        conn = self._get_pooled_connection()
        try:
            # Create tables if they don't exist (though they should already exist)
            self._create_tables(conn)
            yield conn
        finally:
            self._return_connection(conn)

    def _get_pooled_connection(self):
        """Get a connection from the pool or create a new one if pool is empty."""
        try:
            return self.connection_pool.get(timeout=1)
        except Queue.Empty:
            # Create new connection if pool is empty
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._create_tables(conn)
            return conn

    def _return_connection(self, conn):
        """Return a connection to the pool or close it if pool is full."""
        try:
            self.connection_pool.put(conn, timeout=1)
        except Queue.Full:
            # Close connection if pool is full
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
                source_topic_id INTEGER,
                source_saved_file TEXT,
                ingestion_timestamp TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS polls (
                message_id INTEGER PRIMARY KEY,
                question TEXT,
                total_voters INTEGER,
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
            self._batch_insert_messages(cursor, messages)
            conn.commit()

    def _batch_insert_messages(self, cursor, messages: List[Dict[str, Any]]):
        """Batch insert messages for improved performance."""
        if not messages:
            return

        # Prepare data for batch insertion
        message_data = []
        poll_data = []
        poll_options_data = []

        for msg in messages:
            if msg["message_type"] == "poll":
                poll_content = msg["content"]
                poll_data.append(
                    (
                        msg["id"],
                        poll_content["question"],
                        poll_content["total_voters"],
                        poll_content["is_quiz"],
                        poll_content["is_anonymous"],
                    )
                )
                # Also add to messages table with question as content
                message_data.append(
                    (
                        msg["id"],
                        msg["date"],
                        msg["sender_id"],
                        msg["message_type"],
                        poll_content["question"],
                        str(msg["extra_data"]),
                        msg["reply_to_msg_id"],
                        msg["topic_id"],
                        msg["topic_title"],
                        msg["source_name"],
                        msg["source_group_id"],
                        msg["source_topic_id"],
                        msg["source_saved_file"],
                        msg["ingestion_timestamp"],
                    )
                )
                for option in poll_content["options"]:
                    poll_options_data.append(
                        (
                            msg["id"],
                            option["text"],
                            option["voters"],
                            option.get("chosen", False),
                            option.get("correct", False),
                        )
                    )
            else:
                message_data.append(
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
                        msg["source_topic_id"],
                        msg["source_saved_file"],
                        msg["ingestion_timestamp"],
                    )
                )

        # Batch insert messages
        if message_data:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO messages (
                    id, date, sender_id, message_type, content, extra_data,
                    reply_to_msg_id, topic_id, topic_title, source_name,
                    source_group_id, source_topic_id, source_saved_file,
                    ingestion_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                message_data,
            )

        # Batch insert polls
        if poll_data:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO polls (
                    message_id, question, total_voters, is_quiz, is_anonymous
                ) VALUES (?, ?, ?, ?, ?)
            """,
                poll_data,
            )

        # Batch insert poll options
        if poll_options_data:
            cursor.executemany(
                """
                INSERT INTO poll_options (
                    poll_id, text, voters, chosen, correct
                ) VALUES (?, ?, ?, ?, ?)
            """,
                poll_options_data,
            )

    def _insert_message(self, cursor, msg: Dict[str, Any]):
        cursor.execute(
            """
            INSERT OR REPLACE INTO messages (
                id, date, sender_id, message_type, content, extra_data,
                reply_to_msg_id, topic_id, topic_title, source_name,
                source_group_id, source_topic_id, source_saved_file,
                ingestion_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                msg["source_topic_id"],
                msg["source_saved_file"],
                msg["ingestion_timestamp"],
            ),
        )

    def _insert_poll(self, cursor, msg: Dict[str, Any]):
        poll_content = msg["content"]
        cursor.execute(
            """
            INSERT OR REPLACE INTO polls (
                message_id, question, total_voters, is_quiz, is_anonymous
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg["id"],
                poll_content["question"],
                poll_content["total_voters"],
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
                    option["voters"],
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
