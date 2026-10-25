#!/usr/bin/env python3
"""dm-screen: build the act page, push turns, run the local server and follow player actions."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PORT = 18115
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def active_campaign_dir():
    """Cheap lookup (no heavy imports): the hook runs after every Bash call."""
    if os.environ.get("DM_SCREEN_DIR"):
        return Path(os.environ["DM_SCREEN_DIR"]).parent
    name = os.environ.get("DM_ACTIVE_CAMPAIGN") or (PROJECT_ROOT / "world-state" / "active-campaign.txt").read_text().strip()
    return PROJECT_ROOT / "world-state" / "campaigns" / name


def screen_dir():
    return Path(os.environ["DM_SCREEN_DIR"]) if os.environ.get("DM_SCREEN_DIR") else active_campaign_dir() / "screen"


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def server_info(sdir):
    info = _read(sdir / "server.json")
    if not info:
        return None
    try:
        os.kill(info["pid"], 0)
    except (ProcessLookupError, PermissionError):
        return None
    return info


def set_act(sdir, image, title, kicker="", place="", date="", style="classic", captions=None, labels=None, lang="en"):
    from . import content, theme

    cards = content.validate_captions(captions or [])
    sdir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, sdir / "art.png")
    built = theme.build_theme(theme.extract_palette(sdir / "art.png"), style)
    previous = _read(sdir / "act.json") or {}
    act = {"id": previous.get("id", 0) + 1, "title": title, "kicker": kicker, "place": place, "date": date,
           "style": style, "lang": lang, "captions": cards, "labels": labels or {}, "theme": built, "theme_css": theme.theme_css(built)}
    _write(sdir / "act.json", act)
    return act


def set_turn(sdir, data):
    from . import content, inbox

    checked = content.validate_turn(data)
    previous = _read(sdir / "turn.json") or {}
    events = inbox.read_events(sdir)
    turn = {"id": previous.get("id", 0) + 1, "answered": events[-1]["id"] if events else 0, **checked}
    _write(sdir / "turn.json", turn)
    return turn


def set_panels(sdir, panels):
    """Replace the side panels of the current turn in place (no new turn, no story animation)."""
    from . import content

    turn = _read(sdir / "turn.json")
    if not turn:
        raise ValueError("no turn is shown yet")
    turn["panels"] = content.validate_panels(panels)
    _write(sdir / "turn.json", turn)
    return turn


def run_hook(payload_text):
    """PostToolUse: never fail, never print, do nothing unless the screen server is running."""
    try:
        from . import activity, hook

        sdir = screen_dir()
        if not server_info(sdir):
            return
        lang = (_read(sdir / "act.json") or {}).get("lang", "en")
        for event in hook.activities_from_hook(json.loads(payload_text), lang):
            activity.append_activity(sdir, event["kind"], event["text"])
    except Exception:
        return


def serve(sdir, port):
    from backend.campaign_views import get_campaign_views

    from . import clock, server, voice

    campaign = sdir.parent
    httpd, token = server.make_server(sdir, port=port, views_provider=lambda: get_campaign_views(campaign),
                                      clock_provider=lambda: clock.world_clock(campaign),
                                      transcriber=voice.make_transcriber(PROJECT_ROOT))
    _write(sdir / "server.json", {"pid": os.getpid(), "port": httpd.server_port, "token": token})
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        (sdir / "server.json").unlink(missing_ok=True)


def connected_pages(info):
    """How many open pages are listening to the server (0 if it cannot be asked)."""
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/clients", headers={"X-Screen-Token": info["token"]})
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read())["clients"]
    except Exception:
        return 0


def close_windows(sdir):
    """Close every app window of this campaign's screen profile (the profile belongs to the screen only)."""
    subprocess.run(["pkill", "-f", f"--user-data-dir={sdir / 'chrome-profile'}"], capture_output=True)


