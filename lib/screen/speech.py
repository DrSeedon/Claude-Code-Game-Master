"""Voices for the screen: a narrator and per-character speech through ElevenLabs, cached on disk.

A turn's story blocks become a script: narration is read by the campaign narrator, a paragraph that
starts with <b>Name:</b> and a quoted line is read by that character's voice. Each audio file is cached by
its content, so the same text with the same voice never costs credits twice.
"""

import hashlib
import html
import json
import os
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

API = "https://api.elevenlabs.io"
MODEL_COST = {"eleven_flash_v2_5": 0.5, "eleven_turbo_v2_5": 0.5}
NO_LANGUAGE_CODE = {"eleven_multilingual_v2"}
ENVIRONMENTS = {"small_room", "big_room", "hall", "tunnel", "street", "valley", "forest"}
FILTERS = {"old_radio", "robot", "cheap_microphone", "phone", "low_quality_phone", "bright_phone"}
NOISES = {"call_center", "cafe", "city", "keyboard"}
RANGES = {"distance": (0, 1), "send_level": (0, 1), "pan": (-1, 1)}
IDS = {"environment_id": ENVIRONMENTS, "filter_preset_id": FILTERS, "background_noise_id": NOISES}
DEFAULTS = {"model": "eleven_flash_v2_5", "language": "ru", "output_format": "mp3_44100_128",
            "stability": 0.5, "similarity_boost": 0.75, "narrator": {}, "default": {}}
CONFIG_FILE = "speech.json"
LEDGER = "usage.jsonl"
LEDGER_DAYS = 30
AUDIO_DIR = "audio"
CHUNK = 600
_TAG = re.compile(r"<[^>]+>")
_DIALOGUE = re.compile(r"\s*<p[^>]*>\s*<b>(?P<who>[^<]{1,60}?):</b>\s*(?P<rest>.*)</p>\s*$", re.S)
_QUOTED = re.compile(r"^[«\"“](?P<line>.+)[»\"”]$", re.S)
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


class SpeechUnavailable(RuntimeError):
    """No key or no narrator voice: speech cannot work yet."""


class SpeechError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def load_api_key(project_root, environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("ELEVENLABS_API_KEY"):
        return environ["ELEVENLABS_API_KEY"]
    env_file = Path(project_root) / ".env"
    return (dotenv_values(env_file).get("ELEVENLABS_API_KEY") or None) if env_file.is_file() else None


def _plain(markup):
    return " ".join(html.unescape(_TAG.sub("", markup)).split())


def _split(text, limit):
    chunks, current = [], ""
    for sentence in _SENTENCE.split(text):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit) or limit
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def script_from_blocks(blocks, max_chars=CHUNK):
    """Segments {'speaker','text','blocks'} in reading order; headings, dice, lists and UI boxes are skipped."""
    segments, narration = [], None

    def flush():
        nonlocal narration
        if narration:
            for i, chunk in enumerate(_split(narration["text"], max_chars)):
                segments.append({"speaker": "narrator", "text": chunk, "blocks": narration["blocks"] if i == 0 else narration["blocks"][-1:]})
        narration = None

    for index, raw in enumerate(blocks):
        if not re.match(r"\s*<p[\s>]", raw):
            continue
        dialogue = _DIALOGUE.match(raw)
        rest = _plain(dialogue.group("rest")) if dialogue else ""
        quoted = _QUOTED.match(rest) if dialogue else None
        if quoted:
            flush()
            segments.append({"speaker": dialogue.group("who").strip(), "text": quoted.group("line").strip(), "blocks": [index]})
            continue
        text = _plain(raw)
        if not text or text.startswith("🎲"):
            continue
        if narration:
            narration["text"] += " " + text
            narration["blocks"].append(index)
        else:
            narration = {"text": text, "blocks": [index]}
    flush()
    return segments


def validate_effects(effects):
    out = {}
    for key, value in effects.items():
        if key in IDS:
            if value not in IDS[key]:
                raise ValueError(f"unknown {key} {value!r}; choose from {sorted(IDS[key])}")
        elif key in RANGES:
            low, high = RANGES[key]
            if not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
        else:
            raise ValueError(f"unknown effect {key!r}")
        out[key] = value
    return out


def load_config(screen_dir):
    path = Path(screen_dir) / CONFIG_FILE
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        user = {}
    return {**DEFAULTS, **user}


def characters_from_world(campaign_dir):
    """Lowercased name -> voice profile for every player and NPC that has one."""
    try:
        nodes = json.loads((Path(campaign_dir) / "world.json").read_text(encoding="utf-8"))["nodes"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}
    found = {}
    for node in nodes.values():
        data = node.get("data")
        if node.get("type") in ("npc", "player") and isinstance(data, dict) and data.get("voice"):
            for name in [node["name"], *data.get("aliases", [])]:
                found[name.lower()] = data["voice"]
    return found


def _lookup(characters, speaker):
    key = speaker.lower()
    if key in characters:
        return characters[key]
    for name, voice in characters.items():
        if name.split()[0] == key or name.startswith(key + " "):
            return voice
    return None


