#!/usr/bin/env python3
"""dm-screen: build the act page, push turns, run the local server and follow player actions."""

import argparse
import filecmp
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
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")   # NaN is not JSON for the page
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


def set_act(sdir, image, title, kicker=None, place=None, date=None, style=None, captions=None, labels=None, lang=None):
    """A new act. A field left out (None) keeps the current act's value; the captions only when the picture is the
    same, because they point at things in it. Retitling with the shown art.png itself is fine."""
    from . import content, eventlog, theme

    sdir.mkdir(parents=True, exist_ok=True)
    art, previous = sdir / "art.png", _read(sdir / "act.json") or {}
    shown = art.is_file() and os.path.samefile(image, art)
    same_art = shown or (art.is_file() and filecmp.cmp(image, art, shallow=False))

    def keep(value, key, default):
        return value if value is not None else previous.get(key, default)

    cards = content.validate_captions(captions if captions is not None else (previous.get("captions") or []) if same_art else [])
    kicker, place, date = keep(kicker, "kicker", ""), keep(place, "place", ""), keep(date, "date", "")
    style, lang, labels = keep(style, "style", "classic"), keep(lang, "lang", "en"), keep(labels, "labels", {})
    if not shown:
        shutil.copyfile(image, art)
    built = theme.build_theme(theme.extract_palette(art), style)
    act = {"id": previous.get("id", 0) + 1, "title": title, "kicker": kicker, "place": place, "date": date,
           "style": style, "lang": lang, "captions": cards, "labels": labels or {}, "theme": built, "theme_css": theme.theme_css(built)}
    _write(sdir / "act.json", act)
    eventlog.log(sdir, "act", id=act["id"], title=title, kicker=kicker, place=place, date=date, style=style, lang=lang, captions=len(cards),
                 labels=len(labels or {}), theme=built, snapshot=eventlog.world_snapshot(sdir.parent))
    return act


WAIT_CURSOR = "wait-cursor.json"


