"""The online tables: which campaign each shared screen plays (world-state/online-<table>.json) and its driver's status.

The driver (backend.screen_driver) reads the config between master turns and writes the status. CLI: tools/dm-play.sh.
A table is named by DM_PLAY_TABLE (default "play", the first table: world-state/online-play.json); owner 2026-10-27:
a second table ("demo") plays a copy of a campaign for guests beside the owner's own.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CAMPAIGN = "pratchett-dungeon"
DEFAULT_PORT = 18116
TABLE = "play"
# No dashes: a config online-<table>.json can then never match the status pattern below.
_TABLE_NAME = re.compile(r"[a-z][a-z0-9]{0,30}")
STATUS_GLOB = "online-*-status.json"   # beside campaigns/: lib/screen/server.py reads them from there


def table_name(table=None):
    name = str(table or os.environ.get("DM_PLAY_TABLE") or TABLE).strip()
    if not _TABLE_NAME.fullmatch(name):
        raise ValueError(f"invalid table name {name!r}: lowercase letters and digits")
    return name


def default_port():
    """A new table config's port: DM_PLAY_PORT (each further table needs its own), else 18116."""
    try:
        return int(os.environ.get("DM_PLAY_PORT") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def config_path(root=PROJECT_ROOT, table=None):
    custom = os.environ.get("DM_PLAY_CONFIG") if table is None else None
    path = Path(custom or f"world-state/online-{table_name(table)}.json")
    return path if path.is_absolute() else Path(root) / path


def status_path(root=PROJECT_ROOT, table=None):
    return Path(root) / "world-state" / f"online-{table_name(table)}-status.json"


def table_names(root=PROJECT_ROOT):
    """Every table with a config or a status file."""
    names = set()
    for path in (Path(root) / "world-state").glob("online-*.json"):
        name = path.name[len("online-"):-len(".json")].removesuffix("-status")
        if _TABLE_NAME.fullmatch(name):
            names.add(name)
    return sorted(names)


def campaigns_dir(root=PROJECT_ROOT):
    return Path(root) / "world-state" / "campaigns"


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, IsADirectoryError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path, data, mode=0o644):
    """Atomic: a reader never sees half a file. Changes nothing (and keeps the mtime) when the content is the same."""
    path = Path(path)
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.stem + ".", suffix=path.suffix, dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return True


class CampaignError(ValueError):
    """A configured campaign that is not a valid campaign of this repository."""


def check_campaign(name, root=PROJECT_ROOT):
    """The campaign name when world-state/campaigns/<name>/campaign-overview.json exists, else CampaignError."""
    name = str(name or "").strip()
    if not name or name.startswith(".") or ".." in name or "/" in name or "\\" in name:
        raise CampaignError(f"invalid campaign name {name!r}")
    if not (campaigns_dir(root) / name / "campaign-overview.json").is_file():
        raise CampaignError(f"no campaign {name!r} (world-state/campaigns/{name}/campaign-overview.json is missing)")
    return name


def normalize(raw, campaign=None):
    raw = raw if isinstance(raw, dict) else {}

    def number(key, default):
        try:
            return int(raw.get(key, default))
        except (TypeError, ValueError):
            return default

    config = {"campaign": str(raw.get("campaign") or campaign or DEFAULT_CAMPAIGN), "port": number("port", default_port()),
              "paused": raw.get("paused") is True, "screen_restart": number("screen_restart", 0)}
    if raw.get("session_reset") is not None:   # only once `new-session` was used
        config["session_reset"] = number("session_reset", 0)
    return config


def load_config(root=PROJECT_ROOT, campaign=None, create=False, table=None):
    """The table config; with `create`, a missing file is written with `campaign` (or the default campaign)."""
    path = config_path(root, table)
    raw = read_json(path)
    config = normalize(raw, campaign)
    if raw is None and create:
        write_json(path, config)
    return config


def update_config(root=PROJECT_ROOT, **changes):
    config = {**load_config(root), **changes}
    write_json(config_path(root), config)
    return config


def read_status(root=PROJECT_ROOT, table=None):
    return read_json(status_path(root, table))


def write_status(status, root=PROJECT_ROOT):
    return write_json(status_path(root), status)


def driver_alive(status):
    try:
        os.kill(int((status or {}).get("pid")), 0)
    except PermissionError:
        return True
    except (ProcessLookupError, TypeError, ValueError, OverflowError):
        return False
    return True


def _live(status):
    return status.get("campaign") if status and status.get("state") != "offline" and driver_alive(status) else None


