"""Sound effects, ambience and music for the screen.

One library is shared by every campaign (world-state/audio-library): a cue is looked up there first, then on Freesound
(CC0 only, free, needs FREESOUND_API_KEY), and only then generated with ElevenLabs. Whatever is found or generated is
kept in the library, so the same sound is never paid twice.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

KINDS = ("sfx", "ambience", "music")
DEFAULT_SECONDS = {"sfx": 3, "ambience": 30, "music": 90}
SECONDS_RANGE = {"sfx": (0.5, 30), "ambience": (5, 30), "music": (10, 300)}
DEFAULT_VOLUME = {"sfx": 0.9, "ambience": 0.45, "music": 0.3}
SFX_CREDITS_PER_SECOND = 10      # measured on the Starter plan (2026-10-25); the price list says 40
MUSIC_CREDITS_PER_SECOND = 15    # about 900 credits a minute; the account counter tells the real price afterwards
MAX_SFX = 6
LIBRARY_DIR = Path("world-state") / "audio-library"
INDEX = "index.json"
FILE_NAME = re.compile(r"^[0-9a-f]{24}\.(mp3|ogg|wav)$")
CONTENT_TYPES = {"mp3": "audio/mpeg", "ogg": "audio/ogg", "wav": "audio/wav"}
_STOP = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to", "from", "sound", "sounds", "effect", "loop", "music", "track"}
FREESOUND = "https://freesound.org/apiv2/search/text/"
LOUDNESS = {"sfx": -16, "ambience": -26, "music": -20}   # integrated LUFS: effects stand out, beds stay under the voices


def normalize(data, ext, kind):
    """Even loudness with ffmpeg (EBU R128 loudnorm) so no sound is inaudible or deafening; unchanged without ffmpeg."""
    if not shutil.which("ffmpeg"):
        return data, ext, False
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / f"in.{ext}", Path(tmp) / "out.mp3"
        src.write_bytes(data)
        result = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                                 "-af", f"loudnorm=I={LOUDNESS[kind]}:TP=-1.5:LRA=11", "-ar", "44100", "-b:a", "160k", str(out)],
                                capture_output=True, timeout=300)
        if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            return data, ext, False
        return out.read_bytes(), "mp3", True


def words(text):
    return {w for w in re.findall(r"\w+", str(text).lower()) if w not in _STOP and len(w) > 1}


def validate_cue(cue, kind, where, blocks=0):
    if not isinstance(cue, dict) or not str(cue.get("cue", "")).strip():
        raise ValueError(f"{where}: needs a text 'cue' describing the sound")
    out = {"cue": " ".join(str(cue["cue"]).split())[:300], "tags": [str(t).strip().lower() for t in cue.get("tags", []) if str(t).strip()][:8]}
    low, high = SECONDS_RANGE[kind]
    seconds = cue.get("seconds", DEFAULT_SECONDS[kind])
    if not isinstance(seconds, (int, float)) or not low <= seconds <= high:
        raise ValueError(f"{where}: seconds must be between {low} and {high}")
    volume = cue.get("volume", DEFAULT_VOLUME[kind])
    if not isinstance(volume, (int, float)) or not 0 <= volume <= 1:
        raise ValueError(f"{where}: volume must be between 0 and 1")
    out.update(seconds=seconds, volume=volume)
    if kind == "sfx" and cue.get("block") is not None:
        if not isinstance(cue["block"], int) or not 0 <= cue["block"] < blocks:
            raise ValueError(f"{where}: block must be the index of a shown block")
        out["block"] = cue["block"]
    if "generate" in cue:
        out["generate"] = bool(cue["generate"])
    return out


def turn_cues(turn):
    """(slot, kind, cue) for every sound the turn asks for; music or ambience left out of the turn keep playing."""
    audio = turn.get("audio") or {}
    found = []
    for kind in ("music", "ambience"):
        if audio.get(kind):
            found.append((kind, kind, audio[kind]))
    for index, cue in enumerate(audio.get("sfx") or []):
        found.append((f"sfx{index}", "sfx", cue))
    return found


def estimate(kind, seconds):
    return int(seconds * (MUSIC_CREDITS_PER_SECOND if kind == "music" else SFX_CREDITS_PER_SECOND) + 0.999)


class Library:
    def __init__(self, root):
        self.dir = Path(root) / LIBRARY_DIR
        self._lock = threading.Lock()

    def entries(self):
        try:
            return json.loads((self.dir / INDEX).read_text(encoding="utf-8"))["entries"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return []

    def path(self, entry):
        return self.dir / "files" / entry["file"]

    def find(self, kind, cue, tags=()):
        """The best stored sound for a cue: the same prompt wins outright, otherwise shared tags and words."""
        wanted, tags = words(cue), {t.lower() for t in tags}
        best, best_score = None, 0
        for entry in self.entries():
            if entry.get("kind") != kind or not self.path(entry).is_file():
                continue
            if entry.get("prompt") and entry["prompt"].strip().lower() == cue.strip().lower():
                return entry
            score = 3 * len(tags & set(entry.get("tags", []))) + len(wanted & words(" ".join([entry.get("title", ""), entry.get("prompt") or ""] + entry.get("tags", []))))
            if score > best_score:
                best, best_score = entry, score
        return best if best_score >= 3 else None

    def add(self, data, ext, kind, title, tags=(), source="local", license="", attribution="", url="", prompt=None, seconds=None, loop=False, key=None,
            normalized=None):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if ext not in CONTENT_TYPES:
            raise ValueError(f"only {sorted(CONTENT_TYPES)} files")
        done = False
        if normalized is None:
            data, ext, done = normalize(data, ext, kind)
        entry_id = hashlib.sha256((key or url or prompt or title).encode() + b"|" + kind.encode()).hexdigest()[:24]
        entry = {"id": entry_id, "kind": kind, "title": title, "tags": sorted({t.lower() for t in tags}), "file": f"{entry_id}.{ext}",
                 "source": source, "license": license, "attribution": attribution, "url": url, "prompt": prompt, "seconds": seconds,
                 "loop": bool(loop), "added": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if done:
            entry["normalized"] = LOUDNESS[kind]
        with self._lock:
            (self.dir / "files").mkdir(parents=True, exist_ok=True)
            self.path(entry).write_bytes(data)
            entries = [e for e in self.entries() if e["id"] != entry_id] + [entry]
            tmp = self.dir / (INDEX + ".tmp")
            tmp.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.dir / INDEX)
        return entry

    def renormalize(self):
        """Bring every stored sound to its kind's loudness (files become mp3); returns how many changed."""
        changed = 0
        for entry in self.entries():
            path = self.path(entry)
            if not path.is_file() or entry.get("normalized"):
                continue
            data, ext, done = normalize(path.read_bytes(), path.suffix.lstrip("."), entry["kind"])
            if not done:
                continue
            with self._lock:
                entries = self.entries()
                for e in entries:
                    if e["id"] == entry["id"]:
                        new_file = f"{e['id']}.mp3"
                        (self.dir / "files" / new_file).write_bytes(data)
                        if new_file != e["file"]:
                            path.unlink()
                        e["file"], e["normalized"] = new_file, LOUDNESS[e["kind"]]
                (self.dir / INDEX).write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
            changed += 1
        return changed

    def remove(self, entry_id):
        with self._lock:
            entries = self.entries()
            kept = [e for e in entries if e["id"] != entry_id]
            if len(kept) == len(entries):
                raise ValueError(f"no library entry {entry_id!r}")
            for e in entries:
                if e["id"] == entry_id and self.path(e).is_file():
                    self.path(e).unlink()
            (self.dir / INDEX).write_text(json.dumps({"entries": kept}, ensure_ascii=False, indent=1), encoding="utf-8")