def resolve_voice(speaker, config, characters):
    base = {"model": config.get("model"), "stability": config.get("stability"), "similarity_boost": config.get("similarity_boost"), "effects": {}}
    if speaker == "narrator":
        layers = [config.get("narrator") or {}]
    else:
        layers = [config.get("default") or {}, _lookup(characters, speaker) or {}]
    for layer in layers:
        base.update({k: v for k, v in layer.items() if v is not None})
    if not base.get("voice_id"):
        raise SpeechUnavailable("the narrator voice is not set" if speaker == "narrator" else f"no voice for {speaker!r} and no default voice")
    return base


def _credits(text, model):
    return len(text) * MODEL_COST.get(model, 1.0)


def estimate_credits(segments, config, characters=None):
    total = 0.0
    for seg in segments:
        model = config.get("model")
        if characters is not None:
            model = resolve_voice(seg["speaker"], config, characters)["model"]
        total += _credits(seg["text"], model)
    return int(total + 0.999)


def _cache_key(voice, text, config):
    material = json.dumps([voice["voice_id"], voice["model"], voice["stability"], voice["similarity_boost"],
                           voice["effects"], config["output_format"], config["language"], text], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode()).hexdigest() + ".mp3"


class ElevenLabsApi:
    def __init__(self, project_root, opener=urllib.request.urlopen):
        self.project_root, self.opener = project_root, opener

    def has_key(self):
        return bool(load_api_key(self.project_root))

    def _call(self, method, path, body=None):
        key = load_api_key(self.project_root)
        if not key:
            raise SpeechUnavailable("ELEVENLABS_API_KEY is not set (put it in the project .env)")
        request = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with self.opener(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode())["detail"]
                message = detail.get("message") if isinstance(detail, dict) else str(detail)
            except Exception:
                message = exc.reason
            raise SpeechError(f"ElevenLabs: {message}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise SpeechError(f"ElevenLabs is unreachable: {exc.reason}", 502) from exc

    def tts(self, voice_id, body, output_format):
        return self._call("POST", f"/v1/text-to-speech/{voice_id}?output_format={output_format}", body)

    def subscription(self):
        return json.loads(self._call("GET", "/v1/user/subscription"))

    def voices(self):
        return json.loads(self._call("GET", "/v1/voices"))["voices"]


class Speaker:
    def __init__(self, screen_dir, api, characters):
        self.dir, self.api, self.characters = Path(screen_dir), api, characters
        self._ledger_lock = threading.Lock()

    def _segments(self, turn, config, characters):
        out = []
        for seg in script_from_blocks(turn.get("blocks", [])):
            voice = resolve_voice(seg["speaker"], config, characters)
            out.append({**seg, "voice": voice, "file": _cache_key(voice, seg["text"], config)})
        return out

    def available(self):
        has_key = getattr(self.api, "has_key", lambda: True)()
        return has_key and bool((load_config(self.dir).get("narrator") or {}).get("voice_id"))

    def plan(self, turn):
        config, characters = load_config(self.dir), self.characters()
        segments = self._segments(turn, config, characters)
        todo = [s for s in segments if not (self.dir / AUDIO_DIR / s["file"]).is_file()]
        return {"segments": len(segments), "cached": len(segments) - len(todo),
                "credits": int(sum(_credits(s["text"], s["voice"]["model"]) for s in todo) + 0.999)}

    def _ledger_used(self):
        path = self.dir / AUDIO_DIR / LEDGER
        if not path.is_file():
            return 0
        since = datetime.now(timezone.utc) - timedelta(days=LEDGER_DAYS)
        total = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if datetime.strptime(entry["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) >= since:
                total += entry["credits"]
        return total

    def quota(self):
        """The account counter can lag or be stale, so our own ledger of the last 30 days wins when it is larger."""
        sub = self.api.subscription()
        limit = int(sub["character_limit"])
        used = max(int(sub["character_count"]), self._ledger_used())
        return {"used": used, "limit": limit, "left": max(0, limit - used)}

    def _log_spending(self, credits):
        path = self.dir / AUDIO_DIR / LEDGER
        entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "credits": credits}
        with self._ledger_lock:
            with open(path, "a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

    def _synthesize(self, seg, config):
        voice = seg["voice"]
        body = {"text": seg["text"], "model_id": voice["model"], "apply_text_normalization": "auto",
                "voice_settings": {"stability": voice["stability"], "similarity_boost": voice["similarity_boost"]}}
        if config.get("language") and voice["model"] not in NO_LANGUAGE_CODE:
            body["language_code"] = config["language"]
        if voice["effects"]:
            body["audio_effects"] = validate_effects(voice["effects"])
        audio = self.api.tts(voice["voice_id"], body, config["output_format"])
        path = self.dir / AUDIO_DIR / seg["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(audio)
        tmp.replace(path)
        self._log_spending(int(_credits(seg["text"], voice["model"]) + 0.999))

    def render(self, turn):
        config, characters = load_config(self.dir), self.characters()
        segments = self._segments(turn, config, characters)
        todo = [s for s in segments if not (self.dir / AUDIO_DIR / s["file"]).is_file()]
        if todo:
            need = int(sum(_credits(s["text"], s["voice"]["model"]) for s in todo) + 0.999)
            left = self.quota()["left"]
            if need > left:
                raise SpeechError(f"Not enough ElevenLabs credits: need {need}, left {left}", 402)
            with ThreadPoolExecutor(3) as pool:
                list(pool.map(lambda s: self._synthesize(s, config), todo))
        return [{k: seg[k] for k in ("speaker", "text", "blocks", "file")} for seg in segments]