def live_campaign(root=PROJECT_ROOT):
    """The campaign this table's running driver plays now, else None."""
    return _live(read_status(root))


def live_campaigns(root=PROJECT_ROOT):
    """The campaigns running drivers play now on any table (the web game master leaves them alone meanwhile)."""
    return {name for path in (Path(root) / "world-state").glob(STATUS_GLOB) if (name := _live(read_json(path)))}


def other_table_with(campaign, root=PROJECT_ROOT):
    """Another table set to play `campaign` (its config) or playing it now (its status), else None."""
    own = table_name()
    for table in table_names(root):
        if table != own and campaign in (load_config(root, table=table)["campaign"] if config_path(root, table).is_file() else None,
                                         _live(read_status(root, table))):
            return table
    return None


def status_lines(root=PROJECT_ROOT):
    config, status = load_config(root), read_status(root)
    lines = [f"table {table_name()}: campaign {config['campaign']}, port {config['port']}, paused {'yes' if config['paused'] else 'no'}, "
             f"screen restarts {config['screen_restart']}"]
    if not status:
        return lines + ["driver: no status yet (not started)"]
    alive = driver_alive(status)
    lines.append(f"driver: {'running' if alive else 'not running'} (pid {status.get('pid')}), state {status.get('state') if alive else 'offline'}, "
                 f"campaign {status.get('campaign')}, port {status.get('port')}")
    lines.append(f"session: {status.get('session_id') or '(none yet)'}")
    lines.append(f"turns: {status.get('turns_hour', 0)} this hour, {status.get('turns_day', 0)} today, last {status.get('last_turn_at') or 'never'}")
    if status.get("last_error"):
        lines.append(f"last error: {status['last_error']}")
    if isinstance(status.get("retry_at"), (int, float)):
        lines.append("usage limit: nothing goes to the master before "
                     + datetime.fromtimestamp(status["retry_at"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    if status.get("campaign") != config["campaign"] and alive:
        lines.append(f"pending: the driver switches to {config['campaign']} after the current turn")
    if os.environ.get("DM_SCREEN_PUBLIC_URL"):
        lines.append(f"public: {os.environ['DM_SCREEN_PUBLIC_URL']}")
    return lines


def main(argv=None, root=PROJECT_ROOT):
    ap = argparse.ArgumentParser(prog="dm-play", description="the online screen tables (driver: backend.screen_driver)")
    ap.add_argument("--table", help=f"which table (default: DM_PLAY_TABLE, else {TABLE!r}); 'tables' lists them")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="the driver's state and the table config")
    sub.add_parser("tables", help="every table: campaign, state, port")
    sw = sub.add_parser("switch", help="play another campaign; the driver switches after the current turn")
    sw.add_argument("campaign")
    sub.add_parser("restart-screen", help="restart the screen server (after a fix in lib/screen)")
    sub.add_parser("new-session", help="drop the master's conversation: a fresh session on the same campaign after the current turn")
    sub.add_parser("pause", help="stop answering actions; the screen stays up")
    sub.add_parser("resume", help="answer actions again")
    args = ap.parse_args(argv)
    try:
        if args.table:
            os.environ["DM_PLAY_TABLE"] = table_name(args.table)
            os.environ.pop("DM_PLAY_CONFIG", None)   # the named table's own file
        table_name()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.cmd == "status":
        print("\n".join(status_lines(root)))
    elif args.cmd == "tables":
        for table in table_names(root) or [TABLE]:
            config, status = load_config(root, table=table), read_status(root, table)
            state = (status.get("state") if driver_alive(status) else "offline") if status else "not started"
            print(f"{table}: campaign {config['campaign']}, port {config['port']}, {state}")
    elif args.cmd == "switch":
        try:
            name = check_campaign(args.campaign, root)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if busy := other_table_with(name, root):
            print(f"error: table {busy!r} plays {name}; two masters must never share a campaign (copy it instead)", file=sys.stderr)
            return 1
        update_config(root, campaign=name)
        print(f"switch to {name} requested: the driver ends the current turn, then starts a fresh session there")
    elif args.cmd == "restart-screen":
        config = update_config(root, screen_restart=load_config(root)["screen_restart"] + 1)
        print(f"screen restart {config['screen_restart']} requested")
    elif args.cmd == "new-session":
        config = update_config(root, session_reset=load_config(root).get("session_reset", 0) + 1)
        print(f"fresh master session {config['session_reset']} requested: the driver starts it after the current turn")
    elif args.cmd in ("pause", "resume"):
        update_config(root, paused=args.cmd == "pause")
        print("paused: actions wait, the screen stays up" if args.cmd == "pause" else "resumed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