def download(url, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={"User-Agent": "dm-screen/1.0"})
    with opener(request, timeout=60) as response:
        return response.read()


def extension(url, default="mp3"):
    ext = Path(urllib.parse.urlparse(url).path).suffix.lstrip(".").lower()
    return ext if ext in CONTENT_TYPES else default


class Freesound:
    """CC0 sounds from freesound.org (a free key from freesound.org/apiv2/apply in .env as FREESOUND_API_KEY)."""

    def __init__(self, project_root, opener=urllib.request.urlopen):
        self.project_root, self.opener = Path(project_root), opener

    def key(self):
        env = self.project_root / ".env"
        return (dotenv_values(env).get("FREESOUND_API_KEY") or None) if env.is_file() else None

    def search(self, query, kind):
        key = self.key()
        if not key:
            return None
        low, high = (0.3, 30) if kind == "sfx" else (10, 600)
        params = {"query": query, "filter": f'license:"Creative Commons 0" duration:[{low} TO {high}]', "sort": "rating_desc",
                  "fields": "id,name,tags,username,duration,previews,url,license", "page_size": 5, "token": key}
        request = urllib.request.Request(FREESOUND + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "dm-screen/1.0"})
        with self.opener(request, timeout=30) as response:
            results = json.loads(response.read().decode()).get("results", [])
        return results[0] if results else None


