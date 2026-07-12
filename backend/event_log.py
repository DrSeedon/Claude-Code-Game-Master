"""Append-only JSONL event log per campaign — replaces chat_history.json.

Each line is one event: {"id": int, "type": str, "content": str, "timestamp": str}.
Monotonic ids let clients request replay via `after_id` on reconnect.
"""

import json
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


def _next_id(campaign_dir: Path) -> int:
    path = _log_path(campaign_dir)
    if not path.exists():
        return 1
    last_id = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last_id = max(last_id, json.loads(line).get("id", 0))
        except json.JSONDecodeError:
            continue
    return last_id + 1


def append_event(
    campaign_dir: Path,
    event_type: str,
    content: str,
    timestamp: Optional[str] = None,
) -> Dict:
    """Append a single event to the log. Returns the stored event (with id)."""
    campaign_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "id": _next_id(campaign_dir),
        "type": event_type,
        "content": content,
        "timestamp": timestamp or _now_iso(),
    }
    with open(_log_path(campaign_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event
