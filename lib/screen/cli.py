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
    from . import content, eventlog, theme

    cards = content.validate_captions(captions or [])
    sdir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, sdir / "art.png")
    built = theme.build_theme(theme.extract_palette(sdir / "art.png"), style)
    previous = _read(sdir / "act.json") or {}
    act = {"id": previous.get("id", 0) + 1, "title": title, "kicker": kicker, "place": place, "date": date,
           "style": style, "lang": lang, "captions": cards, "labels": labels or {}, "theme": built, "theme_css": theme.theme_css(built)}
    _write(sdir / "act.json", act)
    eventlog.log(sdir, "act", id=act["id"], title=title, kicker=kicker, place=place, date=date, style=style, lang=lang, captions=len(cards),
                 labels=len(labels or {}), theme=built, snapshot=eventlog.world_snapshot(sdir.parent))
    return act


def set_turn(sdir, data):
    from . import content, eventlog, inbox

    checked = content.validate_turn(data)
    previous = _read(sdir / "turn.json") or {}
    events = inbox.read_events(sdir)
    turn = {"id": previous.get("id", 0) + 1, "answered": events[-1]["id"] if events else 0, **checked}
    _write(sdir / "turn.json", turn)
    eventlog.log(sdir, "turn", snapshot=eventlog.world_snapshot(sdir.parent), **turn)
    return turn


def set_panels(sdir, panels):
    """Replace the side panels of the current turn in place (no new turn, no story animation)."""
    from . import content, eventlog

    turn = _read(sdir / "turn.json")
    if not turn:
        raise ValueError("no turn is shown yet")
    turn["panels"] = content.validate_panels(panels)
    _write(sdir / "turn.json", turn)
    eventlog.log(sdir, "panels", turn=turn["id"], panels=turn["panels"], snapshot=eventlog.world_snapshot(sdir.parent))
    return turn


def run_hook(payload_text):
    """PostToolUse: never fail, never print, do nothing unless the screen server is running."""
    try:
        from . import activity, eventlog, hook

        sdir = screen_dir()
        if not server_info(sdir):
            return
        lang = (_read(sdir / "act.json") or {}).get("lang", "en")
        payload = json.loads(payload_text)
        shown = hook.activities_from_hook(payload, lang)
        if shown or "dm-" in json.dumps(payload.get("tool_input") or {}):
            response = payload.get("tool_response")
            output = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
            eventlog.log(sdir, "tool", command=(payload.get("tool_input") or {}).get("command", ""), output=output[:1500], shown=[e["text"] for e in shown])
        for event in shown:
            activity.append_activity(sdir, event["kind"], event["text"])
    except Exception:
        return