class Director:
    """Resolves the turn's sound cues to files the page can play, spending credits only when it must generate."""

    def __init__(self, project_root, api, speaker, freesound=None, log=None, opener=urllib.request.urlopen):
        self.library = Library(project_root)
        self.api, self.speaker, self.opener = api, speaker, opener
        self.freesound = freesound if freesound is not None else Freesound(project_root, opener)
        self.log = log or (lambda kind, **data: None)

    def _item(self, entry, cue):
        item = {"file": entry["file"], "url": "/library/" + entry["file"], "title": entry.get("title"), "volume": cue["volume"],
                "loop": entry.get("loop", False), "credit": entry.get("attribution") or None, "source": entry.get("source")}
        if "block" in cue:
            item["block"] = cue["block"]
        return item

    def _free(self, kind, cue):
        entry = self.library.find(kind, cue["cue"], cue["tags"])
        if entry or kind == "music":
            return entry
        try:
            hit = self.freesound.search(cue["cue"], kind)
        except Exception as exc:     # Freesound being slow or down never stops the game
            self.log("audio", ok=False, source="freesound", cue=cue["cue"], error=f"{type(exc).__name__}: {exc}")
            return None
        if not hit:
            return None
        url = (hit.get("previews") or {}).get("preview-hq-mp3")
        if not url:
            return None
        entry = self.library.add(download(url, self.opener), "mp3", kind, hit.get("name", cue["cue"]), set(cue["tags"]) | set(hit.get("tags", [])[:8]),
                                 source="freesound", license="CC0", attribution=f"«{hit.get('name')}» by {hit.get('username')} (freesound.org, CC0)",
                                 url=hit.get("url", url), seconds=hit.get("duration"), loop=kind == "ambience", key=f"freesound:{hit.get('id')}")
        self.log("audio", ok=True, source="freesound", sound=kind, cue=cue["cue"], file=entry["file"], title=entry["title"])
        return entry

    def _generate(self, kind, cue):
        before = self.speaker.quota()
        need = estimate(kind, cue["seconds"])
        if need > before["left"]:
            raise RuntimeError(f"Not enough ElevenLabs credits for «{cue['cue']}»: need {need}, left {before['left']}")
        started = time.monotonic()
        if kind == "music":
            data = self.api.music(cue["cue"], cue["seconds"] * 1000, model_id=self.speaker_config().get("music_model", "music_v1"))
        else:
            data = self.api.sound(cue["cue"], seconds=cue["seconds"], loop=kind == "ambience")
        credits = self.speaker.spent(before, need)
        entry = self.library.add(data, "mp3", kind, cue["cue"], cue["tags"], source="elevenlabs", license="ElevenLabs paid plan",
                                 prompt=cue["cue"], seconds=cue["seconds"], loop=kind != "sfx")
        self.log("audio", ok=True, source="elevenlabs", sound=kind, cue=cue["cue"], seconds=cue["seconds"], credits=credits, file=entry["file"],
                 ms=round((time.monotonic() - started) * 1000))
        return entry

    def speaker_config(self):
        from . import speech
        return speech.load_config(self.speaker.dir)

    def plan(self, turn):
        """Credits the turn's sounds would cost now: nothing for what the library already has."""
        found, credits, cues = 0, 0, turn_cues(turn)
        for _, kind, cue in cues:
            if self.library.find(kind, cue["cue"], cue["tags"]):
                found += 1
            elif cue.get("generate", True):
                credits += estimate(kind, cue["seconds"])
        return {"cues": len(cues), "found": found, "credits": credits}

    def resolve(self, turn, generate=False):
        """{'music','ambience','sfx'} for the page. 'keep' means the turn did not mention it; None means silence."""
        audio = turn.get("audio") or {}
        out = {kind: (None if kind in audio and not audio[kind] else "keep") for kind in ("music", "ambience")}
        out["sfx"], missing = [], []
        for slot, kind, cue in turn_cues(turn):
            try:
                entry = self._free(kind, cue)
                if not entry and generate and cue.get("generate", True):
                    entry = self._generate(kind, cue)
            except Exception as exc:
                self.log("audio", ok=False, sound=kind, cue=cue["cue"], error=f"{type(exc).__name__}: {exc}")
                entry = None
            if not entry:
                missing.append(cue["cue"])
                continue
            if kind == "sfx":
                out["sfx"].append(self._item(entry, cue))
            else:
                out[kind] = self._item({**entry, "loop": True}, cue)
        out["missing"] = missing
        return out
