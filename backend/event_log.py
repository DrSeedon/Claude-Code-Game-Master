"""Append-only JSONL event log per campaign — replaces chat_history.json.

Each line is one event: {"id": int, "type": str, "content": str, "timestamp": str}.
Monotonic ids let clients request replay via `after_id` on reconnect.
"""

import fcntl
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

EVENT_LOG_FILENAME = "events.jsonl"


def _log_path(campaign_dir: Path) -> Path:
    return campaign_dir / EVENT_LOG_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_events(campaign_dir: Path, after_id: int = 0) -> List[Dict]:
    """Read events from the log, optionally only those after a given id."""
    path = _log_path(campaign_dir)
    if not path.exists():
        return []

    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("id", 0) > after_id:
            events.append(event)
    return events


def read_current_session_events(
    campaign_dir: Path,
    after_id: int = 0,
) -> List[Dict]:
    """Read replayable chat events after the latest session boundary.

    Reset markers stay in the append-only log for auditability, but neither the
    marker nor events from earlier AI conversations are replayed into the chat.
    """
    events = read_events(campaign_dir)
    latest_boundary = max(
        (
            event.get("id", 0)
            for event in events
            if event.get("type") == "session_reset"
        ),
        default=0,
    )
    replay_after = max(after_id, latest_boundary)
    return [
        event
        for event in events
        if event.get("id", 0) > replay_after
        and event.get("type") != "session_reset"
    ]


def _last_id_from_tail(file_obj, chunk_size: int = 64 * 1024) -> int:
    """Find the last valid id, expanding only when one event exceeds the tail window."""
    file_obj.seek(0, os.SEEK_END)
    end = file_obj.tell()
    if end == 0:
        return 0

    window = chunk_size
    while True:
        start = max(0, end - window)
        file_obj.seek(start)
        tail = file_obj.read()
        if start:
            tail = tail.split("\n", 1)[-1]

        for line in reversed(tail.splitlines()):
            try:
                event_id = json.loads(line).get("id")
            except (json.JSONDecodeError, AttributeError):
                continue
            if isinstance(event_id, int):
                return event_id

        if start == 0:
            return 0
        window *= 2


def append_event(
    campaign_dir: Path,
    event_type: str,
    content: str,
    timestamp: Optional[str] = None,
) -> Dict:
    """Append a single event to the log. Returns the stored event (with id)."""
    campaign_dir.mkdir(parents=True, exist_ok=True)
    path = _log_path(campaign_dir)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        event = {
            "id": _last_id_from_tail(f) + 1,
            "type": event_type,
            "content": content,
            "timestamp": timestamp or _now_iso(),
        }
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return event
