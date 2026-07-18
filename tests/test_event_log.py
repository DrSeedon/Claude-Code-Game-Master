"""Unit tests for the append-only JSONL event log."""

import json
from concurrent.futures import ThreadPoolExecutor
import pytest

from backend.event_log import (
    EVENT_LOG_FILENAME,
    append_event,
    read_current_session_events,
    read_events,
)


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


def test_current_session_events_start_after_latest_reset_boundary(campaign_dir):
    old_user = append_event(campaign_dir, "user_message", "old question")
    old_dm = append_event(campaign_dir, "text", "old answer")
    boundary = append_event(campaign_dir, "session_reset", "")
    current = append_event(campaign_dir, "text", "new answer")

    assert [event["id"] for event in read_events(campaign_dir)] == [
        old_user["id"],
        old_dm["id"],
        boundary["id"],
        current["id"],
    ]
    assert read_current_session_events(campaign_dir) == [current]
    assert read_current_session_events(campaign_dir, after_id=old_dm["id"]) == [current]
    assert read_current_session_events(campaign_dir, after_id=current["id"]) == []


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


def test_event_metadata_is_preserved_when_provided(campaign_dir):
    event = append_event(
        campaign_dir,
        "activity",
        "Bash: pwd",
        metadata={
            "activity_type": "tool_use",
            "tool_name": "Bash",
            "tool_use_id": "tool-1",
        },
    )

    assert event["metadata"] == {
        "activity_type": "tool_use",
        "tool_name": "Bash",
        "tool_use_id": "tool-1",
    }
    assert read_events(campaign_dir)[0] == event


def test_concurrent_appends_get_unique_monotonic_ids(campaign_dir):
    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(
            pool.map(
                lambda index: append_event(campaign_dir, "text", f"event-{index}"),
                range(40),
            )
        )

    assert sorted(event["id"] for event in events) == list(range(1, 41))
    assert [event["id"] for event in read_events(campaign_dir)] == list(range(1, 41))


def test_append_uses_last_valid_tail_event_after_corrupt_line(campaign_dir):
    path = campaign_dir / EVENT_LOG_FILENAME
    path.write_text(
        '{"id": 7, "type": "text", "content": "ok"}\nnot-json\n',
        encoding="utf-8",
    )

    event = append_event(campaign_dir, "text", "next")

    assert event["id"] == 8


def test_append_finds_id_before_event_larger_than_tail_window(campaign_dir):
    path = campaign_dir / EVENT_LOG_FILENAME
    path.write_text(
        json.dumps({"id": 41, "type": "text", "content": "x" * (70 * 1024)})
        + "\nnot-json\n",
        encoding="utf-8",
    )

    event = append_event(campaign_dir, "text", "next")

    assert event["id"] == 42


def test_append_tail_scan_handles_utf8_boundary_inside_multibyte_text(campaign_dir):
    path = campaign_dir / EVENT_LOG_FILENAME
    prefix = json.dumps(
        {"id": 52, "type": "text", "content": ""},
        ensure_ascii=False,
    ).encode("utf-8")[:-2]
    payload = prefix + ("я" * (40 * 1024)).encode("utf-8") + b'"}\nnot-json'
    start = len(payload) - (64 * 1024)
    if (start - len(prefix)) % 2 == 0:
        payload += b"x"
    path.write_bytes(payload + b"\n")

    event = append_event(campaign_dir, "text", "next")

    assert event["id"] == 53