def start(sdir, port, open_window, new_window=False, replace=False):
    """Idempotent: reuse the server, and open a window only if no page is connected yet."""
    info = server_info(sdir)
    if not info:
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "server.json").unlink(missing_ok=True)
        log = open(sdir / "server.log", "ab")
        subprocess.Popen([sys.executable, "-m", "lib.screen.cli", "serve", "--port", str(port)], cwd=PROJECT_ROOT,
                         stdout=log, stderr=log, start_new_session=True, env={**os.environ, "DM_SCREEN_DIR": str(sdir)})
        for _ in range(50):
            time.sleep(0.1)
            info = server_info(sdir)
            if info:
                break
        else:
            raise SystemExit(f"server did not start, see {sdir / 'server.log'}")
    url = f"http://127.0.0.1:{info['port']}/"
    if replace:
        close_windows(sdir)
        time.sleep(0.5)
    if open_window and (replace or new_window or connected_pages(info) == 0):
        browser = next((shutil.which(b) for b in os.environ.get("DM_SCREEN_BROWSER", "").split() + list(BROWSERS) if shutil.which(b)), None)
        if browser:
            subprocess.Popen([browser, f"--app={url}", f"--user-data-dir={sdir / 'chrome-profile'}",
                              "--use-fake-ui-for-media-stream", "--start-maximized", "--no-first-run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            print("no Chromium-based browser found; open the URL manually", file=sys.stderr)
    return url


def ensure_window(sdir):
    """Used by act/turn: make sure the page exists, never open a second one."""
    if os.environ.get("DM_SCREEN_AUTOSTART") == "0":
        return
    start(sdir, DEFAULT_PORT, True)


def stop(sdir):
    info = server_info(sdir)
    if not info:
        return False
    os.kill(info["pid"], signal.SIGTERM)
    return True


def listen(sdir, from_start):
    from . import inbox

    events = inbox.read_events(sdir)
    last = 0 if from_start else (events[-1]["id"] if events else 0)
    while True:
        for event in inbox.read_events(sdir, after_id=last):
            print(inbox.format_line(event), flush=True)
            last = event["id"]
        time.sleep(0.3)


def doctor():
    """Requirements of the screen as (name, ok, hint); the microphone ones are optional."""
    from . import voice

    try:
        import PIL  # noqa: F401
        pillow = True
    except ImportError:
        pillow = False
    settings = (PROJECT_ROOT / ".claude" / "settings.json")
    hooked = settings.is_file() and "lib.screen.cli hook" in settings.read_text(encoding="utf-8")
    return [
        ("Pillow (theme from the art)", pillow, "uv pip install pillow"),
        ("Chromium-based browser (app window)", any(shutil.which(b) for b in BROWSERS), "install google-chrome or chromium, or open the printed URL in any browser"),
        ("ffmpeg (microphone audio clean-up)", bool(shutil.which("ffmpeg")), "sudo apt install ffmpeg"),
        ("DEEPGRAM_API_KEY in .env (microphone)", bool(voice.load_api_key(PROJECT_ROOT)), "add DEEPGRAM_API_KEY=... to the project .env"),
        ("PostToolUse hook (live feed of the Master's work)", hooked, "register `python3 -m lib.screen.cli hook` for Bash in .claude/settings.json"),
    ]


def enable():
    """Switch the active campaign to the screen: apply the custom rule and prepare the folder."""
    rule = subprocess.run(["bash", str(PROJECT_ROOT / ".claude/additional/infrastructure/dm-campaign-custom-rules.sh"),
                           "apply", "html-screen"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    (screen_dir()).mkdir(parents=True, exist_ok=True)
    return (rule.stdout + rule.stderr).strip().splitlines()[-1] if (rule.stdout + rule.stderr).strip() else "rule applied"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dm-screen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("act", help="start a new act: key art, captions, theme from the art")
    a.add_argument("--image", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--kicker", default="")
    a.add_argument("--place", default="")
    a.add_argument("--date", default="")
    a.add_argument("--style", default="classic", choices=["classic", "severe", "soft"])
    a.add_argument("--lang", default="en", choices=["en", "ru"], help="interface language of the page")
    a.add_argument("--captions", help="JSON file: {\"cards\": [...]}")
    a.add_argument("--labels", help="JSON file: skill key to display name")
    t = sub.add_parser("turn", help="show a new turn (story blocks, question, options, panels)")
    t.add_argument("--file", required=True, help="JSON file or - for stdin")
    pn = sub.add_parser("panels", help="replace the side panels of the current turn without a new turn")
    pn.add_argument("--file", required=True, help="JSON list of panels, or - for stdin")
    n = sub.add_parser("activity", help="add a line to the Master's visible work feed")
    n.add_argument("kind", choices=["think", "roll", "save", "world", "info"])
    n.add_argument("text")
    s = sub.add_parser("start", help="run the local server and open the window")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--no-open", action="store_true")
    s.add_argument("--new-window", action="store_true", help="open another window even if a page is connected")
    s.add_argument("--replace", action="store_true", help="close the old window first and open a fresh one")
    r = sub.add_parser("restart", help="restart the server; open pages reconnect by themselves")
    r.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("stop")
    sub.add_parser("status")
    l = sub.add_parser("listen", help="print player actions as they arrive (use with the Monitor tool)")
    l.add_argument("--from-start", action="store_true")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("hook")
    sub.add_parser("doctor", help="check what the screen needs")
    sub.add_parser("enable", help="turn the screen mode on for the active campaign")
    args = ap.parse_args(argv)

    if args.cmd == "hook":
        return run_hook(sys.stdin.read())
    if args.cmd == "doctor":
        results = doctor()
        for name, ok, hint in results:
            print(f"[{'ok' if ok else 'MISSING'}] {name}" + ("" if ok else f"  -> {hint}"))
        return 0 if all(ok for name, ok, _ in results if "microphone" not in name and "hook" not in name) else 1
    sdir = screen_dir()
    if args.cmd == "act":
        cards = json.loads(Path(args.captions).read_text(encoding="utf-8"))["cards"] if args.captions else []
        labels = json.loads(Path(args.labels).read_text(encoding="utf-8")) if args.labels else {}
        act = set_act(sdir, args.image, args.title, args.kicker, args.place, args.date, args.style, cards, labels, args.lang)
        print(f"act {act['id']} ready: accent {act['theme']['accent']}, style {act['style']}")
        ensure_window(sdir)
    elif args.cmd == "turn":
        data = json.loads(sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8"))
        print(f"turn {set_turn(sdir, data)['id']} shown")
        ensure_window(sdir)
    elif args.cmd == "panels":
        data = json.loads(sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8"))
        print(f"{len(set_panels(sdir, data)['panels'])} panels updated")
    elif args.cmd == "activity":
        from . import activity
        print(f"activity {activity.append_activity(sdir, args.kind, args.text)['id']}")
    elif args.cmd == "start":
        print(start(sdir, args.port, not args.no_open, args.new_window, args.replace))
    elif args.cmd == "restart":
        had_pages = connected_pages(server_info(sdir)) if server_info(sdir) else 0
        stop(sdir)
        for _ in range(30):
            if not server_info(sdir):
                break
            time.sleep(0.1)
        info = None
        url = start(sdir, args.port, False)
        info = server_info(sdir)
        for _ in range(60):  # open pages reconnect by themselves; a stale one never will
            if connected_pages(info) or not had_pages:
                break
            time.sleep(0.2)
        else:
            url = start(sdir, args.port, True, replace=True)
        print(url)
    elif args.cmd == "stop":
        print("stopped" if stop(sdir) else "not running")
    elif args.cmd == "status":
        info = server_info(sdir)
        print(f"running on http://127.0.0.1:{info['port']}/" if info else "not running")
    elif args.cmd == "listen":
        listen(sdir, args.from_start)
    elif args.cmd == "serve":
        serve(sdir, args.port)
    elif args.cmd == "enable":
        print(enable())
        print("Next: dm-screen.sh act ... (art + captions), dm-screen.sh turn --file ..., dm-screen.sh start")


if __name__ == "__main__":
    sys.exit(main() or 0)
