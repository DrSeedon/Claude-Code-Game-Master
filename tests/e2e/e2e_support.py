"""Helpers of the play-screen browser tests: a stub master, a temp table, tiny art and sound files."""

import threading
import time
import wave
from pathlib import Path

from lib.screen import inbox, server

TOKEN = "e2e-token"
PASSWORD = "e2e-table-password"
BROWSER_ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"]


def make_art(path, colors):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (640, 360), colors[0])
    ImageDraw.Draw(image).rectangle((0, 180, 640, 360), fill=colors[1])
    image.save(path)
    return path


def silent_wav(path, seconds=0.3):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\x00\x00" * int(8000 * seconds))
    return path.read_bytes()


class NoFreesound:
    """A stand-in for the Freesound client: the library is all the test may use."""

    def search(self, query, kind):
        return None


class Master(threading.Thread):
    """A stub master: for every `step` waits for the next player action, then (after release()) runs the step with it."""

    def __init__(self, sdir, steps):
        super().__init__(daemon=True)
        self.sdir, self.steps = sdir, steps
        self.go, self.stop, self.errors, self.seen = threading.Semaphore(0), threading.Event(), [], []

    def release(self):
        self.go.release()

    def run(self):
        cursor = 0
        try:
            for step in self.steps:
                while not self.stop.is_set() and not inbox.read_events(self.sdir, after_id=cursor):
                    time.sleep(0.05)
                if self.stop.is_set():
                    return
                event = inbox.read_events(self.sdir, after_id=cursor)[0]
                cursor = event["id"]
                self.seen.append(event)
                while not self.stop.is_set() and not self.go.acquire(timeout=0.1):
                    pass
                if self.stop.is_set():   # a test that failed before release() must not get a turn written in teardown
                    return
                step(event)
        except Exception as exc:  # reported by the test, a dead thread must not hide as a timeout
            self.errors.append(repr(exc))


class Table:
    """One temp campaign with its screen directory and a running server."""

    def __init__(self, root):
        self.root = Path(root)
        self.sdir = self.root / "campaigns" / "e2e" / "screen"
        self.sdir.mkdir(parents=True)

    def start(self, views, director=None):
        self.httpd, _ = server.make_server(self.sdir, port=0, token=TOKEN, views_provider=lambda: views, director=director,
                                           transcriber=lambda data, ctype: "stub", speaker=None)
        server.serve_in_thread(self.httpd)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        return self

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
