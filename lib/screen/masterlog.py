"""The master's console log (owner request 2026-10-28): what the online master was given, said and ran, for the page.

<screen>/master-log.jsonl holds one JSON object per line: {"id", "ts", "kind", "master", "text", ...extra}. Kinds:
"batch" (the message the master was given), "text" (the master's own words), "tool" (a call), "result" (a tool's
output, "error": true when it failed), "turn" (a turn was published) and "note" (driver events). The driver and the
hub bridge write it (backend/screen_driver.py, backend/hub_master.py); the screen server serves it only with
DM_SCREEN_MASTER_CONSOLE=1, because it shows hidden rolls and plot notes. Every text is redacted before it is
written; a failure to log never breaks a turn. Stdlib only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

LOG = "master-log.jsonl"
KINDS = {"batch", "text", "tool", "result", "turn", "note"}
MASTERS = {"sdk", "hub", "driver"}
CAPS = {"batch": 8000, "text": 8000, "tool": 2000, "result": 2000, "turn": 2000, "note": 2000}
MORE = " …"
ROTATE_AT = 2 * 1024 * 1024
KEEP = 1024 * 1024
TAIL_BYTES = 64 * 1024
REDACTED = "[скрыто]"
MAX_ID = 2 ** 40

logger = logging.getLogger("dnd-play")
_LOCK = threading.Lock()

# Token shapes. A run of 40+ key-like characters counts only with a digit and both letter cases (a base64 key), or
# as pure hex not followed by a file extension (sha256 audio file names stay readable).
_PATTERNS = [
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
]
_BEARER = re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+/=\-]{8,}", re.IGNORECASE)
_AUTH_HEADER = re.compile(r"(\bAuthorization\s*[:=]\s*(?:(?:Basic|Bearer|Digest|Token)\s+)?)(?!\[)[^\s\"',;]+", re.IGNORECASE)
_USERINFO = re.compile(r"(\b[a-z][a-z0-9+.\-]*://[^/\s:@]+:)[^/\s@]+(@)", re.IGNORECASE)
# A secret-named field: the word alone or as a part of a longer name (DND_AUTH_PASSWORD, ELEVENLABS_API_KEY, apiKey,
# refreshToken). A name is split at "_", "-", "." and camelCase humps, so "monkey" or "max_tokens" are not secrets.
_STRONG = {"password", "passwd", "pwd", "passphrase", "secret", "token", "apikey", "accesskey", "privatekey",
           "credential", "credentials", "authtoken", "accesstoken", "refreshtoken", "secretkey"}
_PAIRS = {("api", "key"), ("access", "key"), ("private", "key"), ("secret", "key"), ("client", "secret")}
_WEAK = {"key", "auth"}
_HUMP = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
_NAME = r"[A-Za-z][A-Za-z0-9_\-]{0,80}"
_ENV_LINE = re.compile(r"(?m)^([ \t]*(?:export[ \t]+)?([A-Z][A-Z0-9_]{0,80})[ \t]*=[ \t]*)(?!\[скрыто\])(\S[^\n]*)$")
_ASSIGN = re.compile(rf"(?<![A-Za-z0-9_\-])({_NAME})(\s*(=|:)\s*)(?!\[скрыто\]|//)")
_VALUE = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|[^\s&;,\"'{}\[\]()]+")
_JSON_FIELD = re.compile(r"(\"([A-Za-z0-9_\-]{1,80})\"\s*:\s*\")((?:[^\"\\\n]|\\.)+)(\")")
_HEX = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{40,}(?![A-Za-z0-9]|\.[A-Za-z])")
_RUN = re.compile(r"(?<![A-Za-z0-9+_\-])[A-Za-z0-9+_\-]{40,}={0,2}(?![A-Za-z0-9+_\-])")


def _keylike(match):
    run = match.group(0)
    if re.search(r"\d", run) and re.search(r"[a-z]", run) and re.search(r"[A-Z]", run):
        return REDACTED
    return run


def _secret_name(name, strict=False):
    """True for a name that holds a secret. `strict` (a "name: value" pair or a JSON field, as in prose and data)
    refuses a bare "key" (a music key, a dict key); "key=..." still counts."""
    parts = [p.lower() for chunk in re.split(r"[_\-.]+", name) for p in _HUMP.findall(chunk)]
    if not parts:
        return False
    if any(p in _STRONG for p in parts) or any(pair in _PAIRS for pair in zip(parts, parts[1:])):
        return True
    if any(p in _WEAK for p in parts):
        return len(parts) > 1 or not strict or parts[0] != "key"
    return False


def _assignments(text):
    """`name=value` / `name: value` with a secret name: the value redacted. A name that is not a secret consumes
    nothing, so "a: token=x" still finds the token."""
    out, pos = [], 0
    while (match := _ASSIGN.search(text, pos)) is not None:
        value = _VALUE.match(text, match.end())
        if value is None or not _secret_name(match.group(1), strict=match.group(3) == ":"):
            out.append(text[pos:match.start(1) + 1])
            pos = match.start(1) + 1
            continue
        out.append(text[pos:match.end()] + REDACTED)
        pos = value.end()
    out.append(text[pos:])
    return "".join(out)


def redact(text, secrets=()):
    """`text` without the given secrets (the hub ticket, the webhook URL) and without token-shaped strings."""
    text = str(text)
    for secret in sorted({s for s in secrets if isinstance(s, str) and len(s) >= 6}, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    text = _USERINFO.sub(lambda m: m.group(1) + REDACTED + m.group(2), text)
    text = _AUTH_HEADER.sub(lambda m: m.group(1) + REDACTED, text)
    text = _BEARER.sub(lambda m: m.group(1) + REDACTED, text)
    text = _JSON_FIELD.sub(lambda m: m.group(1) + REDACTED + m.group(4) if _secret_name(m.group(2), strict=True) else m.group(0), text)
    text = _ENV_LINE.sub(lambda m: m.group(1) + REDACTED if _secret_name(m.group(2)) else m.group(0), text)
    text = _assignments(text)
    text = _HEX.sub(REDACTED, text)
    return _RUN.sub(_keylike, text)


def env_secrets(env=None, env_file=None):
    """The values of the secret-named variables the process can see (os.environ and the project .env): redacted
    literally, whatever their shape, since a master's `cat .env` or `env` would print them."""
    found = set((os.environ if env is None else env).items())
    try:
        for line in Path(env_file).read_text(encoding="utf-8").splitlines() if env_file else ():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep:
                found.add((name.strip(), value.strip().strip("\"'")))
    except OSError:
        pass
    return sorted({v for k, v in found if isinstance(v, str) and len(v) >= 8 and _secret_name(k)}, key=len, reverse=True)


