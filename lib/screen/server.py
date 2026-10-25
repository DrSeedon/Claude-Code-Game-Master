"""Local web server for the play screen: page, live event stream, player actions, microphone."""

import json
import re
import secrets
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import activity, inbox, speech as speech_module, voice

TEMPLATE = Path(__file__).with_name("template.html")
MAX_AUDIO = 8 * 1024 * 1024
_AUDIO_NAME = re.compile(r"^[0-9a-f]{64}\.mp3$|^ambient-[\w-]{1,60}\.mp3$")
POLL_SECONDS = 0.3
PING_SECONDS = 15


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


class ScreenServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    clients = 0
    clients_lock = threading.Lock()

    def shutdown(self):
        self.stopping = True
        super().shutdown()


def _signature(screen_dir):
    files = [screen_dir / n for n in ("act.json", "turn.json", activity.ACTIVITY, inbox.INBOX)]
    files += [screen_dir.parent / "world.json", screen_dir.parent / "campaign-overview.json"]
    sig = []
    for f in files:
        try:
            st = f.stat()
            sig.append((st.st_mtime_ns, st.st_size))
        except FileNotFoundError:
            sig.append(None)
    return tuple(sig)


def build_state(screen_dir, views_provider, clock_provider=lambda: None, speech_on=False):
    events = inbox.read_events(screen_dir)
    return {"build": TEMPLATE.stat().st_mtime_ns, "act": _read_json(screen_dir / "act.json"), "turn": _read_json(screen_dir / "turn.json"),
            "views": views_provider(), "clock": clock_provider(), "speech": speech_on, "activity": activity.read_activity(screen_dir, tail=40),
            "inbox_last": events[-1]["id"] if events else 0}


def make_server(screen_dir, port=0, token=None, views_provider=None, transcriber=None, host="127.0.0.1", clock_provider=None, speaker=None):
    screen_dir = Path(screen_dir)
    token = token or secrets.token_urlsafe(24)
    views_provider = views_provider or (lambda: {})
    clock_provider = clock_provider or (lambda: None)

    def speech_on():
        return speaker is not None and getattr(speaker, "available", lambda: True)()

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

        def _send(self, status, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page went away (reload) while we answered

        def _deny(self):
            self._send(403, {"error": "forbidden"})

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._page() if self._host_ok() else self._deny()
            if path.startswith("/audio/"):
                return self._audio(path[len("/audio/"):])
            if path == "/art.png":
                art = screen_dir / "art.png"
                if not self._host_ok() or not art.is_file():
                    return self._deny() if not self._host_ok() else self._send(404, {"error": "no art"})
                return self._send(200, art.read_bytes(), "image/png")
            if not self._authorized():
                return self._deny()
            if path == "/api/state":
                return self._send(200, build_state(screen_dir, views_provider, clock_provider, speech_on()))
            if path == "/api/speech/plan":
                return self._plan()
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
            self.end_headers()
            last, idle = None, 0.0
            with self.server.clients_lock:
                self.server.clients += 1
            try:
                while not getattr(self.server, "stopping", False) and not self._client_gone():
                    sig = _signature(screen_dir)
                    if sig != last:
                        last, idle = sig, 0.0
                        payload = json.dumps(build_state(screen_dir, views_provider, clock_provider, speech_on()), ensure_ascii=False)
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
            if not self._authorized():
                return self._deny()
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_AUDIO:
                return self._send(413, {"error": "too large"})
            body = self.rfile.read(length)
            if path == "/api/action":
                return self._action(body)
            if path == "/api/voice":
                return self._voice(body)
            if path == "/api/speech/render":
                return self._render()
            self._send(404, {"error": "not found"})

        def _audio(self, name):
            if not self._authorized():
                return self._deny()
            path = screen_dir / speech_module.AUDIO_DIR / name
            if not _AUDIO_NAME.fullmatch(name) or not path.is_file():
                return self._send(404, {"error": "no such audio"})
            self._send(200, path.read_bytes(), "audio/mpeg")

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
                quota = speaker.quota()
            except Exception:
                quota = None
            try:
                return self._send(200, {"plan": speaker.plan(turn), "quota": quota})
            except (speech_module.SpeechUnavailable, speech_module.SpeechError) as exc:
                return self._speech_error(exc)

        def _render(self):
            turn = self._turn()
            if speaker is None or not turn:
                return self._send(503, {"error": "speech is not available"})
            try:
                segments = speaker.render(turn)
                try:
                    quota = speaker.quota()
                except Exception:
                    quota = None
            except (speech_module.SpeechUnavailable, speech_module.SpeechError) as exc:
                return self._speech_error(exc)
            for seg in segments:
                seg["url"] = "/audio/" + seg["file"]
            self._send(200, {"turn": turn["id"], "segments": segments, "quota": quota})

        def _action(self, body):
            try:
                data = json.loads(body or b"{}")
                event = inbox.append_event(screen_dir, data.get("who", ""), data.get("source", "text"), data.get("text", ""))
            except (ValueError, json.JSONDecodeError) as exc:
                return self._send(400, {"error": str(exc)})
            self._send(200, {"ok": True, "id": event["id"]})

        def _voice(self, body):
            if not body:
                return self._send(400, {"error": "empty recording"})
            try:
                text = transcriber(body, self.headers.get("Content-Type", "audio/webm"))
            except voice.VoiceUnavailable as exc:
                return self._send(503, {"error": str(exc)})
            except ValueError as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # network or provider failure: tell the page, keep the server alive
                return self._send(502, {"error": f"speech service failed: {exc}"})
            self._send(200, {"text": text})

    httpd = ScreenServer((host, port), Handler)
    httpd.stopping = False
    return httpd, token


def serve_in_thread(httpd):
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def _escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
