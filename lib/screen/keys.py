"""Putting an ElevenLabs key into the project .env without ever printing it, and checking what it may do."""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

_KEY = re.compile(r"^sk_[A-Za-z0-9]{20,}$")
VAR = "ELEVENLABS_API_KEY"


def store_key(env_path, key):
    """Replace (or add) the key line; a copy of the old file is kept as .env.bak. The key is never printed."""
    key = key.strip()
    if not _KEY.match(key):
        raise ValueError("the clipboard does not hold an ElevenLabs key (it starts with sk_ and has no spaces)")
    env_path = Path(env_path)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    if env_path.is_file():
        backup = env_path.with_name(env_path.name + ".bak")
        backup.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(backup, 0o600)
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(VAR + "="):
            lines[i], replaced = f"{VAR}={key}", True
    if not replaced:
        lines.append(f"{VAR}={key}")
    tmp = env_path.with_name(env_path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(env_path)


def _call(method, path, body, key):
    request = urllib.request.Request("https://api.elevenlabs.io" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode()[:400]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:400]
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def permission_report(key, call=_call):
    """What the key may do, found with requests that create, change and spend nothing; None when a probe did not answer."""
    def allowed(status, text):
        return None if status is None else not (status == 401 and "permission" in text)

    checks = {"read_voices": ("GET", "/v1/voices", None), "read_models": ("GET", "/v1/models", None), "read_user": ("GET", "/v1/user/subscription", None),
              "history": ("GET", "/v1/history?page_size=1", None), "voices_write": ("DELETE", "/v1/voices/doesNotExist000000", None),
              "voice_design": ("POST", "/v1/text-to-voice/design", {"voice_description": "x"}), "sound_effects": ("POST", "/v1/sound-generation", {"text": ""}),
              "pronunciation": ("GET", "/v1/pronunciation-dictionaries", None)}
    return {name: allowed(*call(m, p, b, key)) for name, (m, p, b) in checks.items()}
