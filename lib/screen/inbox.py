"""Append-only queue of player actions sent from the screen; the DM follows it with `dm-screen.sh listen`."""

import fcntl
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

INBOX = "inbox.jsonl"
SOURCES = {"button": "button", "voice": "voice", "text": "text"}
MAX_TEXT = 1000


def one_line(value):
    """One line of plain text: no line breaks, control or format characters. Each action is one line of the
    master's message, so a newline in a name or a text would let a player forge a line of their own."""
    return " ".join("".join(ch for ch in str(value) if unicodedata.category(ch) not in ("Cc", "Cf")
                            or ch.isspace()).split())


def append_jsonl(screen_dir, filename, fields):
    """Append one record with the next id and a timestamp; safe under concurrent writers."""
    screen_dir = Path(screen_dir)
    screen_dir.mkdir(parents=True, exist_ok=True)
    with open(screen_dir / f".{filename}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = read_jsonl(screen_dir, filename)
        record = {"id": (records[-1]["id"] if records else 0) + 1,
                  "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **fields}
        with open(screen_dir / filename, "a", encoding="utf-8") as out:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_jsonl(screen_dir, filename, after_id=0):
    path = Path(screen_dir) / filename
    if not path.is_file():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in records if r["id"] > after_id]


def append_event(screen_dir, who, source, text):
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    text = one_line(text)[:MAX_TEXT]
    if not text:
        raise ValueError("empty action")
    return append_jsonl(screen_dir, INBOX, {"who": one_line(who)[:40] or "Everyone", "source": source, "text": text})


def read_events(screen_dir, after_id=0):
    return read_jsonl(screen_dir, INBOX, after_id)


def format_line(event):
    """Records written before the who/text clean-up go through it here too."""
    return f"[screen #{event['id']}] {one_line(event['who'])} ({SOURCES[event['source']]}): {one_line(event['text'])}"
