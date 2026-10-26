"""Local web server for the play screen: page, live event stream, player actions, microphone.

Online limits come from the environment (0 or unset = no limit, the laptop default): DM_SCREEN_DAILY_CREDITS and
DM_SCREEN_TURN_CREDITS (speech and sound credits), DM_SCREEN_SOUND_GENERATION=0 (library and free sounds only),
DM_SCREEN_MAX_PENDING (actions waiting for the master) and DM_SCREEN_DAILY_VOICE_MB (microphone uploads a day).
The daily ledger is <screen>/spend.json unless DM_SCREEN_SPEND_FILE names one (the online driver shares one file
across campaigns, so a switch does not reset the day). A credit cap also turns the page's Auto speech off.
"""

import json
import os
import re
import secrets
import traceback
import select
import socket
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import activity, audio as audio_module, cli, eventlog, inbox, speech as speech_module, voice

TEMPLATE = Path(__file__).with_name("template.html")
MAX_AUDIO = 8 * 1024 * 1024
QUIET_PATHS = {"/api/state", "/api/events", "/api/clients", "/art.png"}
MAX_UI_EVENTS, MAX_UI_BYTES, MAX_LOG_BODY = 50, 4000, 256 * 1024
_AUDIO_NAME = re.compile(r"^[0-9a-f]{64}\.mp3$|^ambient-[\w-]{1,60}\.mp3$")
_LENGTH = re.compile(r"[0-9]{1,12}")
_RANGE = re.compile(r"bytes=([0-9]*)-([0-9]*)")
POLL_SECONDS = 0.3
PING_SECONDS = 15
QUOTA_SECONDS = 60
SPEND, SPEND_DAYS = "spend.json", 14
MASTER_STATUS = "online-play-status.json"
_SPEND_LOCK = threading.Lock()


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _env_number(name):
    """A limit from the environment; unset, bad or negative means no limit (0)."""
    try:
        value = max(0.0, float(os.environ.get(name) or 0))
    except ValueError:
        return 0
    return int(value) if value.is_integer() else value


def spend_path(screen_dir):
    """The daily ledger: <screen>/spend.json, or DM_SCREEN_SPEND_FILE (the online table shares one across campaigns)."""
    return Path(os.environ["DM_SCREEN_SPEND_FILE"]) if os.environ.get("DM_SCREEN_SPEND_FILE") else Path(screen_dir) / SPEND


def spent_today(screen_dir, key):
    """What today (local date) has used: 'credits' really spent on speech and sounds, 'voice_bytes' uploaded."""
    day = (_read_json(spend_path(screen_dir)) or {}).get(datetime.now().date().isoformat())
    return day.get(key, 0) if isinstance(day, dict) else 0


def add_spend(screen_dir, key, amount, cap=0):
    """Add to today's ledger. With a `cap`, check and add are one step: over the cap nothing is added, False returns."""
    path, today = spend_path(screen_dir), datetime.now().date().isoformat()
    with _SPEND_LOCK:
        data = _read_json(path)
        data = data if isinstance(data, dict) else {}
        day = data.get(today) if isinstance(data.get(today), dict) else {}
        if cap and day.get(key, 0) + amount > cap:
            return False
        data[today] = {**day, key: day.get(key, 0) + amount}
        data = {d: data[d] for d in sorted(data)[-SPEND_DAYS:]}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
    return True


def _ledger_size(path):
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _ledger_since(path, offset):
    """Credits the speaker's own ledger (speech.Speaker.spent) recorded after byte `offset`."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            tail = f.read().decode("utf-8", "replace")
    except FileNotFoundError:
        return 0
    total = 0
    for line in tail.splitlines():
        try:
            total += json.loads(line)["credits"]
        except (ValueError, KeyError, TypeError):
            continue
    return total


def _alive(pid):
    try:
        os.kill(int(pid), 0)
    except PermissionError:
        return True
    except (ProcessLookupError, ValueError, TypeError, OverflowError):
        return False
    return True


def _status_file(screen_dir):
    campaign = Path(screen_dir).parent
    return campaign.parent.parent / MASTER_STATUS if campaign.parent.name == "campaigns" else None


def master_status(screen_dir):
    """The online master's state for the page, when world-state/online-play-status.json says it plays this campaign."""
    path = _status_file(screen_dir)
    status = _read_json(path) if path else None
    if not isinstance(status, dict) or status.get("campaign") != Path(screen_dir).parent.name:
        return None
    state = status.get("state") if not status.get("pid") or _alive(status["pid"]) else "offline"
    return {"state": state, "last_error": status.get("last_error")}