def cap(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + MORE


def path(sdir):
    return Path(sdir) / LOG


def _last_id(file):
    """The id of the newest readable line, from the file's tail (a full scan only when the tail holds none)."""
    try:
        size = file.stat().st_size
    except FileNotFoundError:
        return 0
    with open(file, "rb") as handle:
        for start in (max(0, size - TAIL_BYTES), 0):
            handle.seek(start)
            lines = handle.read().splitlines()
            if start:
                lines = lines[1:]          # the first line of a tail read may be cut
            for raw in reversed(lines):
                entry = _parse(raw)
                if entry is not None:
                    return entry["id"]
            if not start:
                break
    return 0


def _parse(raw):
    try:
        entry = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(entry, dict):
        return None
    ident = entry.get("id")
    # A sane id only: the master's sandbox can write this file, and a forged huge id would stop the page (ids past
    # 2**53 lose precision in JavaScript, so every later entry would look old).
    return entry if type(ident) is int and 0 < ident < MAX_ID else None


def _rotate(file):
    """Keep the newest ~KEEP bytes, whole lines only; ids go on from where they were."""
    with open(file, "rb") as handle:
        handle.seek(max(0, file.stat().st_size - KEEP))
        data = handle.read()
    cut = data.find(b"\n")
    data = data[cut + 1:] if cut >= 0 else b""
    tmp = file.with_name(f".{file.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, file)


def append(sdir, kind, text, master="driver", secrets=(), **extra):
    """Add one entry; returns it, or None when logging failed (it never raises)."""
    try:
        if kind not in KINDS:
            raise ValueError(f"unknown master log kind {kind!r}")
        text = cap(redact(text, secrets), CAPS[kind])
        clean = {k: (cap(redact(v, secrets), 300) if isinstance(v, str) else v) for k, v in extra.items()
                 if k not in ("id", "ts", "kind", "master", "text")}
        file = path(sdir)
        with _LOCK:
            file.parent.mkdir(parents=True, exist_ok=True)
            entry = {"id": _last_id(file) + 1, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind,
                     "master": master if master in MASTERS else "driver", "text": text, **clean}
            line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
            fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
            if file.stat().st_size > ROTATE_AT:
                _rotate(file)
        return entry
    except Exception as exc:
        logger.warning("master log entry skipped: %s: %s", type(exc).__name__, exc)
        return None


def read(sdir, after=0, limit=300):
    """Entries with id > `after`, the newest `limit` of them, oldest first; broken lines are skipped."""
    try:
        data = path(sdir).read_bytes()
    except FileNotFoundError:
        return []
    entries = [e for e in map(_parse, data.splitlines()) if e is not None and e["id"] > after]
    return entries[-limit:] if limit else entries


def last_id(sdir):
    try:
        return _last_id(path(sdir))
    except OSError:
        return 0


def tail(sdir, offset, after, limit=500):
    """New entries since byte `offset` (only the new bytes are read): (entries with id > after, the new offset).
    A file that shrank was rotated: then it is read whole, by id."""
    file = path(sdir)
    try:
        size = file.stat().st_size
    except FileNotFoundError:
        return [], 0
    if size < offset:
        return read(sdir, after, limit), size
    with open(file, "rb") as handle:
        handle.seek(offset)
        data = handle.read(size - offset)
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset              # a line still being written: next time
    entries = [e for e in map(_parse, data[:end].splitlines()) if e is not None and e["id"] > after]
    return entries[-limit:], offset + end + 1
