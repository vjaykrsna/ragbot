import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, List

from src.core.config import PathSettings
from src.core.serializer import (
    deserialize_extra_data,
    serialize_content,
    serialize_date,
    serialize_extra_data,
)


class Database:
    def __init__(self, settings: PathSettings, pool_size: int = 10):  # Back to 10
        os.makedirs(settings.db_dir, exist_ok=True)
        self.db_path = os.path.join(settings.db_dir, "ragbot.sqlite")
        # Create the database file if it doesn't exist
        if not os.path.exists(self.db_path):
            # Create an empty file to ensure SQLite can connect
            with open(self.db_path, "w"):
                pass
        # Use thread-local storage for connections to ensure thread safety
        self.local = threading.local()
        # Initialize shared connection for table creation
        self.shared_conn = sqlite3.connect(self.db_path)
        self.shared_conn.execute(
            "PRAGMA journal_mode=WAL"
        )  # Enable WAL mode for better concurrency
        self.shared_conn.execute(
            "PRAGMA synchronous=NORMAL"
        )  # Optimize for performance
        self.shared_conn.execute("PRAGMA cache_size=5000")  # Balanced cache size
        self.shared_conn.execute(
            "PRAGMA temp_store=MEMORY"
        )  # Use memory for temp storage
        self._create_tables(self.shared_conn)
        self.shared_conn.close()

    def _get_thread_local_connection(self):
        """Get a thread-local connection to the database."""
        if not hasattr(self.local, "connection"):
            # Create a new connection for this thread
            self.local.connection = sqlite3.connect(self.db_path)
            self.local.connection.execute("PRAGMA journal_mode=WAL")
            self.local.connection.execute("PRAGMA synchronous=NORMAL")
            self.local.connection.execute("PRAGMA cache_size=5000")
            self.local.connection.execute("PRAGMA temp_store=MEMORY")
        return self.local.connection

    @contextmanager
    def _get_connection(self):
        """Get a thread-safe connection to the database."""
        conn = self._get_thread_local_connection()
        try:
            # Ensure tables exist (though they should already exist)
            self._create_tables(conn)
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        else:
            conn.commit()
        # Note: We don't close the connection here to allow for connection reuse
        # The connection will be closed when the Database instance is destroyed

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

        for msg in messages:
            # For all message types including polls, store in the main messages table
            # Poll data is already serialized in the content or extra_data fields
            serialized_extra_data = serialize_extra_data(msg["extra_data"])
            content = serialize_content(msg["content"])
            date_value = serialize_date(msg["date"])

            message_data.append(
                (
                    msg["id"],
                    msg["source_group_id"],
                    msg["topic_id"],
                    date_value,  # Serialize date if needed
                    msg["sender_id"],
                    msg["message_type"],
                    content,  # Serialize content if needed
                    serialized_extra_data,  # Serialize dict to JSON string
                    msg["reply_to_msg_id"],
                    msg["topic_title"],
                    msg["source_name"],
                    msg["ingestion_timestamp"],
                )
            )

        # Batch insert messages with executemany for better performance
        if message_data:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO messages (
                    id, source_group_id, topic_id, date, sender_id, message_type, content, extra_data,
                    reply_to_msg_id, topic_title, source_name, ingestion_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                message_data,
            )

    def _insert_message(self, cursor, msg: Dict[str, Any]):
        serialized_extra_data = serialize_extra_data(msg["extra_data"])
        content = serialize_content(msg["content"])
        date_value = serialize_date(msg["date"])

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
                date_value,  # Serialize date if needed
                msg["sender_id"],
                msg["message_type"],
                content,  # Serialize content if needed
                serialized_extra_data,  # Serialize dict to JSON string
                msg["reply_to_msg_id"],
                msg["topic_title"],
                msg["source_name"],
                msg["ingestion_timestamp"],
            ),
        )

    def get_all_messages(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages ORDER BY date")
            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                # Deserialize extra_data from JSON string back to dict
                row_dict["extra_data"] = deserialize_extra_data(
                    row_dict.get("extra_data")
                )
                yield row_dict

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
            if row:
                row_dict = dict(zip(columns, row))
                # Deserialize extra_data from JSON string back to dict
                row_dict["extra_data"] = deserialize_extra_data(
                    row_dict.get("extra_data")
                )
                return row_dict
            return None

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
            results = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                # Deserialize extra_data from JSON string back to dict if needed
                row_dict["extra_data"] = deserialize_extra_data(
                    row_dict.get("extra_data")
                )
                results.append(row_dict)
            return results

    def close_all_connections(self):
        """
        Close all database connections to ensure clean shutdown.
        """
        # Close thread-local connection if it exists
        if hasattr(self.local, "connection"):
            try:
                # Commit any pending transactions before closing
                self.local.connection.commit()
                self.local.connection.close()
                delattr(self.local, "connection")
            except Exception:
                pass  # Ignore cleanup errors

    def __del__(self):
        """Ensure all connections are closed when the Database instance is destroyed."""
        self.close_all_connections()

    def clear_all_messages(self):
        """
        Clear all messages from the database.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            conn.commit()