def pending_actions(screen_dir):
    """Actions not given to the master yet: newer than the delivery cursor, or than the shown turn when there is none."""
    screen_dir = Path(screen_dir)
    handled = cli.read_cursor(screen_dir) if (screen_dir / cli.WAIT_CURSOR).is_file() else (_read_json(screen_dir / "turn.json") or {}).get("answered", 0)
    return len(inbox.read_events(screen_dir, after_id=handled))


def byte_range(header, size):
    """(start, end) of a single 'bytes=' range, None to send the whole file, False when it cannot be satisfied."""
    found = _RANGE.fullmatch((header or "").strip())
    if not found or not any(found.groups()):
        return None
    first, last = found.groups()
    if not first:                          # the last N bytes
        if int(last) == 0:
            return False
        start, end = max(0, size - int(last)), size - 1
    elif last and int(last) < int(first):
        return None                        # malformed: ignored, the whole file goes
    else:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    return (start, end) if start < size else False


class ScreenServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    clients = 0
    clients_lock = threading.Lock()

    def handle_error(self, request, client_address):
        pass  # a page that went away mid-request is normal; real failures are logged by the handler

    def shutdown(self):
        self.stopping = True
        super().shutdown()


def _signature(screen_dir):
    files = [screen_dir / n for n in ("act.json", "turn.json", activity.ACTIVITY, inbox.INBOX)] + [TEMPLATE]   # a new page build reloads open pages
    files += [screen_dir.parent / "world.json", screen_dir.parent / "campaign-overview.json"] + [f for f in [_status_file(screen_dir)] if f]
    sig = []
    for f in files:
        try:
            st = f.stat()
            sig.append((st.st_mtime_ns, st.st_size))
        except FileNotFoundError:
            sig.append(None)
    return tuple(sig)


def build_state(screen_dir, views_provider, clock_provider=lambda: None, speech_on=False, auto_speech=True):
    events = inbox.read_events(screen_dir)
    state = {"build": TEMPLATE.stat().st_mtime_ns, "act": _read_json(screen_dir / "act.json"), "turn": _read_json(screen_dir / "turn.json"),
             "views": views_provider(), "clock": clock_provider(), "speech": speech_on, "auto_speech": auto_speech, "activity": activity.read_activity(screen_dir, tail=40),
             "inbox_last": events[-1]["id"] if events else 0}
    master = master_status(screen_dir)
    if master:
        state["master"] = master
    return state