def serve(sdir, port):
    from backend.campaign_views import get_campaign_views

    from . import clock, eventlog, server, speech, voice

    campaign = sdir.parent
    httpd, token = server.make_server(sdir, port=port, views_provider=lambda: get_campaign_views(campaign),
                                      clock_provider=lambda: clock.world_clock(campaign),
                                      speaker=speech.Speaker(sdir, speech.ElevenLabsApi(PROJECT_ROOT), lambda: speech.characters_from_world(campaign)),
                                      transcriber=voice.make_transcriber(PROJECT_ROOT))
    _write(sdir / "server.json", {"pid": os.getpid(), "port": httpd.server_port, "token": token})
    eventlog.log(sdir, "server", event="start", pid=os.getpid(), port=httpd.server_port, speech=speech.load_config(sdir).get("model"), key_present=bool(speech.load_api_key(PROJECT_ROOT)))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        (sdir / "server.json").unlink(missing_ok=True)
        eventlog.log(sdir, "server", event="stop", pid=os.getpid())


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
    from . import eventlog
    eventlog.log(sdir, "window", event="close")
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
            from . import eventlog
            eventlog.log(sdir, "window", event="open", browser=browser, replace=replace, url=url)
            subprocess.Popen([browser, f"--app={url}", f"--user-data-dir={sdir / 'chrome-profile'}",
                              "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required", "--start-maximized", "--no-first-run"],
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


def _parse_age(text):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if not text or text[-1] not in units or not text[:-1].isdigit():
        raise SystemExit("--since looks like 30s, 10m, 2h or 1d")
    from datetime import timedelta
    return timedelta(seconds=int(text[:-1]) * units[text[-1]])


def _format_entry(entry):
    skip = {"ts", "kind", "blocks", "words", "theme", "snapshot", "traceback"}
    parts = []
    for key, value in entry.items():
        if key in skip:
            continue
        shown = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        parts.append(f"{key}={shown[:90]}")
    extra = ""
    if entry.get("words"):
        extra = " | words: " + " ".join(f"{w['word']}({w.get('confidence')})" for w in entry["words"])[:400]
    if entry.get("blocks"):
        extra += f" | {len(entry['blocks'])} blocks"
    return f"{entry['ts'][11:23]} {entry['kind']:<14} " + " ".join(parts)[:260] + extra


def show_log(sdir, tail=40, kinds=None, errors=False, since=None, as_json=False, summary=False, follow=False):
    from . import eventlog

    if summary:
        for key, value in eventlog.summary(sdir).items():
            print(f"{key}: {value}")
        return
    seen = 0
    while True:
        entries = eventlog.read(sdir, kinds=kinds, since=since, errors=errors)
        fresh = entries[seen:] if follow and seen else entries[-tail:] if tail else entries
        for entry in fresh:
            print(json.dumps(entry, ensure_ascii=False) if as_json else _format_entry(entry), flush=True)
        seen = len(entries)
        if not follow:
            return
        time.sleep(0.5)


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


def voice_command(sdir, args):
    from . import speech, voices

    api = speech.ElevenLabsApi(PROJECT_ROOT)
    if args.what == "show":
        config = speech.load_config(sdir)
        print("model:", config["model"], "| language:", config["language"])
        print("narrator:", config.get("narrator") or "(not set)")
        print("default:", config.get("default") or "(not set)")
        for name, profile in sorted(speech.characters_from_world(sdir.parent).items()):
            print(f"{name}: {profile}")
        return
    if args.what == "model":
        voices.set_model(sdir, args.name)
        print("model set to", args.name)
        return
    if args.what == "design":
        if not args.name or not args.describe:
            raise SystemExit('voice design "Name" --describe "..."')
        found = voices.design_voice(api, sdir, args.describe, args.text, args.seed, args.model)
        from . import eventlog
        eventlog.log(sdir, "voice_design", character=args.name, description=args.describe, seed=args.seed, previews=found)
        for item in found:
            print(f"preview {item['id']}  {item['seconds']}s  {sdir / item['file']}")
        print(f'listen, then: dm-screen.sh voice keep "{args.name}" --preview <id> --describe "{args.describe}"')
        return
    if args.what == "keep":
        if not (args.name and args.preview and args.describe):
            raise SystemExit('voice keep "Name" --preview <id> --describe "..."')
        profile = voices.keep_voice(api, args.name, args.describe, args.preview, args.model)
        voices.set_character_voice(sdir.parent, args.name, profile)
        from . import eventlog
        eventlog.log(sdir, "voice_keep", character=args.name, profile=profile)
        print(f"kept: {args.name} -> voice {profile['voice_id']}")
        return
    if not args.voice:
        raise SystemExit("--voice is required")
    effects = {k: v for k, v in (("environment_id", args.env), ("distance", args.distance), ("pan", args.pan),
                                 ("filter_preset_id", args.filter)) if v is not None}
    profile = voices.make_profile(voices.find_voice(api, args.voice), args.model, args.stability, args.similarity, effects, args.speed)
    if args.what == "narrator":
        voices.set_narrator(sdir, profile)
    elif args.what == "default":
        voices.set_default(sdir, profile)
    else:
        if not args.name:
            raise SystemExit('give the character name: voice set "Name" --voice ...')
        voices.set_character_voice(sdir.parent, args.name, profile)
    print(f"{args.what}{' ' + args.name if args.what == 'set' else ''}: {profile['name']}")


def audition(sdir, text, names, speed, model, models=None):
    """Show a turn with one paragraph per voice, then render it so a click plays them in order."""
    from . import speech, voices

    api = speech.ElevenLabsApi(PROJECT_ROOT)
    profiles, blocks = {}, ["<h1>Прослушивание голосов</h1>"]
    if models:
        if len(names) != 1:
            raise SystemExit("--models needs exactly one voice")
        voice = voices.find_voice(api, names[0])
        for number, model_id in enumerate([m.strip() for m in models.split(",")], 1):
            label = f"Модель {number} · {model_id.replace('eleven_', '')}"
            profiles[label] = voices.make_profile(voice, model=model_id, speed=speed if model_id not in speech.NO_SPEED else None)
            blocks.append(f"<p><b>{label}:</b> «{text}»</p>")
    else:
        for number, query in enumerate(names, 1):
            profile = voices.make_profile(voices.find_voice(api, query), model=model, speed=speed)
            label = f"Голос {number} · {profile['name']}"
            profiles[label] = profile
            blocks.append(f"<p><b>{label}:</b> «{text}»</p>")
    voices.set_audition(sdir, profiles)
    set_turn(sdir, {"blocks": blocks, "question": "Какой голос взять диктором?", "options": [f"Вариант {i}" for i in range(1, len(profiles) + 1)][:6]})
    spk = speech.Speaker(sdir, api, lambda: speech.characters_from_world(sdir.parent))
    plan = spk.plan({"blocks": blocks})
    print(f"rendering {plan['segments']} lines, about {plan['credits']} credits")
    spk.render({"blocks": blocks})
    print("done: press the speaker button on the page")


def speak_once(sdir, text, speaker_name):
    from . import speech

    spk = speech.Speaker(sdir, speech.ElevenLabsApi(PROJECT_ROOT), lambda: speech.characters_from_world(sdir.parent))
    before = spk.quota()
    block = f"<p>{text}</p>" if speaker_name == "narrator" else f"<p><b>{speaker_name}:</b> «{text}»</p>"
    result = spk.render({"id": 0, "blocks": [block]})
    after = spk.quota()
    print(f"audio: {sdir / speech.AUDIO_DIR / result[0]['file']}\ncredits used: {after['used'] - before['used']} (left {after['left']})")


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
    lg = sub.add_parser("log", help="read the screen log: requests, microphone words, prices, turns, errors")
    lg.add_argument("--tail", type=int, default=40)
    lg.add_argument("--kind", help="comma-separated kinds, e.g. tts,stt,turn,error,ui.click")
    lg.add_argument("--errors", action="store_true")
    lg.add_argument("--since", help="30s, 10m, 2h, 1d")
    lg.add_argument("--json", action="store_true", dest="as_json")
    lg.add_argument("--summary", action="store_true")
    lg.add_argument("--follow", action="store_true")
    sub.add_parser("voices", help="list the voices of your ElevenLabs account (Russian first)")
    vp = sub.add_parser("voice", help="narrator, default and per-character voices")
    vp.add_argument("what", choices=["narrator", "default", "model", "set", "show", "design", "keep"])
    vp.add_argument("name", nargs="?", help="character name for 'set', model id for 'model'")
    vp.add_argument("--voice", help="voice name (or part of it) or id")
    vp.add_argument("--model")
    vp.add_argument("--stability", type=float)
    vp.add_argument("--similarity", type=float)
    vp.add_argument("--speed", type=float, help="0.7 to 1.2 (not for Eleven v4)")
    vp.add_argument("--describe", help="design/keep: what the voice is like (age, timbre, manner)")
    vp.add_argument("--text", help="design: sample text of 100 to 1000 characters (default: written by the service)")
    vp.add_argument("--seed", type=int, help="design: the same seed and description give the same voice")
    vp.add_argument("--preview", help="keep: the preview id printed by design")
    vp.add_argument("--env", help="room: small_room big_room hall tunnel street valley forest")
    vp.add_argument("--distance", type=float)
    vp.add_argument("--pan", type=float)
    vp.add_argument("--filter", help="old_radio robot cheap_microphone phone low_quality_phone bright_phone")
    au = sub.add_parser("audition", help="the same line in several voices, one after another (spends credits)")
    au.add_argument("text")
    au.add_argument("--voices", required=True, help="comma-separated voice names")
    au.add_argument("--speed", type=float)
    au.add_argument("--model")
    au.add_argument("--models", help="comma-separated model ids: the same voice in each model (needs exactly one voice)")
    sp = sub.add_parser("speak", help="voice one line now (spends credits) and print the audio file")
    sp.add_argument("text")
    sp.add_argument("--as", dest="speaker", default="narrator")
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
    elif args.cmd == "log":
        show_log(sdir, args.tail, set(args.kind.split(",")) if args.kind else None, args.errors, _parse_age(args.since) if args.since else None,
                 args.as_json, args.summary, args.follow)
    elif args.cmd == "voices":
        from . import speech as speech_mod, voices as voices_mod
        for v in sorted(voices_mod.describe_all(speech_mod.ElevenLabsApi(PROJECT_ROOT)), key=lambda v: (not v["ru"], v["name"])):
            print(f"{'RU ' if v['ru'] else '   '}{v['name'][:40]:40} {v['gender'] or '?':8} {v['accent'] or '':11} {v['category']:12} {v['voice_id']}")
    elif args.cmd == "voice":
        voice_command(sdir, args)
    elif args.cmd == "speak":
        speak_once(sdir, args.text, args.speaker)
    elif args.cmd == "audition":
        audition(sdir, args.text, [v.strip() for v in args.voices.split(",")], args.speed, args.model, args.models)
    elif args.cmd == "enable":
        print(enable())
        print("Next: dm-screen.sh act ... (art + captions), dm-screen.sh turn --file ..., dm-screen.sh start")


def run(argv=None):
    """main() with readable errors: a service refusal or a bad value prints one line instead of a traceback."""
    from . import eventlog, speech

    try:
        return main(argv) or 0
    except (speech.SpeechError, speech.SpeechUnavailable, ValueError) as exc:
        eventlog.log(screen_dir(), "error", where="cli " + " ".join(argv if argv is not None else sys.argv[1:3]), message=f"{type(exc).__name__}: {exc}")
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
