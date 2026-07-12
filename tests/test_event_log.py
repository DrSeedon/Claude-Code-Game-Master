"""Unit tests for the append-only JSONL event log."""

import json
import pytest

from backend.event_log import append_event, read_events, EVENT_LOG_FILENAME


@pytest.fixture
def campaign_dir(tmp_path):
    d = tmp_path / "test-campaign"
    d.mkdir()
    return d


def test_append_creates_file_with_monotonic_id(campaign_dir):
    e1 = append_event(campaign_dir, "user_message", "hello")
    e2 = append_event(campaign_dir, "text", "world")

    assert e1["id"] == 1
    assert e2["id"] == 2
    assert (campaign_dir / EVENT_LOG_FILENAME).exists()


def test_append_creates_directory(tmp_path):
    missing_dir = tmp_path / "new-campaign"
    assert not missing_dir.exists()

    append_event(missing_dir, "text", "hi")

    assert missing_dir.exists()


def test_read_events_empty_when_no_file(campaign_dir):
    assert read_events(campaign_dir) == []


def test_read_events_returns_all_by_default(campaign_dir):
    append_event(campaign_dir, "user_message", "a")
    append_event(campaign_dir, "text", "b")

    events = read_events(campaign_dir)

    assert len(events) == 2
    assert events[0]["content"] == "a"
    assert events[1]["content"] == "b"


def test_read_events_after_id_filters(campaign_dir):
    append_event(campaign_dir, "user_message", "a")
    e2 = append_event(campaign_dir, "text", "b")
    append_event(campaign_dir, "text", "c")

    events = read_events(campaign_dir, after_id=e2["id"])

    assert len(events) == 1
    assert events[0]["content"] == "c"


def test_read_events_skips_corrupted_lines(campaign_dir):
    append_event(campaign_dir, "text", "valid")
    path = campaign_dir / EVENT_LOG_FILENAME
    with open(path, "a") as f:
        f.write("not valid json{\n")

    events = read_events(campaign_dir)

    assert len(events) == 1
    assert events[0]["content"] == "valid"


def test_event_schema_has_type_content_timestamp(campaign_dir):
    event = append_event(campaign_dir, "activity", "🔧 dm-roll.sh")

    assert event["type"] == "activity"
    assert event["content"] == "🔧 dm-roll.sh"
    assert "timestamp" in event

    stored = json.loads((campaign_dir / EVENT_LOG_FILENAME).read_text().splitlines()[0])
    assert stored == event