def read_cursor(sdir):
    """The last player action delivered to the master (0 when nothing was delivered yet)."""
    try:
        return int((_read(Path(sdir) / WAIT_CURSOR) or {}).get("last", 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def write_cursor(sdir, last):
    _write(Path(sdir) / WAIT_CURSOR, {"last": int(last)})


def next_batch(sdir, after, settle=1.5, max_events=6, timeout=0, poll=0.3):
    """Player actions newer than `after`, oldest first and at most `max_events`. Blocks until one arrives, then waits
    `settle` seconds so a second player or a correction comes in the same batch; [] on timeout. Never moves the cursor."""
    from . import inbox

    deadline = time.monotonic() + timeout if timeout else None
    while True:
        if inbox.read_events(sdir, after_id=after):
            time.sleep(settle)
            return inbox.read_events(sdir, after_id=after)[:max_events]
        if deadline and time.monotonic() >= deadline:
            return []
        time.sleep(poll)


def set_turn(sdir, data, answered=None):
    """Publish a turn. `answered` is the last action it answers: by default the delivery cursor when there is one (an
    action that came while the master wrote stays waiting), else the newest action in the inbox."""
    from . import content, eventlog, inbox

    checked = content.validate_turn(data)
    previous = _read(sdir / "turn.json") or {}
    if answered is None and (sdir / WAIT_CURSOR).is_file():
        answered = read_cursor(sdir)
    elif answered is None:
        events = inbox.read_events(sdir)
        answered = events[-1]["id"] if events else 0
    turn = {"id": previous.get("id", 0) + 1, "answered": int(answered), **checked}
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

    from . import audio, clock, eventlog, server, speech, voice

    campaign = sdir.parent
    api = speech.ElevenLabsApi(PROJECT_ROOT)
    speaker = speech.Speaker(sdir, api, lambda: speech.characters_from_world(campaign))
    httpd, token = server.make_server(sdir, port=port, views_provider=lambda: get_campaign_views(campaign),
                                      clock_provider=lambda: clock.world_clock(campaign), speaker=speaker,
                                      director=audio.Director(PROJECT_ROOT, api, speaker, log=lambda kind, **data: eventlog.log(sdir, kind, **data)),
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


def online_driver(sdir):
    """The online driver's state when a live driver of any table plays this screen (world-state/online-*-status.json), else None."""
    from . import server

    master = server.master_status(sdir)
    return master if master and master["state"] != "offline" else None


def listen(sdir, from_start, poll=0.3):
    """Print actions as they arrive and move the delivery cursor with them (old actions count as delivered)."""
    from . import inbox

    events = inbox.read_events(sdir)
    last = 0 if from_start else (events[-1]["id"] if events else 0)
    write_cursor(sdir, last)
    while True:
        for event in inbox.read_events(sdir, after_id=last):
            print(inbox.format_line(event), flush=True)
            last = event["id"]
            write_cursor(sdir, last)
        time.sleep(poll)


def wait_for_action(sdir, after=None, timeout=0, settle=1.5, poll=0.3):
    """Block until the next player action, print it (with any that follow within `settle` seconds) and return 0.

    For agents without a persistent monitor: run it as a background command, answer when it exits, run it again.
    The cursor in <screen>/wait-cursor.json makes a restart neither miss nor repeat an action; the shown turn's
    'answered' is only the starting point when there is no cursor yet. Returns 2 on timeout.
    """
    from . import inbox

    if after is None:
        after = read_cursor(sdir) if (sdir / WAIT_CURSOR).is_file() else (_read(sdir / "turn.json") or {}).get("answered", 0)
    events = next_batch(sdir, after, settle=settle, timeout=timeout, poll=poll)
    if not events:
        print("no player action yet: run wait again", flush=True)
        return 2
    for event in events:
        print(inbox.format_line(event), flush=True)
    write_cursor(sdir, events[-1]["id"])
    return 0


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
        extra += f" | {entry['blocks'] if isinstance(entry['blocks'], int) else len(entry['blocks'])} blocks"
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


def key_command(action):
    from . import keys, speech

    if action == "paste":
        for reader in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"], ["xsel", "-ob"]):
            if shutil.which(reader[0]):
                text = subprocess.run(reader, capture_output=True, text=True).stdout
                break
        else:
            raise SystemExit("no clipboard tool found (wl-paste, xclip or xsel)")
        keys.store_key(PROJECT_ROOT / ".env", text)
        if shutil.which("wl-copy"):
            subprocess.run(["wl-copy", "--clear"], capture_output=True)
        print("key stored in .env, clipboard cleared")
    key = speech.load_api_key(PROJECT_ROOT, {})
    if not key:
        raise SystemExit("no ELEVENLABS_API_KEY in .env")
    print(f"key ending {key[-4:]}")
    for name, ok in keys.permission_report(key).items():
        print(f"  {'UNKNOWN (no answer)' if ok is None else 'ok     ' if ok else 'MISSING'} {name}")


def voice_command(sdir, args):
    from . import speech, voices

    api = speech.ElevenLabsApi(PROJECT_ROOT)
    if args.what == "show":
        config = speech.load_config(sdir)
        print("model:", config["model"], "| language:", config["language"])
        print("narrator:", config.get("narrator") or "(not set)")
        print("default:", config.get("default") or "(not set)")
        for gender, profile in sorted((config.get("cast") or {}).items()):
            print(f"cast {gender}:", profile)
        try:
            sub = api.subscription()
            print(f"own voice slots: {sub.get('voice_slots_used')} of {sub.get('voice_limit')} used")
        except Exception as exc:
            print(f"own voice slots: unknown ({type(exc).__name__})")
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
    if args.what == "delete":
        return delete_voice(api, args.name or args.voice, args.force)
    if not args.voice:
        raise SystemExit("--voice is required")
    effects = {k: v for k, v in (("environment_id", args.env), ("distance", args.distance), ("pan", args.pan),
                                 ("filter_preset_id", args.filter)) if v is not None}
    profile = voices.make_profile(voices.find_voice(api, args.voice), args.model, args.stability, args.similarity, effects, args.speed)
    if args.what == "cast":
        if args.name not in speech.CASTS:
            raise SystemExit(f"voice cast {'|'.join(speech.CASTS)} --voice ...")
        voices.set_cast(sdir, args.name, profile)
    elif args.what == "narrator":
        voices.set_narrator(sdir, profile)
    elif args.what == "default":
        voices.set_default(sdir, profile)
    else:
        if not args.name:
            raise SystemExit('give the character name: voice set "Name" --voice ...')
        voices.set_character_voice(sdir.parent, args.name, profile)
    print(f"{args.what}{' ' + args.name if args.what in ('set', 'cast') else ''}: {profile['name']}")


def voice_users(voice_id):
    """Every campaign place that uses a voice: the screen config (narrator, default, cast) and character cards."""
    users = []
    for campaign in sorted(c for c in (PROJECT_ROOT / "world-state" / "campaigns").iterdir() if c.is_dir()):
        config = _read(campaign / "screen" / "speech.json") or {}
        for role in ("narrator", "default"):
            if (config.get(role) or {}).get("voice_id") == voice_id:
                users.append(f"{campaign.name}: {role}")
        for gender, profile in (config.get("cast") or {}).items():
            if (profile or {}).get("voice_id") == voice_id:
                users.append(f"{campaign.name}: cast {gender}")
        world = _read(campaign / "world.json") or {}
        for node in (world.get("nodes") or {}).values():
            if ((node.get("data") or {}).get("voice") or {}).get("voice_id") == voice_id:
                users.append(f"{campaign.name}: {node.get('name')}")
    return users


def delete_voice(api, query, force=False):
    from . import voices

    if not query:
        raise SystemExit('voice delete "Name or id" [--force]')
    voice = voices.find_voice(api, query)
    if voice.get("category") == "premade":
        raise SystemExit(f"{voice['name']} is a premade voice: it cannot be deleted")
    users = voice_users(voice["voice_id"])
    if users and not force:
        raise SystemExit(f"{voice['name']} is still used by: " + "; ".join(users) + ". Give them another voice first, or pass --force")
    api.delete_voice(voice["voice_id"])
    print(f"deleted {voice['name']} ({voice['voice_id']})" + (f"; still referenced by: {'; '.join(users)}" if users else ""))


SEED_FILE = Path(__file__).with_name("audio_seed.json")


def audio_command(args):
    from . import audio, eventlog, speech

    library = audio.Library(PROJECT_ROOT)
    if args.what == "list":
        for e in sorted(library.entries(), key=lambda e: (e["kind"], e["title"])):
            if not args.kind or e["kind"] == args.kind:
                print(f"{e['id']}  {e['kind']:8} {e.get('source', ''):11} {e['title'][:48]:48} [{', '.join(e.get('tags', []))}]")
        return
    if args.what == "find":
        entry = library.find(args.kind or "sfx", args.text, args.tags.split(",") if args.tags else [])
        print(f"{entry['id']}  {entry['title']}  {library.path(entry)}" if entry else "nothing in the library")
        return
    if args.what == "normalize":
        print(f"{library.renormalize()} sounds brought to even loudness")
        return
    if args.what == "remove":
        library.remove(args.text)
        print("removed", args.text)
        return
    if args.what == "add":
        if not (args.kind and args.title):
            raise SystemExit("audio add <file|url> --kind sfx|ambience|music --title ... [--tags a,b] [--license ...] [--attribution ...]")
        remote = args.text.startswith(("http://", "https://"))
        data = audio.download(args.text) if remote else Path(args.text).read_bytes()
        entry = library.add(data, audio.extension(args.text), args.kind, args.title, args.tags.split(",") if args.tags else [],
                            source=args.source or ("web" if remote else "local"), license=args.license or "", attribution=args.attribution or "",
                            url=args.text if remote else "", loop=args.kind != "sfx")
        print(f"added {entry['id']} ({entry['kind']}): {entry['title']}")
        return
    if args.what == "seed":
        seeds = json.loads(SEED_FILE.read_text(encoding="utf-8"))["sounds"]
        have = {e.get("url") for e in library.entries()}
        for seed in seeds:
            if seed["url"] in have:
                continue
            try:
                library.add(audio.download(seed["url"]), audio.extension(seed["url"]), seed["kind"], seed["title"], seed.get("tags", []),
                            source=seed.get("source", "web"), license=seed.get("license", ""), attribution=seed.get("attribution", ""),
                            url=seed["url"], loop=seed["kind"] != "sfx")
                print(f"added {seed['kind']}: {seed['title']}")
            except Exception as exc:
                print(f"skipped {seed['title']}: {type(exc).__name__}: {exc}")
        return
    if args.what == "make":
        kind = args.kind or "sfx"
        cue = audio.validate_cue({"cue": args.text, "tags": args.tags.split(",") if args.tags else [],
                                  **({"seconds": args.seconds} if args.seconds else {})}, kind, "make")
        sdir = screen_dir()
        api = speech.ElevenLabsApi(PROJECT_ROOT)
        director = audio.Director(PROJECT_ROOT, api, speech.Speaker(sdir, api, lambda: {}), log=lambda kind, **data: eventlog.log(sdir, kind, **data))
        entry = director.library.find(kind, cue["cue"], cue["tags"]) or director._free(kind, cue) or director._generate(kind, cue)
        print(f"{entry['id']}  {entry.get('source')}  {entry['title']}  {library.path(entry)}")


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
    a = sub.add_parser("act", help="start a new act: key art, captions, theme from the art; a field left out keeps the current act's value (captions only with the same picture)")
    a.add_argument("--image", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--kicker")
    a.add_argument("--place")
    a.add_argument("--date")
    a.add_argument("--style", choices=["classic", "severe", "soft"], help="default: the current act's, else classic")
    a.add_argument("--lang", choices=["en", "ru"], help="interface language of the page (default: the current act's, else en)")
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
    wt = sub.add_parser("wait", help="wait for the next player action, print it and exit (for agents without a Monitor tool)")
    wt.add_argument("--after", type=int, help="action id already handled (default: the saved cursor or the shown turn)")
    wt.add_argument("--timeout", type=float, default=0, help="seconds; exit 2 when nothing came (0 = wait forever)")
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
    ky = sub.add_parser("key", help="ElevenLabs key: 'paste' stores the key from the clipboard into .env, 'check' shows what it may do")
    ky.add_argument("action", choices=["paste", "check"])
    sub.add_parser("voices", help="list the voices of your ElevenLabs account (Russian first)")
    vp = sub.add_parser("voice", help="narrator, default and per-character voices")
    vp.add_argument("what", choices=["narrator", "default", "cast", "model", "set", "show", "design", "keep", "delete"])
    vp.add_argument("name", nargs="?", help="character name for 'set', male|female for 'cast', model id for 'model', voice for 'delete'")
    vp.add_argument("--force", action="store_true", help="delete: even when a campaign still uses the voice")
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
    ad = sub.add_parser("audio", help="the shared library of sound effects, ambience and music")
    ad.add_argument("what", choices=["list", "find", "add", "remove", "seed", "make", "normalize"])
    ad.add_argument("text", nargs="?", default="", help="find/make: the cue; add: a file or URL; remove: the entry id")
    ad.add_argument("--kind", choices=["sfx", "ambience", "music"])
    ad.add_argument("--tags", help="comma-separated English tags")
    ad.add_argument("--title")
    ad.add_argument("--seconds", type=float)
    ad.add_argument("--license")
    ad.add_argument("--attribution")
    ad.add_argument("--source")
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
        cards = json.loads(Path(args.captions).read_text(encoding="utf-8"))["cards"] if args.captions else None
        labels = json.loads(Path(args.labels).read_text(encoding="utf-8")) if args.labels else None
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
        if os.environ.get("DM_SCREEN_PUBLIC_URL"):
            print("public:", os.environ["DM_SCREEN_PUBLIC_URL"])
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
        if info and os.environ.get("DM_SCREEN_PUBLIC_URL"):
            print("public:", os.environ["DM_SCREEN_PUBLIC_URL"])
    elif args.cmd in ("listen", "wait") and online_driver(sdir):
        raise SystemExit(f"the online table driver answers this screen's actions (bash tools/dm-play.sh status): {args.cmd} would move "
                         "its delivery cursor and take them away from it")
    elif args.cmd == "listen":
        listen(sdir, args.from_start)
    elif args.cmd == "wait":
        return wait_for_action(sdir, args.after, args.timeout)
    elif args.cmd == "serve":
        serve(sdir, args.port)
    elif args.cmd == "log":
        show_log(sdir, args.tail, set(args.kind.split(",")) if args.kind else None, args.errors, _parse_age(args.since) if args.since else None,
                 args.as_json, args.summary, args.follow)
    elif args.cmd == "key":
        key_command(args.action)
    elif args.cmd == "voices":
        from . import speech as speech_mod, voices as voices_mod
        for v in sorted(voices_mod.describe_all(speech_mod.ElevenLabsApi(PROJECT_ROOT)), key=lambda v: (not v["ru"], v["name"])):
            print(f"{'RU ' if v['ru'] else '   '}{v['name'][:40]:40} {v['gender'] or '?':8} {v['accent'] or '':11} {v['category']:12} {v['voice_id']}")
    elif args.cmd == "voice":
        voice_command(sdir, args)
    elif args.cmd == "audio":
        audio_command(args)
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
