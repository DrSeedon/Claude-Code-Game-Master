"""One structured log for the whole screen: every request, word, price, turn and error, one JSON line each.

Lives in <campaign>/screen/log/YYYY-MM-DD.jsonl (git-ignored). Secrets are scrubbed before anything is written
and a failing log never breaks the game.
"""

import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_DIR = "log"
SECRET_KEYS = {"token", "key", "api_key", "apikey", "authorization", "xi-api-key", "x-screen-token", "password", "secret"}
_PATTERNS = [
    (re.compile(r"sk_[0-9a-zA-Z]{20,}"), "[redacted]"),
    (re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40,}(?![0-9a-fA-F])"), "[redacted]"),
    (re.compile(r"(token|key|api_key)=[^&\s\"']+", re.IGNORECASE), r"\1=[redacted]"),
    (re.compile(r"\b(Token|Bearer)\s+\S+"), r"\1 [redacted]"),
]
_LOCK = threading.Lock()


def redact(value):
    if isinstance(value, dict):
        return {k: "[redacted]" if str(k).lower() in SECRET_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern, replacement in _PATTERNS:
            value = pattern.sub(replacement, value)
    return value


def _now():
    return datetime.now(timezone.utc)


def log(screen_dir, kind, **data):
    try:
        moment = _now()
        entry = {"ts": moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z", "kind": kind, **redact(data)}
        folder = Path(screen_dir) / LOG_DIR
        folder.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with _LOCK, open(folder / f"{moment.strftime('%Y-%m-%d')}.jsonl", "a", encoding="utf-8") as out:
            out.write(line)
        return entry
    except Exception:
        return None


def read(screen_dir, kinds=None, since=None, tail=None, errors=False):
    """Entries in time order. since: a timedelta (look back that far; negative means nothing is that new)."""
    folder = Path(screen_dir) / LOG_DIR
    if not folder.is_dir():
        return []
    cutoff = (_now() - since).strftime("%Y-%m-%dT%H:%M:%S.000Z") if since is not None else None
    found = []
    for path in sorted(folder.glob("*.jsonl")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if kinds and entry["kind"] not in kinds:
                continue
            if errors and not (entry["kind"] == "error" or entry.get("status", 0) >= 400 or entry.get("ok") is False):
                continue
            if cutoff and entry["ts"] < cutoff:
                continue
            found.append(entry)
    return found[-tail:] if tail else found


def summary(screen_dir):
    entries = read(screen_dir)
    kinds = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    tts = [e for e in entries if e["kind"] == "tts"]
    return {"events": len(entries), "kinds": kinds,
            "tts_credits": sum(e.get("credits", 0) for e in tts), "tts_chars": sum(e.get("chars", 0) for e in tts if not e.get("cached")),
            "tts_cached": sum(1 for e in tts if e.get("cached")),
            "stt_seconds": round(sum(e.get("seconds", 0) for e in entries if e["kind"] == "stt"), 1),
            "stt_words": sum(len(e.get("words", [])) for e in entries if e["kind"] == "stt"),
            "errors": len(read(screen_dir, errors=True))}


def world_snapshot(campaign_dir):
    """Values worth having next to every turn when a bug has to be traced: time, place, HP, purse, quests."""
    campaign_dir = Path(campaign_dir)
    snap = {}
    try:
        overview = json.loads((campaign_dir / "campaign-overview.json").read_text(encoding="utf-8"))
        snap.update(date=overview.get("current_date"), time=overview.get("precise_time"),
                    location=(overview.get("player_position") or {}).get("current_location"))
        nodes = json.loads((campaign_dir / "world.json").read_text(encoding="utf-8"))["nodes"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return snap
    hp = lambda d: (f"{d['hp']['current']}/{d['hp']['max']}" if isinstance(d.get("hp"), dict) else None)
    player = next((n for n in nodes.values() if n.get("type") == "player"), None)
    if player:
        snap["player"] = {"name": player["name"], "hp": hp(player["data"]), "money": player["data"].get("money")}
    snap["party"] = [{"name": n["name"], "hp": hp(n["data"])} for n in nodes.values() if n.get("type") == "npc" and n["data"].get("party_member")]
    snap["quests"] = [{"name": n["name"], "done": sum(1 for o in n["data"].get("objectives", []) if isinstance(o, dict) and o.get("done")),
                       "total": len(n["data"].get("objectives", []))}
                      for n in nodes.values() if n.get("type") == "quest" and n["data"].get("status", "active") == "active"]
    return snap
