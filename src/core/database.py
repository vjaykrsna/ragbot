import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List

from src.core.config import PathSettings


def serialize_extra_data(extra_data: Dict[str, Any]) -> str:
    """Serialize extra_data dictionary to JSON string, handling datetime objects."""
    # Handle None case
    if extra_data is None:
        return "{}"

    # Handle non-dict cases
    if not isinstance(extra_data, dict):
        # Try to convert to dict if it's a string representation of a dict
        if isinstance(extra_data, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(extra_data)
                if isinstance(parsed, dict):
                    extra_data = parsed
                else:
                    # If it's not a dict after parsing, convert to string
                    return json.dumps({"value": extra_data})
            except json.JSONDecodeError:
                # If it's not valid JSON, convert to string
                return json.dumps({"value": extra_data})
        else:
            # If it's not a dict and not a string, convert to string
            return json.dumps({"value": str(extra_data)})

    # At this point, extra_data should be a dict
    # Create a copy of the dictionary to avoid modifying the original
    serializable_data = {}
    for key, value in extra_data.items():
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        else:
            # Handle non-serializable objects
            try:
                json.dumps(value)  # Test if value is JSON serializable
                serializable_data[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string
                serializable_data[key] = str(value)

    return json.dumps(serializable_data)


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
        finally:
            # Ensure connection is properly closed/cleaned up
            if hasattr(self.local, "connection"):
                try:
                    self.local.connection.close()
                    delattr(self.local, "connection")
                except Exception:
                    pass  # Ignore cleanup errors

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

            # Also serialize content if it's not a string (e.g., for polls)
            content = msg["content"]
            if not isinstance(content, str):
                try:
                    content = json.dumps(content)
                except (TypeError, ValueError):
                    # If content is not JSON serializable, convert to string
                    content = str(content)

            # Serialize date field if it's not already a string
            date_value = msg["date"]
            if not isinstance(date_value, str):
                # Handle datetime objects
                if hasattr(date_value, "isoformat"):
                    date_value = date_value.isoformat()
                # Handle timestamp objects
                elif hasattr(date_value, "timestamp"):
                    date_value = datetime.fromtimestamp(
                        date_value.timestamp()
                    ).isoformat()
                # Handle MagicMock objects and other non-serializable objects
                else:
                    try:
                        json.dumps(date_value)  # Test if value is JSON serializable
                        # If it is, convert to string
                        date_value = str(date_value)
                    except (TypeError, ValueError):
                        # If not serializable, convert to string
                        date_value = str(date_value)

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

        # Also serialize content if it's not a string (e.g., for polls)
        content = msg["content"]
        if not isinstance(content, str):
            try:
                content = json.dumps(content)
            except (TypeError, ValueError):
                # If content is not JSON serializable, convert to string
                content = str(content)

        # Serialize date field if it's not already a string
        date_value = msg["date"]
        if not isinstance(date_value, str):
            # Handle datetime objects
            if hasattr(date_value, "isoformat"):
                date_value = date_value.isoformat()
            # Handle timestamp objects
            elif hasattr(date_value, "timestamp"):
                date_value = datetime.fromtimestamp(date_value.timestamp()).isoformat()
            # Handle MagicMock objects and other non-serializable objects
            else:
                try:
                    json.dumps(date_value)  # Test if value is JSON serializable
                    # If it is, convert to string
                    date_value = str(date_value)
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    date_value = str(date_value)

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
                if row_dict.get("extra_data"):
                    try:
                        row_dict["extra_data"] = json.loads(row_dict["extra_data"])
                    except (json.JSONDecodeError, TypeError):
                        # If deserialization fails, keep as is
                        pass
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
                if row_dict.get("extra_data"):
                    try:
                        row_dict["extra_data"] = json.loads(row_dict["extra_data"])
                    except (json.JSONDecodeError, TypeError):
                        # If deserialization fails, keep as is
                        pass
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
                if row_dict.get("extra_data"):
                    try:
                        row_dict["extra_data"] = json.loads(row_dict["extra_data"])
                    except (json.JSONDecodeError, TypeError):
                        # If deserialization fails, keep as is
                        pass
                results.append(row_dict)
            return results
