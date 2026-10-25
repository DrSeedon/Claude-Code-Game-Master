"""The Master's visible work: thinking, dice, saves. The page shows it as a live feed."""

from .inbox import append_jsonl, read_jsonl

ACTIVITY = "activity.jsonl"
KINDS = {"think", "roll", "save", "world", "info"}
MAX_TEXT = 300


def append_activity(screen_dir, kind, text):
    if kind not in KINDS:
        raise ValueError(f"unknown activity kind {kind!r}")
    text = " ".join(str(text).split())[:MAX_TEXT]
    if not text:
        raise ValueError("empty activity")
    return append_jsonl(screen_dir, ACTIVITY, {"kind": kind, "text": text})


def read_activity(screen_dir, after_id=0, tail=None):
    records = read_jsonl(screen_dir, ACTIVITY, after_id)
    return records[-tail:] if tail else records
