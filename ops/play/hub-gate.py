#!/usr/bin/python3 -I
"""The hub master's gate on the VPS (owner decision 2026-10-28): the forced command of the hub's ssh key.

Installed root-owned as /usr/local/lib/dnd-play/hub-gate (ops/play/README.md, "Hub master (play table)"), outside the
repository: the sandboxed table masters can edit the repository, so the gate runs no repository code and executes
nothing itself (its one child is `systemctl show`, asking systemd for the table driver's pid). It reads SSH_ORIGINAL_COMMAND as `<table> <ticket> <op> [args...]`, forwards it with stdin to the
table driver's bridge socket (backend/hub_master.py, run inside the table's sandbox) and prints the answer.

The socket lives in the unit's RuntimeDirectory, which the table's own SDK master can write: it could replace the
socket with its own listener and collect the tickets. So the gate sends nothing until the listener's SO_PEERCRED pid
is the unit's MainPID (the driver, which binds the socket itself).

Exit codes: the tool's own, or 2 usage, 3 ticket revoked, 4 no hub master on that table (bridge down, busy, or a
socket that is not the driver's), 5 timeout (the call may have run: check before repeating it).
Stdlib only; DND_PLAY_HUB_RUN replaces /run for tests, and only with it DND_PLAY_HUB_MAINPID replaces systemd's answer.
"""

import json
import os
import re
import shlex
import socket
import struct
import subprocess
import sys

TABLE = re.compile(r"[a-z][a-z0-9-]{0,31}")
MAX_STDIN = 1024 * 1024
TIMEOUT = 330.0   # the bridge waits up to 5 s for the call before it, stops a tool after 300 s, runs the hook up to 20 s
SYSTEMCTL = ("/usr/bin/systemctl", "/bin/systemctl")


def fail(code, text):
    print(f"hub-gate: {text}", file=sys.stderr)
    return code


def main_pid(table):
    """The pid systemd started as dnd-play@<table>.service, or None."""
    if os.environ.get("DND_PLAY_HUB_RUN") and os.environ.get("DND_PLAY_HUB_MAINPID"):
        return int(os.environ["DND_PLAY_HUB_MAINPID"])
    systemctl = next((path for path in SYSTEMCTL if os.path.exists(path)), None)
    if systemctl is None:
        return None
    try:
        out = subprocess.run([systemctl, "show", "-p", "MainPID", "--value", f"dnd-play@{table}.service"],
                             capture_output=True, text=True, timeout=10, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        return int(out.stdout.strip() or 0) or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def peer_pid(conn):
    pid, _uid, _gid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    return pid


def main():
    try:
        words = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except ValueError as exc:
        return fail(2, f"cannot parse the command: {exc}")
    if len(words) < 3:
        return fail(2, "usage: <table> <ticket> <tool|prompt|status|read|say> [args...]")
    table, ticket, argv = words[0], words[1], words[2:]
    if not TABLE.fullmatch(table):
        return fail(2, f"invalid table name {table[:40]!r}")
    data = sys.stdin.buffer.read(MAX_STDIN + 1)
    if len(data) > MAX_STDIN:
        return fail(2, "stdin over 1 MiB")
    try:
        stdin = data.decode("utf-8") if data else None
    except UnicodeDecodeError:
        return fail(2, "stdin is not UTF-8 text")
    path = os.path.join(os.environ.get("DND_PLAY_HUB_RUN") or "/run", "dnd-play", table, "hub.sock")
    request = json.dumps({"ticket": ticket, "argv": argv, "stdin": stdin}, ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(TIMEOUT)
            try:
                conn.connect(path)
            except OSError:
                return fail(4, f"no hub master on table {table} (its driver is not in hub mode or not running)")
            driver, peer = main_pid(table), peer_pid(conn)
            if driver is None or peer != driver:
                return fail(4, f"the socket of table {table} is not its driver's (listener pid {peer}, driver pid "
                               f"{driver}): nothing was sent")
            conn.sendall(request)
            # No shutdown of the sending side: the bridge reads EOF as "the gate left" and stops the call.
            with conn.makefile("rb") as answer:
                line = answer.readline()
    except socket.timeout:
        return fail(5, f"no answer from table {table} in {TIMEOUT:.0f}s")
    except OSError as exc:
        return fail(4, f"the bridge of table {table} dropped the call: {exc.strerror or exc}")
    try:
        response = json.loads(line.decode("utf-8"))
        code, output = int(response["code"]), str(response["output"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return fail(4, f"the bridge of table {table} gave no answer")
    if code == 3:
        return fail(3, output)
    sys.stdout.write(output if output.endswith("\n") or not output else output + "\n")
    sys.stdout.flush()
    return min(max(code, 0), 255)


if __name__ == "__main__":
    sys.exit(main())
