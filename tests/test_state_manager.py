import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from src.core.config import AppSettings, PathSettings
from src.core.state_manager import StateManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def mock_settings(temp_dir):
    """Create mock settings with temporary file paths."""
    # Create a PathSettings instance with the correct attributes
    paths = PathSettings()

    # Override the computed paths with our test paths
    paths.synthesis_checkpoint_file = os.path.join(
        temp_dir, "synthesis_checkpoint.json"
    )
    paths.synthesis_progress_file = os.path.join(temp_dir, "synthesis_progress.json")
    paths.processed_hashes_file = os.path.join(temp_dir, "processed_hashes.json")
    paths.failed_batches_file = os.path.join(temp_dir, "failed_batches.json")

    settings = MagicMock(spec=AppSettings)
    settings.paths = paths
    return settings


@pytest.fixture
def state_manager(mock_settings):
    """Create a StateManager instance for testing."""
    return StateManager(mock_settings)


def test_save_and_load_checkpoint(state_manager):
    """Test saving and loading checkpoints."""
    # Save a checkpoint
    test_data = {
        "last_processed_index": 10,
        "processed_hashes": ["hash1", "hash2"],
        "total_nuggets_stored": 100,
    }
    state_manager.save_checkpoint(**test_data)

    # Load the checkpoint
    loaded_data = state_manager.load_checkpoint()

    # Verify the data
    assert loaded_data == test_data
    assert state_manager.last_checkpoint == test_data


def test_clear_checkpoint(state_manager):
    """Test clearing checkpoints."""
    # Save a checkpoint first
    state_manager.save_checkpoint(last_processed_index=5)
    assert state_manager.load_checkpoint() == {"last_processed_index": 5}

    # Clear the checkpoint
    state_manager.clear_checkpoint()

    # Verify it's cleared
    assert state_manager.load_checkpoint() == {}
    assert state_manager.last_checkpoint == {}

    # Verify file is removed
    assert not os.path.exists(state_manager.checkpoint_file)


def test_save_and_load_progress(state_manager):
    """Test saving and loading progress."""
    # Save progress
    state_manager.save_progress(42)

    # Load progress
    loaded_progress = state_manager.load_progress()

    # Verify
    assert loaded_progress == 42


def test_load_progress_file_not_found(state_manager):
    """Test loading progress when file doesn't exist."""
    progress = state_manager.load_progress()
    assert progress == -1


def test_load_progress_invalid_json(state_manager):
    """Test loading progress with invalid JSON."""
    # Create an invalid JSON file
    with open(state_manager.progress_file, "w") as f:
        f.write("invalid json")

    progress = state_manager.load_progress()
    assert progress == -1


def test_save_and_load_processed_hashes(state_manager):
    """Test saving and loading processed hashes."""
    # Save hashes
    test_hashes = {"hash1", "hash2", "hash3"}
    state_manager.save_processed_hashes(test_hashes)

    # Load hashes
    loaded_hashes = state_manager.load_processed_hashes()

    # Verify
    assert loaded_hashes == test_hashes


def test_load_processed_hashes_file_not_found(state_manager):
    """Test loading processed hashes when file doesn't exist."""
    hashes = state_manager.load_processed_hashes()
    assert hashes == set()


def test_load_processed_hashes_invalid_json(state_manager):
    """Test loading processed hashes with invalid JSON."""
    # Create an invalid JSON file
    with open(state_manager.processed_hashes_file, "w") as f:
        f.write("invalid json")

    hashes = state_manager.load_processed_hashes()
    assert hashes == set()


def test_save_failed_batch(state_manager):
    """Test saving a failed batch."""
    # Test data
    conv_batch = [{"id": 1, "content": "test"}, {"id": 2, "content": "test2"}]
    error = "Test error"
    response_text = "Test response"

    # Save failed batch
    state_manager.save_failed_batch(conv_batch, error, response_text)

    # Verify file was created and contains the data
    assert os.path.exists(state_manager.failed_batches_file)

    # Read and verify content
    with open(state_manager.failed_batches_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["error"] == error
        assert data["response_text"] == response_text
        assert data["batch"] == conv_batch
        assert "timestamp" in data


def test_multiple_failed_batches(state_manager):
    """Test saving multiple failed batches."""
    # Save multiple batches
    for i in range(3):
        conv_batch = [{"id": i, "content": f"test{i}"}]
        state_manager.save_failed_batch(conv_batch, f"Error {i}")

    # Verify all batches were saved
    with open(state_manager.failed_batches_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 3


if __name__ == "__main__":
    pytest.main([__file__])