def make_server(screen_dir, port=0, token=None, views_provider=None, transcriber=None, host="127.0.0.1", clock_provider=None, speaker=None, director=None):
    screen_dir = Path(screen_dir)
    token = token or secrets.token_urlsafe(24)
    views_provider = views_provider or (lambda: {})
    clock_provider = clock_provider or (lambda: None)

    daily_credits, turn_credits = _env_number("DM_SCREEN_DAILY_CREDITS"), _env_number("DM_SCREEN_TURN_CREDITS")
    sound_generation = os.environ.get("DM_SCREEN_SOUND_GENERATION", "1").strip() != "0"
    max_pending = int(_env_number("DM_SCREEN_MAX_PENDING"))
    voice_cap = _env_number("DM_SCREEN_DAILY_VOICE_MB") * 1024 * 1024
    render_lock, quota_lock, quota_cache = threading.Lock(), threading.Lock(), {"at": None, "value": None}
    action_lock = threading.Lock()
    # Under a credit budget speech plays only on a press of the speaker button: the page hides its Auto switch.
    auto_speech = not (daily_credits or turn_credits)

    def note(kind, **data):
        eventlog.log(screen_dir, kind, **data)

    def speech_on():
        return speaker is not None and getattr(speaker, "available", lambda: True)()

    def quota(fresh=False):
        """The account quota, asked at most once a minute unless something was just spent."""
        with quota_lock:
            if fresh or quota_cache["at"] is None or time.monotonic() - quota_cache["at"] >= QUOTA_SECONDS:
                try:
                    value = speaker.quota()
                except Exception:
                    value = None
                quota_cache.update(at=time.monotonic(), value=value)
            return quota_cache["value"]

    def estimate(turn):
        need = speaker.plan(turn)["credits"]
        if director is not None and sound_generation:
            need += director.plan(turn)["credits"]
        return need

    def over_budget(need):
        """The refusal (a JSON body for 402) when a render would break the per-turn or the daily credit limit."""
        if not need:
            return None
        if turn_credits and need > turn_credits:
            return {"error": f"this turn would cost about {need} credits, more than the {turn_credits:g} allowed per turn",
                    "limit": "turn_credits", "need": need, "cap": turn_credits}
        today = spent_today(screen_dir, "credits")
        if daily_credits and today + need > daily_credits:
            return {"error": f"today's speech budget is spent: {today:g} of {daily_credits:g} credits used, this turn needs about {need}",
                    "limit": "daily_credits", "need": need, "spent": today, "cap": daily_credits}
        return None

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _host_ok(self):
            return self.headers.get("Host", "") in {f"127.0.0.1:{self.server.server_port}",
                                                    f"localhost:{self.server.server_port}"}

        def _authorized(self):
            supplied = self.headers.get("X-Screen-Token") or parse_qs(urlparse(self.path).query).get("token", [""])[0]
            return self._host_ok() and secrets.compare_digest(supplied, token)

        def _send(self, status, body, content_type="application/json; charset=utf-8", headers=None):
            path = urlparse(self.path).path
            if (path not in QUIET_PATHS and not path.startswith("/audio/")) or status >= 400:
                note("http", method=self.command, path=path, status=status, ms=round((time.monotonic() - getattr(self, "_t0", time.monotonic())) * 1000),
                     bytes=len(body) if isinstance(body, bytes) else len(json.dumps(body)), error=body.get("error") if isinstance(body, dict) else None)
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page went away (reload) while we answered

        def _deny(self):
            self._send(403, {"error": "forbidden"})

        def do_GET(self):
            self._t0 = time.monotonic()
            try:
                self._get()
            except Exception as exc:
                self._crash(exc)

        def _crash(self, exc):
            note("error", where=f"{self.command} {urlparse(self.path).path}", message=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
            try:
                self._send(500, {"error": "internal error, see the log"})
            except Exception:
                pass

        def _get(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._page() if self._host_ok() else self._deny()
            if path.startswith("/audio/"):
                return self._audio(path[len("/audio/"):])
            if path.startswith("/library/"):
                return self._library(path[len("/library/"):])
            if path == "/art.png":
                art = screen_dir / "art.png"
                if not self._host_ok() or not art.is_file():
                    return self._deny() if not self._host_ok() else self._send(404, {"error": "no art"})
                return self._send(200, art.read_bytes(), "image/png")
            if not self._authorized():
                return self._deny()
            if path == "/api/state":
                return self._send(200, build_state(screen_dir, views_provider, clock_provider, speech_on(), auto_speech))
            if path == "/api/speech/plan":
                return self._plan()
            if path == "/api/audio":
                return self._sounds()
            if path == "/api/clients":
                return self._send(200, {"clients": self.server.clients})
            if path == "/api/events":
                return self._stream()
            self._send(404, {"error": "not found"})

        def _page(self):
            act = _read_json(screen_dir / "act.json") or {}
            html = (TEMPLATE.read_text(encoding="utf-8")
                    .replace("{{THEME_CSS}}", act.get("theme_css", ""))
                    .replace("{{TOKEN}}", token)
                    .replace("{{TITLE}}", _escape(act.get("title", "Игровой экран"))))
            self._send(200, html.encode(), "text/html; charset=utf-8")

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")     # nginx must pass every event at once
            self.end_headers()
            last, idle = None, 0.0
            with self.server.clients_lock:
                self.server.clients += 1
            try:
                while not getattr(self.server, "stopping", False) and not self._client_gone():
                    sig = _signature(screen_dir)
                    if sig != last:
                        last, idle = sig, 0.0
                        payload = json.dumps(build_state(screen_dir, views_provider, clock_provider, speech_on(), auto_speech), ensure_ascii=False)
                        self.wfile.write(f"event: state\ndata: {payload}\n\n".encode())
                    elif idle >= PING_SECONDS:
                        idle = 0.0
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    time.sleep(POLL_SECONDS)
                    idle += POLL_SECONDS
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
            finally:
                with self.server.clients_lock:
                    self.server.clients -= 1

        def _client_gone(self):
            readable, _, _ = select.select([self.connection], [], [], 0)
            if not readable:
                return False
            try:
                return self.connection.recv(1, socket.MSG_PEEK) == b""
            except OSError:
                return True

        def do_POST(self):
            self._t0 = time.monotonic()
            try:
                self._post()
            except Exception as exc:
                self._crash(exc)

        def _post(self):
            if not self._authorized():
                return self._deny()
            path = urlparse(self.path).path
            raw = (self.headers.get("Content-Length") or "").strip()
            if not _LENGTH.fullmatch(raw):         # never read a body of unknown size: a negative one would block the thread
                return self._send(400, {"error": "a Content-Length header with the body size is required"}, headers={"Connection": "close"})
            length = int(raw)
            if length > (MAX_LOG_BODY if path == "/api/log" else MAX_AUDIO):
                return self._send(413, {"error": "too large"}, headers={"Connection": "close"})
            body = self.rfile.read(length)
            if path == "/api/action":
                return self._action(body)
            if path == "/api/voice":
                return self._voice(body)
            if path == "/api/speech/render":
                return self._render()
            if path == "/api/log":
                return self._ui_log(body)
            self._send(404, {"error": "not found"})

        def _audio(self, name):
            if not self._authorized():
                return self._deny()
            path = screen_dir / speech_module.AUDIO_DIR / name
            if not _AUDIO_NAME.fullmatch(name) or not path.is_file():
                return self._send(404, {"error": "no such audio"})
            self._file(path, "audio/mpeg")

        def _library(self, name):
            if not self._authorized():
                return self._deny()
            if director is None or not audio_module.FILE_NAME.fullmatch(name):
                return self._send(404, {"error": "no such sound"})
            path = director.library.dir / "files" / name
            if not path.is_file():
                return self._send(404, {"error": "no such sound"})
            self._file(path, audio_module.CONTENT_TYPES[name.rsplit(".", 1)[1]])

        def _file(self, path, content_type):
            """A file with single byte-range support: Safari and iOS play media only from 206 answers."""
            size = path.stat().st_size
            span = byte_range(self.headers.get("Range"), size)
            if span is False:
                return self._send(416, {"error": "range not satisfiable"}, headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})
            start, end = span or (0, size - 1)
            with open(path, "rb") as f:
                f.seek(start)
                data = f.read(end - start + 1)
            if span:
                return self._send(206, data, content_type, {"Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes"})
            self._send(200, data, content_type, {"Accept-Ranges": "bytes"})

        def _sounds(self):
            """The turn's sounds that cost nothing: the library and free sources, never a generation."""
            turn = self._turn()
            if director is None or not turn:
                return self._send(200, {"audio": None})
            return self._send(200, {"turn": turn["id"], "audio": director.resolve(turn, generate=False)})

        def _turn(self):
            return _read_json(screen_dir / "turn.json")

        def _speech_error(self, exc):
            if isinstance(exc, speech_module.SpeechUnavailable):
                return self._send(503, {"error": str(exc)})
            if isinstance(exc, speech_module.SpeechError):
                return self._send(exc.status if 400 <= exc.status < 600 else 502, {"error": str(exc)})
            raise exc

        def _plan(self):
            turn = self._turn()
            if speaker is None or not turn:
                return self._send(503, {"error": "speech is not available"})
            try:
                plan = speaker.plan(turn)
                if director is not None:
                    sounds = director.plan(turn)
                    sound_credits = sounds["credits"] if sound_generation else 0
                    plan = {**plan, "speech_credits": plan["credits"], "sound_credits": sound_credits, "credits": plan["credits"] + sound_credits,
                            "sounds": sounds["cues"], "sounds_found": sounds["found"]}
            except (speech_module.SpeechUnavailable, speech_module.SpeechError) as exc:
                return self._speech_error(exc)
            body = {"plan": plan, "quota": quota()}
            if daily_credits or turn_credits:
                body["budget"] = {"daily": daily_credits or None, "turn": turn_credits or None, "spent_today": spent_today(screen_dir, "credits")}
            return self._send(200, body)

        def _render(self):
            turn = self._turn()
            if speaker is None or not turn:
                return self._send(503, {"error": "speech is not available"})
            ledger = Path(getattr(speaker, "dir", screen_dir)) / speech_module.AUDIO_DIR / speech_module.LEDGER
            with render_lock:       # one render at a time: a second press on the same turn waits, then plays from the cache
                try:
                    refusal = over_budget(estimate(turn)) if daily_credits or turn_credits else None
                    if refusal:
                        return self._send(402, refusal)
                    offset = _ledger_size(ledger)
                    try:
                        segments = speaker.render(turn)
                        sounds = director.resolve(turn, generate=sound_generation) if director is not None else None
                    finally:
                        spent = _ledger_since(ledger, offset)
                        if spent:
                            add_spend(screen_dir, "credits", spent)
                except (speech_module.SpeechUnavailable, speech_module.SpeechError) as exc:
                    return self._speech_error(exc)
            for seg in segments:
                seg["url"] = "/audio/" + seg["file"]
            self._send(200, {"turn": turn["id"], "segments": segments, "audio": sounds, "quota": quota(fresh=bool(spent))})

        def _ui_log(self, body):
            try:
                events = json.loads(body or b"{}").get("events", [])
            except (json.JSONDecodeError, AttributeError):
                return self._send(400, {"error": "bad json"})
            kept = 0
            for event in events[:MAX_UI_EVENTS]:
                kind = str(event.get("kind", ""))
                if not kind.startswith("ui."):
                    continue
                data = {k: (v[:MAX_UI_BYTES] if isinstance(v, str) else v) for k, v in event.items() if k != "kind"}
                if len(json.dumps(data, ensure_ascii=False)) > MAX_UI_BYTES:
                    data = {"truncated": json.dumps(data, ensure_ascii=False)[:MAX_UI_BYTES]}
                note(kind, **data)
                kept += 1
            self._send(200, {"ok": True, "kept": kept})

        def _action(self, body):
            try:
                data = json.loads(body or b"{}")
                with action_lock:       # the pending check and the append are one step for parallel posts
                    if max_pending and pending_actions(screen_dir) >= max_pending:
                        return self._send(429, {"error": f"{max_pending} actions are already waiting for the master", "limit": "pending"})
                    event = inbox.append_event(screen_dir, data.get("who", ""), data.get("source", "text"), data.get("text", ""))
            except (ValueError, json.JSONDecodeError, AttributeError) as exc:
                return self._send(400, {"error": str(exc)})
            note("action", id=event["id"], who=event["who"], source=event["source"], text=event["text"])
            self._send(200, {"ok": True, "id": event["id"]})

        def _voice(self, body):
            if not body:
                return self._send(400, {"error": "empty recording"})
            if not add_spend(screen_dir, "voice_bytes", len(body), cap=voice_cap):   # reserved before the upload goes out
                return self._send(429, {"error": "today's microphone limit is reached: type the action instead", "limit": "voice_mb"})
            started = time.monotonic()
            try:
                result = transcriber(body, self.headers.get("Content-Type", "audio/webm"))
            except voice.VoiceUnavailable as exc:
                note("stt", ok=False, bytes=len(body), error=str(exc))
                return self._send(503, {"error": str(exc)})
            except ValueError as exc:
                note("stt", ok=False, bytes=len(body), error=str(exc))
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # network or provider failure: tell the page, keep the server alive
                note("stt", ok=False, bytes=len(body), error=f"{type(exc).__name__}: {exc}")
                return self._send(502, {"error": f"speech service failed: {exc}"})
            details = result if isinstance(result, dict) else {"text": result}
            note("stt", ok=True, bytes=len(body), content_type=self.headers.get("Content-Type"), ms=round((time.monotonic() - started) * 1000), **details)
            self._send(200, {"text": details["text"]})

    httpd = ScreenServer((host, port), Handler)
    httpd.stopping = False
    return httpd, token


def serve_in_thread(httpd):
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def _escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
