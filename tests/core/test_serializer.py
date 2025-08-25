import json
from datetime import datetime
from unittest.mock import MagicMock

from src.core.serializer import (
    deserialize_extra_data,
    serialize_content,
    serialize_date,
    serialize_extra_data,
)


def test_serialize_extra_data_with_none():
    """Test serialize_extra_data with None input."""
    result = serialize_extra_data(None)
    assert result == "{}"


def test_serialize_extra_data_with_dict():
    """Test serialize_extra_data with dict input."""
    data = {"key": "value", "number": 42}
    result = serialize_extra_data(data)
    assert json.loads(result) == data


def test_serialize_extra_data_with_datetime():
    """Test serialize_extra_data with datetime object."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    data = {"timestamp": dt}
    result = serialize_extra_data(data)
    parsed = json.loads(result)
    assert parsed["timestamp"] == "2023-01-01T12:00:00"


def test_serialize_extra_data_with_non_dict():
    """Test serialize_extra_data with non-dict input."""
    result = serialize_extra_data("not a dict")
    parsed = json.loads(result)
    assert parsed == {"value": "not a dict"}


def test_deserialize_extra_data():
    """Test deserialize_extra_data function."""
    data = {"key": "value"}
    serialized = json.dumps(data)
    result = deserialize_extra_data(serialized)
    assert result == data


def test_deserialize_extra_data_with_none():
    """Test deserialize_extra_data with None input."""
    result = deserialize_extra_data(None)
    assert result == {}


def test_serialize_content_with_string():
    """Test serialize_content with string input."""
    content = "Hello, world!"
    result = serialize_content(content)
    assert result == content


def test_serialize_content_with_dict():
    """Test serialize_content with dict input."""
    content = {"key": "value"}
    result = serialize_content(content)
    assert json.loads(result) == content


def test_serialize_content_with_non_serializable():
    """Test serialize_content with non-serializable object."""
    content = MagicMock()
    result = serialize_content(content)
    assert isinstance(result, str)


def test_serialize_date_with_string():
    """Test serialize_date with string input."""
    date_str = "2023-01-01T12:00:00"
    result = serialize_date(date_str)
    assert result == date_str


def test_serialize_date_with_datetime():
    """Test serialize_date with datetime object."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = serialize_date(dt)
    assert result == "2023-01-01T12:00:00"


def test_serialize_date_with_timestamp():
    """Test serialize_date with timestamp object."""

    # This is a simplified test - in practice, we'd need a proper timestamp object
    class MockTimestamp:
        def timestamp(self):
            return 1672574400.0  # 2023-01-01T12:00:00 UTC

    ts = MockTimestamp()
    result = serialize_date(ts)
    # We just need to verify it returns a string, as the exact time depends on timezone
    assert isinstance(result, str)
    assert len(result) > 0
