"""Unit tests for chat history persistence."""

import pytest
import json
from pathlib import Path
from backend.chat_history import (
    load_chat_history,
    save_chat_history,
    append_message,
    clear_chat_history,
    CHAT_HISTORY_FILENAME,
)


@pytest.fixture
def campaign_dir(tmp_path):
    """Create temporary campaign directory."""
    campaign = tmp_path / "test-campaign"
    campaign.mkdir()
    return campaign


def test_chat_history_save(campaign_dir):
    """Test chat history saves to JSON with correct schema."""
    messages = [
        {
            "role": "user",
            "content": "Hello DM",
            "timestamp": "2026-04-01T10:00:00Z"
        },
        {
            "role": "assistant",
            "content": "Welcome, adventurer!",
            "timestamp": "2026-04-01T10:00:01Z"
        }
    ]

    save_chat_history(campaign_dir, messages)

    # Verify file exists
    history_file = campaign_dir / CHAT_HISTORY_FILENAME
    assert history_file.exists()

    # Verify JSON structure
    saved = json.loads(history_file.read_text(encoding="utf-8"))
    assert isinstance(saved, list)
    assert len(saved) == 2

    # Verify message schema
    assert saved[0]["role"] == "user"
    assert saved[0]["content"] == "Hello DM"
    assert "timestamp" in saved[0]

    assert saved[1]["role"] == "assistant"
    assert saved[1]["content"] == "Welcome, adventurer!"


def test_chat_history_load_empty(campaign_dir):
    """Test loading chat history from non-existent file returns empty list."""
    loaded = load_chat_history(campaign_dir)

    assert isinstance(loaded, list)
    assert len(loaded) == 0


def test_chat_history_load_success(campaign_dir):
    """Test chat history loads from file on connect."""
    # Create mock history file
    history_file = campaign_dir / CHAT_HISTORY_FILENAME
    test_messages = [
        {
            "role": "user",
            "content": "Test message",
            "timestamp": "2026-04-01T10:00:00Z"
        },
        {
            "role": "assistant",
            "content": "Test response",
            "timestamp": "2026-04-01T10:00:01Z"
        }
    ]
    history_file.write_text(
        json.dumps(test_messages, ensure_ascii=False),
        encoding="utf-8"
    )

    # Load history
    loaded = load_chat_history(campaign_dir)

    assert len(loaded) == 2
    assert loaded[0]["content"] == "Test message"
    assert loaded[0]["role"] == "user"
    assert loaded[1]["content"] == "Test response"
    assert loaded[1]["role"] == "assistant"


def test_chat_history_load_invalid_json(campaign_dir):
    """Test loading corrupted JSON returns empty list."""
    # Create invalid JSON file
    history_file = campaign_dir / CHAT_HISTORY_FILENAME
    history_file.write_text("not valid json{", encoding="utf-8")

    loaded = load_chat_history(campaign_dir)

    assert isinstance(loaded, list)
    assert len(loaded) == 0


def test_chat_history_load_invalid_structure(campaign_dir):
    """Test loading non-list JSON returns empty list."""
    # Create JSON that's not a list
    history_file = campaign_dir / CHAT_HISTORY_FILENAME
    history_file.write_text(
        json.dumps({"not": "a list"}),
        encoding="utf-8"
    )

    loaded = load_chat_history(campaign_dir)

    assert isinstance(loaded, list)
    assert len(loaded) == 0


def test_chat_history_filters_invalid_entries(campaign_dir):
    """Test loading filters out entries missing required fields."""
    # Create history with some invalid entries
    history_file = campaign_dir / CHAT_HISTORY_FILENAME
    mixed_messages = [
        {
            "role": "user",
            "content": "Valid message",
            "timestamp": "2026-04-01T10:00:00Z"
        },
        {
            "role": "user",
            # Missing content and timestamp
        },
        {
            "content": "Missing role",
            "timestamp": "2026-04-01T10:00:01Z"
        },
        {
            "role": "assistant",
            "content": "Another valid message",
            "timestamp": "2026-04-01T10:00:02Z"
        }
    ]
    history_file.write_text(
        json.dumps(mixed_messages),
        encoding="utf-8"
    )

    loaded = load_chat_history(campaign_dir)

    # Only valid entries should be loaded
    assert len(loaded) == 2
    assert loaded[0]["content"] == "Valid message"
    assert loaded[1]["content"] == "Another valid message"


def test_append_message(campaign_dir):
    """Test appending single message to history."""
    # Append first message
    result1 = append_message(
        campaign_dir,
        role="user",
        content="First message",
        timestamp="2026-04-01T10:00:00Z"
    )

    assert len(result1) == 1
    assert result1[0]["content"] == "First message"

    # Append second message
    result2 = append_message(
        campaign_dir,
        role="assistant",
        content="Second message",
        timestamp="2026-04-01T10:00:01Z"
    )

    assert len(result2) == 2
    assert result2[1]["content"] == "Second message"

    # Verify persistence
    loaded = load_chat_history(campaign_dir)
    assert len(loaded) == 2


def test_append_message_auto_timestamp(campaign_dir):
    """Test appending message without timestamp auto-generates one."""
    result = append_message(
        campaign_dir,
        role="user",
        content="Auto timestamp test"
    )

    assert len(result) == 1
    assert "timestamp" in result[0]
    # Verify timestamp format (ISO 8601 with Z)
    assert result[0]["timestamp"].endswith("Z")


def test_clear_chat_history(campaign_dir):
    """Test clearing chat history saves empty list."""
    # Create some history first
    save_chat_history(campaign_dir, [
        {"role": "user", "content": "Test", "timestamp": "2026-04-01T10:00:00Z"}
    ])

    # Verify it exists
    assert len(load_chat_history(campaign_dir)) == 1

    # Clear it
    clear_chat_history(campaign_dir)

    # Verify it's empty
    loaded = load_chat_history(campaign_dir)
    assert isinstance(loaded, list)
    assert len(loaded) == 0


def test_save_creates_directory(tmp_path):
    """Test saving chat history creates campaign directory if missing."""
    non_existent_dir = tmp_path / "new-campaign"
    assert not non_existent_dir.exists()

    messages = [
        {"role": "user", "content": "Test", "timestamp": "2026-04-01T10:00:00Z"}
    ]

    # Should create directory and save
    save_chat_history(non_existent_dir, messages)

    assert non_existent_dir.exists()
    assert (non_existent_dir / CHAT_HISTORY_FILENAME).exists()


def test_chat_history_utf8_encoding(campaign_dir):
    """Test chat history correctly handles UTF-8 characters."""
    messages = [
        {
            "role": "user",
            "content": "Привет! 你好! こんにちは! 🎲",
            "timestamp": "2026-04-01T10:00:00Z"
        }
    ]

    save_chat_history(campaign_dir, messages)
    loaded = load_chat_history(campaign_dir)

    assert len(loaded) == 1
    assert loaded[0]["content"] == "Привет! 你好! こんにちは! 🎲"
