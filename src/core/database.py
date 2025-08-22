import os
import sqlite3
import threading
from contextlib import contextmanager
from queue import Queue
from typing import Any, Dict, List

from src.core.config import PathSettings


class Database:
    def __init__(self, settings: PathSettings, pool_size: int = 10):  # Back to 10
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
            conn.execute(
                "PRAGMA journal_mode=WAL"
            )  # Enable WAL mode for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Optimize for performance
            conn.execute("PRAGMA cache_size=5000")  # Balanced cache size
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp storage
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
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=5000")
            conn.execute("PRAGMA temp_store=MEMORY")
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
                id INTEGER,
                source_group_id INTEGER,
                topic_id INTEGER,
                date TEXT,
                sender_id TEXT,
                message_type TEXT,
                content TEXT,
                extra_data TEXT,
                reply_to_msg_id INTEGER,
                topic_title TEXT,
                source_name TEXT,
                ingestion_timestamp TEXT,
                PRIMARY KEY (id, source_group_id, topic_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS polls (
                message_id INTEGER,
                source_group_id INTEGER,
                topic_id INTEGER,
                question TEXT,
                total_voter_count INTEGER,
                is_quiz BOOLEAN,
                is_anonymous BOOLEAN,
                PRIMARY KEY (message_id, source_group_id, topic_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS poll_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER,
                poll_source_group_id INTEGER,
                poll_topic_id INTEGER,
                text TEXT,
                voters INTEGER,
                chosen BOOLEAN,
                correct BOOLEAN,
                FOREIGN KEY (poll_id, poll_source_group_id, poll_topic_id) REFERENCES polls (message_id, source_group_id, topic_id)
            )
            """
        )
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_group ON messages(source_group_id)"
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

        # Batch insert messages with executemany for better performance
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
                id, source_group_id, topic_id, date, sender_id, message_type,
                content, extra_data, reply_to_msg_id, topic_title, source_name,
                ingestion_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["id"],
                msg["source_group_id"],
                msg["topic_id"],
                msg["date"],
                msg["sender_id"],
                msg["message_type"],
                msg["content"],
                str(msg["extra_data"]),
                msg["reply_to_msg_id"],
                msg["topic_title"],
                msg["source_name"],
                msg["ingestion_timestamp"],
            ),
        )

    def _insert_poll(self, cursor, msg: Dict[str, Any]):
        poll_content = msg["content"]
        cursor.execute(
            """
            INSERT OR REPLACE INTO polls (
                message_id, source_group_id, topic_id, question, total_voter_count, is_quiz, is_anonymous
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["id"],
                msg["source_group_id"],
                msg["topic_id"],
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
                    poll_id, poll_source_group_id, poll_topic_id, text, voters, chosen, correct
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg["id"],
                    msg["source_group_id"],
                    msg["topic_id"],
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

    def get_message_by_id(self, message_id: int, source_group_id: int, topic_id: int):
        """
        Retrieve a specific message by its composite key.

        Args:
            message_id: The Telegram message ID
            source_group_id: The source group ID
            topic_id: The topic ID

        Returns:
            The message dictionary or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM messages WHERE id = ? AND source_group_id = ? AND topic_id = ?",
                (message_id, source_group_id, topic_id),
            )
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            return dict(zip(columns, row)) if row else None

    def get_unique_sources(self):
        """
        Retrieve all unique source groups and topics.

        Returns:
            List of dictionaries containing source_group_id and topic_id combinations
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT source_group_id, topic_id, source_name, topic_title FROM messages ORDER BY source_group_id, topic_id"
            )
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
