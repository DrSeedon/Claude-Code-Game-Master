"""The hub master's bridge, gate and ssh wrapper (backend/hub_master.py, ops/play/hub-gate.py, ops/play/hub-vps.sh),
over a real unix socket with fake tools in a temp project."""

import asyncio
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from backend import hub_master
from backend.hub_master import CUT, REVOKED, HubBridge, HubSettings, deny_reason, post_event
from lib.screen import hook, masterlog, online

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "ops" / "play" / "hub-gate.py"
WRAPPER = REPO / "ops" / "play" / "hub-vps.sh"
QUIET_HOOK = [sys.executable, "-c", "import sys; sys.stdin.read()"]

TOOLS = {
    "dm-echo.sh": 'echo "args:$*"\necho "campaign:$DM_ACTIVE_CAMPAIGN autostart:$DM_SCREEN_AUTOSTART term:$TERM"\ncat\n',
    "dm-fail.sh": 'echo "broken"\nexit 7\n',
    "dm-big.sh": "head -c 200000 /dev/zero | tr '\\0' a\nprintf END\n",
    "dm-slow.sh": 'sleep 30 &\necho $! > "$PID_FILE"\nsleep 30\n',
    "dm-sleep.sh": 'echo "start $1" >> "$LOG_FILE"\nsleep 0.3\necho "end $1" >> "$LOG_FILE"\necho done\n',
    "dm-roll.sh": 'echo "🎲 1d20: 17"\n',
    "dm-screen.sh": 'echo "screen ran $*"\n',
    "dm-campaign.sh": 'echo "campaign ran $*"\n',
    "dm-play.sh": 'echo "play ran $*"\n',
    "dm-mark.sh": 'touch "$MARK_FILE"\necho marked\n',
}


@pytest.fixture
def short_dir():
    """Unix socket paths are capped near 108 bytes: pytest's tmp_path can be longer."""
    path = Path(tempfile.mkdtemp(prefix="hub", dir="/tmp"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def root(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    for name, body in TOOLS.items():
        (tools / name).write_text("#!/bin/bash\n" + body, encoding="utf-8")
    sdir = tmp_path / "world-state" / "campaigns" / "alpha" / "screen"
    sdir.mkdir(parents=True)
    return tmp_path


def make_bridge(root, sock, **kw):
    ctx = {"campaign": "alpha", "sdir": root / "world-state" / "campaigns" / "alpha" / "screen", "turn": 7}
    return HubBridge(sock, root, "play", lambda: ctx, **{"hook_argv": QUIET_HOOK, **kw})


async def ask(path, ticket, argv, stdin=None, raw=None):
    reader, writer = await asyncio.open_unix_connection(str(path), limit=8 * 1024 * 1024)
    writer.write(raw if raw is not None else (json.dumps({"ticket": ticket, "argv": argv, "stdin": stdin}) + "\n").encode())
    await writer.drain()
    line = await reader.readline()
    writer.close()
    return json.loads(line)


def with_bridge(root, sock, scenario, **kw):
    async def main():
        bridge = make_bridge(root, sock, **kw)
        await bridge.start()
        try:
            return await scenario(bridge)
        finally:
            await bridge.stop()

    return asyncio.run(main())


# ---- settings and the webhook POST

def test_settings_default_to_sdk_and_hub_needs_a_webhook_and_a_socket(caplog):
    assert HubSettings.from_env({}).master == "sdk"
    assert HubSettings.from_env({"DM_PLAY_MASTER": "opus"}).master == "sdk"
    assert HubSettings.from_env({"DM_PLAY_MASTER": "hub", "RUNTIME_DIRECTORY": "/run/dnd-play/play"}).master == "sdk"
    assert HubSettings.from_env({"DM_PLAY_MASTER": "hub", "DM_PLAY_HUB_WEBHOOK": "https://h/x"}).master == "sdk"
    hub = HubSettings.from_env({"DM_PLAY_MASTER": "hub", "DM_PLAY_HUB_WEBHOOK": "https://h/tok", "RUNTIME_DIRECTORY": "/run/dnd-play/play",
                                "DM_PLAY_HUB_TIMEOUT": "120", "DM_PLAY_HUB_FAILS": "3", "DM_PLAY_HUB_PAUSE": "x"})
    assert (hub.master, hub.socket, hub.timeout, hub.fails, hub.pause) == ("hub", Path("/run/dnd-play/play/hub.sock"), 120.0, 3, 900.0)
    assert "tok" not in repr(hub) and "https://h" not in caplog.text
    assert HubSettings.from_env({"DM_PLAY_MASTER": "hub", "DM_PLAY_HUB_WEBHOOK": "https://h/x", "DM_PLAY_HUB_SOCKET": "/s/h.sock"}).socket == Path("/s/h.sock")


def test_the_sdk_master_is_the_fallback_unless_the_table_says_none():
    assert HubSettings.from_env({}).sdk_fallback
    assert HubSettings.from_env({"DM_PLAY_HUB_FALLBACK": "bogus"}).sdk_fallback
    assert not HubSettings.from_env({"DM_PLAY_HUB_FALLBACK": " None "}).sdk_fallback


class _Hook(BaseHTTPRequestHandler):
    status = 200
    seen = []
    agents = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).seen.append((self.path, self.headers["Content-Type"], json.loads(body)))
        type(self).agents.append(self.headers["User-Agent"])
        self.send_response(type(self).status)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_post_event_sends_json_and_its_errors_never_name_the_url():
    httpd = HTTPServer(("127.0.0.1", 0), _Hook)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}/hooks/SECRETTOKEN"
    try:
        assert post_event(url, {"message": "Привет"}) == (True, None)
        assert _Hook.seen[-1] == ("/hooks/SECRETTOKEN", "application/json", {"message": "Привет"})
        # Cloudflare in front of the T3 webhook answers 403 to urllib's default agent (2026-10-28).
        assert _Hook.agents[-1] == "dnd-play-driver/1 (online table hub master)"
        _Hook.status = 500
        ok, error = post_event(url, {"message": "x"})
        assert not ok and error == "HTTP 500"
    finally:
        httpd.shutdown()
        _Hook.status = 200
    ok, error = post_event(url, {}, timeout=2)
    assert not ok and error and "SECRETTOKEN" not in error and "127.0.0.1" not in error


# ---- the bridge

def test_a_valid_ticket_runs_the_tool_with_stdin_and_the_masters_environment(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        ticket = bridge.issue()
        assert oct(sock.stat().st_mode & 0o777) == "0o600"
        first = await ask(sock, ticket, ["bash", "tools/dm-echo.sh", "a b", "Ж"], stdin="from stdin\n")
        second = await ask(sock, ticket, ["dm-echo.sh"])
        third = await ask(sock, ticket, ["tools/dm-fail.sh"])
        return first, second, third

    first, second, third = with_bridge(root, sock, scenario)
    assert first["code"] == 0
    assert first["output"] == "args:a b Ж\ncampaign:alpha autostart:0 term:dumb\nfrom stdin\n"
    assert second["code"] == 0 and second["output"].startswith("args:\n")
    assert third == {"code": 7, "output": "broken\n"}
    assert not sock.exists()


def test_the_output_is_capped_with_head_and_tail(root, short_dir):
    sock = short_dir / "hub.sock"
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["dm-big.sh"]))
    assert result["code"] == 0 and CUT in result["output"] and len(result["output"]) < 66 * 1024
    assert result["output"].startswith("aaaa") and result["output"].endswith("aaaEND")


def test_a_tool_over_the_time_limit_is_killed_with_its_process_group(root, short_dir, monkeypatch):
    sock, pid_file = short_dir / "hub.sock", short_dir / "pid"
    monkeypatch.setenv("PID_FILE", str(pid_file))
    started = time.monotonic()
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["dm-slow.sh"]), tool_timeout=0.5)
    assert time.monotonic() - started < 10
    assert result["code"] == 124 and "timed out after" in result["output"]
    pid = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"the background sleep {pid} of the tool survived")


def test_a_wrong_or_revoked_ticket_is_refused_and_runs_nothing(root, short_dir, monkeypatch):
    sock, mark = short_dir / "hub.sock", short_dir / "mark"
    monkeypatch.setenv("MARK_FILE", str(mark))

    async def scenario(bridge):
        results = [await ask(sock, None, ["dm-mark.sh"])]       # no ticket issued yet
        ticket = bridge.issue()
        results.append(await ask(sock, ticket + "x", ["dm-mark.sh"]))
        results.append(await ask(sock, "", ["prompt"]))
        await bridge.revoke()
        results.append(await ask(sock, ticket, ["dm-mark.sh"]))
        results.append(await ask(sock, ticket, ["read", "screen/x"]))
        old, new = ticket, bridge.issue()
        results.append(await ask(sock, old, ["dm-mark.sh"]))    # a newer event replaced it
        status = json.loads((await ask(sock, old, ["status"]))["output"])
        fresh = json.loads((await ask(sock, new, ["status"]))["output"])
        return results, status, fresh

    results, status, fresh = with_bridge(root, sock, scenario)
    assert [r["code"] for r in results] == [3] * 6 and all(r["output"] == REVOKED for r in results)
    assert REVOKED.startswith("ticket revoked:") and not mark.exists()
    assert status == {"table": "play", "campaign": "alpha", "turn": 7, "ticket_ok": False} and fresh["ticket_ok"] is True


@pytest.mark.parametrize("argv, allowed", [
    (["dm-screen.sh", "start"], False), (["dm-screen.sh", "listen"], False), (["dm-screen.sh", "speak", "x"], False),
    (["dm-screen.sh", "audio", "make", "rain"], False), (["dm-screen.sh", "audio", "--kind", "sfx", "add", "f"], False),
    (["dm-screen.sh", "voice", "design"], False), (["dm-screen.sh", "key", "check"], False),
    (["dm-campaign.sh", "switch", "beta"], False), (["dm-campaign.sh", "delete", "alpha"], False),
    (["dm-campaign.sh", "create", "x"], False), (["dm-campaign.sh", "reset"], False),
    (["dm-play.sh", "switch", "beta"], False), (["dm-play.sh", "pause"], False), (["dm-play.sh", "--table", "demo", "status"], False),
    (["dm-play.sh", "status"], True), (["dm-campaign.sh", "list"], True), (["dm-screen.sh", "turn", "--file", "-"], True),
    (["dm-screen.sh", "audio", "find", "rain", "--kind", "music"], True), (["dm-screen.sh", "log", "--tail", "3"], True),
])
def test_the_contracts_forbidden_commands_are_refused(root, short_dir, argv, allowed):
    sock = short_dir / "hub.sock"
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), argv))
    if allowed:
        assert result["code"] == 0 and " ran " in result["output"], result
    else:
        assert result["code"] == 2 and result["output"].startswith("refused:") and " ran" not in result["output"], result


def test_deny_reason_covers_whole_tools_and_reset():
    assert deny_reason("dm-migrate-worldgraph.sh", []) and deny_reason("dm-extract.sh", ["prepare", "x"])
    assert deny_reason("dm-reset.sh", ["hard"]) and deny_reason("dm-reset.sh", ["preview"]) is None
    assert deny_reason("dm-roll.sh", ["1d20"]) is None


@pytest.mark.parametrize("argv", [["rm", "-rf", "/"], ["../tools/dm-echo.sh"], ["tools/../tools/dm-echo.sh"],
                                  ["dm-missing.sh"], ["dm-Echo.sh"], ["bash", "-c", "id"], ["bash"], ["/bin/sh"],
                                  ["modules/x/tools/dm-echo.sh"]])
def test_only_project_dm_tools_run(root, short_dir, argv):
    sock = short_dir / "hub.sock"
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), argv))
    assert result["code"] == 2 and "args:" not in result["output"]


def test_bad_requests_are_answered_without_running_anything(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        bridge.issue()
        return [await ask(sock, None, None, raw=b"not json\n"), await ask(sock, None, None, raw=b'{"argv": []}\n'),
                await ask(sock, bridge.ticket, ["dm-echo.sh", "a\0b"]),
                await ask(sock, bridge.ticket, ["dm-echo.sh"], stdin="x" * (1024 * 1024 + 1))]

    results = with_bridge(root, sock, scenario)
    assert [r["code"] for r in results] == [2, 2, 2, 2] and "args:" not in json.dumps(results)


def test_read_is_confined_to_the_campaign_directory(root, short_dir):
    sock = short_dir / "hub.sock"
    campaign = root / "world-state" / "campaigns" / "alpha"
    (campaign / "session-handoff.md").write_text("Где мы были", encoding="utf-8")
    (root / "world-state" / "campaigns" / "beta").mkdir()
    (root / "world-state" / "campaigns" / "beta" / "secret.md").write_text("beta", encoding="utf-8")
    (root / ".env").write_text("KEY=1", encoding="utf-8")
    (campaign / "escape.md").symlink_to(root / ".env")
    (campaign / "inside.md").symlink_to(campaign / "session-handoff.md")
    (campaign / "big.md").write_text("x" * (256 * 1024 + 1), encoding="utf-8")
    (campaign / "art.bin").write_bytes(b"\xff\xfe\x00")

    async def scenario(bridge):
        ticket = bridge.issue()
        paths = ["session-handoff.md", "inside.md", "../beta/secret.md", "escape.md", "/etc/hostname", "screen", "big.md",
                 "art.bin", "missing.md", "."]
        return {p: await ask(sock, ticket, ["read", p]) for p in paths}

    results = with_bridge(root, sock, scenario)
    assert results["session-handoff.md"] == {"code": 0, "output": "Где мы были"}
    # No symlink at all, even one that points inside: a symlink is the way out of the directory.
    for path in ("inside.md", "../beta/secret.md", "escape.md", "/etc/hostname", "screen", "big.md", "art.bin", "missing.md", "."):
        assert results[path]["code"] != 0 and "KEY" not in results[path]["output"] and "beta" != results[path]["output"], path


def test_read_cannot_be_raced_out_through_a_swapped_directory(root, short_dir, monkeypatch):
    """A process of the sandbox swaps a directory of the path for a symlink after any check: the read stays inside."""
    import backend.hub_master as hub_master

    sock = short_dir / "hub.sock"
    campaign = root / "world-state" / "campaigns" / "alpha"
    (campaign / "notes").mkdir()
    (campaign / "notes" / "secret.txt").write_text("inside", encoding="utf-8")
    outside = root / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("WEBHOOK-URL", encoding="utf-8")
    real_open, swapped = os.open, []

    def racing_open(path, flags, *args, **kwargs):
        if not swapped:     # the swap lands between whatever the bridge checked and its first open
            swapped.append(True)
            (campaign / "notes").rename(campaign / "notes.real")
            (campaign / "notes").symlink_to(outside)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(hub_master.os, "open", racing_open)
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["read", "notes/secret.txt"]))
    assert swapped and result["code"] != 0 and "WEBHOOK-URL" not in result["output"]


def test_prompt_returns_the_drivers_system_prompt(root, short_dir):
    sock = short_dir / "hub.sock"
    (root / "world-state/campaigns/alpha/screen/gm-system-prompt.md").write_text("# DM rules\n", encoding="utf-8")
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["prompt"]))
    assert result == {"code": 0, "output": "# DM rules\n"}


def test_the_screen_hook_runs_like_claude_code_and_its_nudge_is_appended(root, short_dir):
    sock, captured = short_dir / "hub.sock", short_dir / "payload.json"
    stub = [sys.executable, "-c", "import json, os, sys; data = sys.stdin.read(); open(sys.argv[1], 'w').write(data); "
            "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': "
            "'Screen: start a new act ' + os.environ['DM_PLAY_TABLE'] + ' ' + os.environ['DM_ACTIVE_CAMPAIGN']}}))", str(captured)]
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["dm-roll.sh", "1d20", "--label", "Ловкость"]),
                         hook_argv=stub)
    assert result["code"] == 0
    assert result["output"] == "🎲 1d20: 17\n\n\n[screen hook] Screen: start a new act play alpha"
    payload = json.loads(captured.read_text(encoding="utf-8"))
    assert payload["tool_input"]["command"] == "bash tools/dm-roll.sh 1d20 --label 'Ловкость'"
    assert payload["tool_response"] == {"stdout": "🎲 1d20: 17\n", "stderr": "", "interrupted": False}
    # The real hook reads exactly these keys: the roll reaches the live feed.
    assert hook.activities_from_hook(payload, "ru") == [{"kind": "roll", "text": "🎲 1d20: 17"}]


def test_a_failing_hook_never_fails_the_call(root, short_dir):
    sock = short_dir / "hub.sock"
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["dm-roll.sh"]),
                         hook_argv=[sys.executable, "-c", "import sys; sys.stdin.read(); print('not json'); sys.exit(3)"])
    assert result == {"code": 0, "output": "🎲 1d20: 17\n"}


def test_calls_never_overlap_and_revoke_waits_for_the_running_one(root, short_dir, monkeypatch):
    sock, log = short_dir / "hub.sock", short_dir / "calls.log"
    monkeypatch.setenv("LOG_FILE", str(log))

    async def scenario(bridge):
        ticket = bridge.issue()
        both = await asyncio.gather(ask(sock, ticket, ["dm-sleep.sh", "1"]), ask(sock, ticket, ["dm-sleep.sh", "2"]))
        overlap = log.read_text().split()
        log.unlink()
        running = asyncio.ensure_future(ask(sock, ticket, ["dm-sleep.sh", "3"]))
        while not log.exists():
            await asyncio.sleep(0.01)
        queued = asyncio.ensure_future(ask(sock, ticket, ["dm-sleep.sh", "4"]))
        await asyncio.sleep(0.05)
        await bridge.revoke()
        after_revoke = log.read_text().split()
        return both, overlap, after_revoke, await running, await queued

    both, overlap, after_revoke, running, queued = with_bridge(root, sock, scenario)
    assert [r["code"] for r in both] == [0, 0]
    assert overlap in (["start", "1", "end", "1", "start", "2", "end", "2"], ["start", "2", "end", "2", "start", "1", "end", "1"])
    assert after_revoke == ["start", "3", "end", "3"] and running["code"] == 0
    assert queued["code"] == 3


def test_a_call_the_gate_abandoned_is_stopped_and_frees_the_bridge(root, short_dir, monkeypatch):
    """The agent's Bash timed out and ssh died: the running tool's group is killed and the queued call never runs, so
    nothing of it runs later with a valid ticket."""
    sock, pid_file, mark = short_dir / "hub.sock", short_dir / "pid", short_dir / "mark"
    monkeypatch.setenv("PID_FILE", str(pid_file))
    monkeypatch.setenv("MARK_FILE", str(mark))

    async def send(ticket, argv):
        reader, writer = await asyncio.open_unix_connection(str(sock))
        writer.write((json.dumps({"ticket": ticket, "argv": argv, "stdin": None}) + "\n").encode())
        await writer.drain()
        return writer

    async def scenario(bridge):
        ticket = bridge.issue()
        running = await send(ticket, ["dm-slow.sh"])
        while not pid_file.exists():
            await asyncio.sleep(0.01)
        queued = await send(ticket, ["dm-mark.sh"])
        await asyncio.sleep(0.1)
        queued.close()
        running.close()
        started = time.monotonic()
        after = await ask(sock, ticket, ["dm-echo.sh"])
        return after, time.monotonic() - started

    after, waited = with_bridge(root, sock, scenario, tool_timeout=20)
    assert after["code"] == 0 and waited < 5 and not mark.exists()
    pid = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"the abandoned tool's background sleep {pid} survived")


def test_a_call_behind_a_long_one_answers_busy_without_running(root, short_dir, monkeypatch):
    sock, pid_file, mark = short_dir / "hub.sock", short_dir / "pid", short_dir / "mark"
    monkeypatch.setenv("PID_FILE", str(pid_file))
    monkeypatch.setenv("MARK_FILE", str(mark))

    async def scenario(bridge):
        ticket = bridge.issue()
        running = asyncio.ensure_future(ask(sock, ticket, ["dm-slow.sh"]))
        while not pid_file.exists():
            await asyncio.sleep(0.01)
        busy = await ask(sock, ticket, ["dm-mark.sh"])
        await bridge.revoke()
        return busy, await running

    busy, running = with_bridge(root, sock, scenario, lock_wait=0.2, tool_timeout=0.8)
    assert busy["code"] == 4 and "did NOT run" in busy["output"] and not mark.exists()
    assert running["code"] == 124


def test_slow_tools_extend_the_hub_deadline_for_their_ticket(root, short_dir):
    sock = short_dir / "hub.sock"
    (root / "tools" / "dm-art.sh").write_text("#!/bin/bash\nsleep 0.3\necho picture\n", encoding="utf-8")

    async def scenario(bridge):
        ticket = bridge.issue()
        await ask(sock, ticket, ["dm-echo.sh"])
        quick = bridge.extension()
        running = asyncio.ensure_future(ask(sock, ticket, ["dm-art.sh", "--prompt", "x"]))
        await asyncio.sleep(0.15)
        during = bridge.extension()
        await running
        after = bridge.extension()
        bridge.issue()
        return quick, during, after, bridge.extension()

    quick, during, after, fresh = with_bridge(root, sock, scenario)
    assert quick == 0 and 0.05 < during < after and after >= 0.3 and fresh == 0


def test_extra_connections_are_turned_away(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        idle = [await asyncio.open_unix_connection(str(sock)) for _ in range(4)]
        await asyncio.sleep(0.05)
        extra = await ask(sock, bridge.issue(), ["dm-echo.sh"])
        for _, writer in idle:
            writer.close()
        await asyncio.sleep(0.05)
        later = await ask(sock, bridge.ticket, ["dm-echo.sh"])
        return extra, later

    extra, later = with_bridge(root, sock, scenario, read_timeout=2)
    assert extra["code"] == 4 and extra["output"].startswith("busy") and later["code"] == 0


def test_a_stale_socket_is_replaced(root, short_dir):
    import socket as socket_module

    sock = short_dir / "hub.sock"
    stale = socket_module.socket(socket_module.AF_UNIX)
    stale.bind(str(sock))
    stale.close()
    result = with_bridge(root, sock, lambda bridge: ask(sock, bridge.issue(), ["dm-echo.sh"]))
    assert result["code"] == 0


def test_the_journal_line_names_the_call_but_never_the_ticket_or_stdin(root, short_dir, caplog):
    sock = short_dir / "hub.sock"
    caplog.set_level(logging.INFO, logger="dnd-play")
    holder = {}

    async def scenario(bridge):
        holder["ticket"] = bridge.issue()
        return await ask(sock, holder["ticket"], ["dm-echo.sh", "x" * 500], stdin="STDIN-SECRET")

    assert with_bridge(root, sock, scenario)["code"] == 0
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("hub call dm-echo.sh"))
    assert "exit 0" in line and len(line) < 260
    assert holder["ticket"] not in caplog.text and "STDIN-SECRET" not in caplog.text


# ---- the gate (ops/play/hub-gate.py) against a real bridge

async def gate(run_dir, command, stdin=b"", driver_pid=None):
    """The bridge runs in this test process, so its pid stands for the unit's MainPID."""
    env = {"PATH": os.environ["PATH"], "SSH_ORIGINAL_COMMAND": command, "DND_PLAY_HUB_RUN": str(run_dir),
           "DND_PLAY_HUB_MAINPID": str(driver_pid or os.getpid())}
    proc = await asyncio.create_subprocess_exec(sys.executable, "-I", str(GATE), env=env, stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate(stdin)
    return proc.returncode, out.decode(), err.decode()


def test_the_gate_forwards_calls_and_reports_its_exit_codes(root, short_dir):
    sock = short_dir / "dnd-play" / "play" / "hub.sock"

    async def scenario(bridge):
        ticket = bridge.issue()
        results = {
            "tool": await gate(short_dir, f"play {ticket} dm-echo.sh 'два слова'", "строка\n".encode()),
            "exit": await gate(short_dir, f"play {ticket} dm-fail.sh"),
            "denied": await gate(short_dir, f"play {ticket} dm-screen.sh start"),
            "status": await gate(short_dir, "play nothing status"),
            "usage": await gate(short_dir, "play"),
            "table": await gate(short_dir, f"Play! {ticket} dm-echo.sh"),
            "path": await gate(short_dir, f"../play {ticket} dm-echo.sh"),
            "quote": await gate(short_dir, "play 'unclosed dm-echo.sh"),
            "none": await gate(short_dir, f"demo {ticket} dm-echo.sh"),
            "big": await gate(short_dir, f"play {ticket} dm-echo.sh", b"x" * (1024 * 1024 + 1)),
        }
        await bridge.revoke()
        results["revoked"] = await gate(short_dir, f"play {ticket} dm-echo.sh")
        return results

    results = with_bridge(root, sock, scenario)
    assert results["tool"] == (0, "args:два слова\ncampaign:alpha autostart:0 term:dumb\nстрока\n", "")
    assert results["exit"] == (7, "broken\n", "")
    assert results["denied"][0] == 2 and "refused" in results["denied"][1]
    assert results["status"][0] == 0 and json.loads(results["status"][1])["ticket_ok"] is False
    for key in ("usage", "table", "path", "quote", "big"):
        assert results[key][0] == 2 and results[key][2].startswith("hub-gate:"), key
    assert results["none"][0] == 4 and "no hub master on table demo" in results["none"][2]
    code, out, err = results["revoked"]
    assert code == 3 and out == "" and "ticket revoked" in err


def test_the_gate_reports_a_timeout(root, short_dir, monkeypatch):
    """A bridge that accepts but never answers: exit 5 (the gate's own wait, shortened through a copy)."""
    gate_copy = short_dir / "gate.py"
    gate_copy.write_text(GATE.read_text(encoding="utf-8").replace("TIMEOUT = 330.0", "TIMEOUT = 0.5"), encoding="utf-8")
    sock = short_dir / "dnd-play" / "play" / "hub.sock"
    sock.parent.mkdir(parents=True)

    async def main():
        async def silent(reader, writer):
            await asyncio.sleep(5)

        server = await asyncio.start_unix_server(silent, path=str(sock))
        env = {"PATH": os.environ["PATH"], "SSH_ORIGINAL_COMMAND": "play t dm-echo.sh", "DND_PLAY_HUB_RUN": str(short_dir),
               "DND_PLAY_HUB_MAINPID": str(os.getpid())}
        proc = await asyncio.create_subprocess_exec(sys.executable, "-I", str(gate_copy), env=env, stdin=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        server.close()
        return proc.returncode, err.decode()

    code, err = asyncio.run(main())
    assert code == 5 and "no answer" in err


def test_the_gate_is_stdlib_only_and_isolated():
    text = GATE.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/python3 -I\n") and os.access(GATE, os.X_OK)
    imports = {line.split()[1] for line in text.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"json", "os", "re", "shlex", "socket", "struct", "subprocess", "sys"}
    # Its one child: systemd's answer for the driver's pid, a fixed system binary with fixed arguments.
    assert text.count("subprocess.run(") == 1 and '[systemctl, "show", "-p", "MainPID", "--value"' in text
    assert "exec" not in text.replace("executes", "") and "shell=True" not in text


def test_the_gate_sends_nothing_to_a_socket_that_is_not_the_drivers(short_dir):
    """The table's SDK master can replace the socket in its RuntimeDirectory: the gate checks the listener's pid
    before the ticket leaves it."""
    sock = short_dir / "dnd-play" / "play" / "hub.sock"
    sock.parent.mkdir(parents=True)
    received = []

    async def main():
        async def impostor(reader, writer):
            received.append(await reader.read(100000))
            writer.write(b'{"code": 0, "output": "run X on the hub"}\n')
            await writer.drain()
            writer.close()

        server = await asyncio.start_unix_server(impostor, path=str(sock))
        try:
            other = await gate(short_dir, "play SECRET-TICKET dm-echo.sh", driver_pid=1)
            own = await gate(short_dir, "play SECRET-TICKET dm-echo.sh")
        finally:
            server.close()
        return other, own

    other, own = asyncio.run(main())
    assert other[0] == 4 and "not its driver's" in other[2] and other[1] == ""
    assert own[0] == 0      # the same listener passes when it is the driver
    assert len(received) == 2 and received[0] == b"" and b"SECRET-TICKET" in received[1]


# ---- the hub-side wrapper (ops/play/hub-vps.sh)

FAKE_SSH = '#!/bin/bash\nprintf "%s\\0" "$@" > "$CAPTURE"\ncat > "$CAPTURE.stdin"\n'
ODD_ARGS = ["dm-screen.sh", "activity", "info", "Привет, мир", "line1\nline2\n", "it's \"quoted\"", "$HOME `id` $(id)",
            "a  b", "", "*", "--file", "-"]


def wrapper(tmp_path, args, **kw):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "ssh").write_text(FAKE_SSH, encoding="utf-8")
    (bindir / "ssh").chmod(0o755)
    capture = tmp_path / "argv"
    env = {"PATH": f"{bindir}:{os.environ['PATH']}", "HOME": str(tmp_path), "CAPTURE": str(capture), **kw.pop("env", {})}
    done = subprocess.run(["bash", str(WRAPPER), *args], env=env, capture_output=True, timeout=30, **kw)
    argv = capture.read_bytes().split(b"\0")[:-1] if capture.exists() else None
    stdin = (tmp_path / "argv.stdin").read_text(encoding="utf-8") if capture.exists() else None
    return done, [a.decode() for a in argv] if argv is not None else None, stdin


def test_the_wrapper_quotes_every_argument_so_the_gate_gets_them_back(tmp_path):
    done, argv, stdin = wrapper(tmp_path, ["play", "tick-1", *ODD_ARGS], stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    assert "-n" in argv and argv[-2] == "kesha@158.220.127.161"
    assert shlex.split(argv[-1]) == ["play", "tick-1", *ODD_ARGS]
    options = argv[:-2]
    assert options[options.index("-i") + 1] == str(tmp_path / ".ssh" / "dnd_play_vps")
    for option in ("IdentitiesOnly=yes", "BatchMode=yes", "ConnectTimeout=15", "ConnectionAttempts=3", "ServerAliveInterval=15",
                   "ControlMaster=auto", f"ControlPath={tmp_path}/.ssh/cm-dnd-play-%h-%p", "ControlPersist=600"):
        assert options[options.index(option) - 1] == "-o", option
    assert stdin == ""


def test_the_wrapper_forwards_a_heredoc_and_a_pipe(tmp_path):
    script = f"bash {shlex.quote(str(WRAPPER))} play t dm-screen.sh turn --file - <<'JSON'\n{{\"blocks\": [\"Дождь\"]}}\nJSON\n"
    bindir = tmp_path / "bin"
    done, _, _ = wrapper(tmp_path, ["play", "t", "status"], stdin=subprocess.DEVNULL)   # installs the fake ssh
    env = {"PATH": f"{bindir}:{os.environ['PATH']}", "HOME": str(tmp_path), "CAPTURE": str(tmp_path / "argv"),
           "DND_PLAY_VPS": "kesha@example", "DND_PLAY_VPS_KEY": "/k/key"}
    done = subprocess.run(["bash", "-c", script], env=env, capture_output=True, timeout=30)
    argv = [a.decode() for a in (tmp_path / "argv").read_bytes().split(b"\0")[:-1]]
    assert done.returncode == 0 and "-n" not in argv and argv[-2] == "kesha@example" and argv[argv.index("-i") + 1] == "/k/key"
    assert shlex.split(argv[-1]) == ["play", "t", "dm-screen.sh", "turn", "--file", "-"]
    assert (tmp_path / "argv.stdin").read_text(encoding="utf-8") == '{"blocks": ["Дождь"]}\n'
    done, argv, stdin = wrapper(tmp_path, ["play", "t", "dm-screen.sh", "turn", "--file", "-"], input=b"piped")
    assert "-n" not in argv and stdin == "piped"


def test_the_wrapper_needs_three_arguments(tmp_path):
    done, argv, _ = wrapper(tmp_path, ["play", "t"], stdin=subprocess.DEVNULL)
    assert done.returncode == 2 and b"usage" in done.stderr and argv is None


def test_status_lines_show_the_master(tmp_path, monkeypatch):
    monkeypatch.delenv("DM_PLAY_CONFIG", raising=False)
    monkeypatch.setenv("DM_PLAY_TABLE", "play")
    online.write_status({"pid": os.getpid(), "campaign": "alpha", "state": "idle", "master": "hub",
                         "hub": {"fails": 1, "paused_until": None, "last_result": "no turn in 300s", "last_turn_at": "2026-10-28T10:00:00Z"}},
                        tmp_path)
    lines = online.status_lines(tmp_path)
    assert "master: hub (last no turn in 300s, last hub turn 2026-10-28T10:00:00Z, 1 failures in a row)" in lines
    online.write_status({"pid": os.getpid(), "campaign": "alpha", "state": "idle", "master": "sdk", "hub": None}, tmp_path)
    assert "master: sdk" in online.status_lines(tmp_path)


# ---- the master console (lib/screen/masterlog.py) and `say`

def console_of(root):
    return masterlog.read(root / "world-state" / "campaigns" / "alpha" / "screen", limit=0)


def test_every_call_that_runs_is_logged_with_its_result_but_never_the_ticket(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        ticket = bridge.issue()
        await ask(sock, ticket, ["bash", "tools/dm-echo.sh", "a b"], stdin=f"leak {ticket}\n")
        await ask(sock, ticket, ["dm-fail.sh"])
        await ask(sock, ticket, ["dm-screen.sh", "turn", "--file", "-"], stdin='{"blocks": ["<p>Дождь</p>"]}')
        await ask(sock, ticket, ["prompt"])
        return ticket

    ticket = with_bridge(root, sock, scenario)
    log = [(e["kind"], e["master"], e["text"], e.get("error")) for e in console_of(root)]
    assert log[0] == ("tool", "hub", f"dm-echo.sh 'a b' <stdin: {len(ticket) + 6} bytes>", None)
    assert log[1][:2] == ("result", "hub") and log[1][2].endswith("leak [скрыто]\n") and log[1][3] is False
    assert log[2:4] == [("tool", "hub", "dm-fail.sh", None), ("result", "hub", "broken\n", True)]
    assert log[4] == ("tool", "hub", 'dm-screen.sh turn --file - <<JSON\n{"blocks": ["<p>Дождь</p>"]}', None)
    assert log[5][:2] == ("result", "hub") and log[5][2].startswith("screen ran turn")
    assert log[6] == ("tool", "hub", "prompt", None) and log[7][:2] == ("result", "hub") and log[7][3] is True
    assert all(e.get("name") == "Bash" for e in console_of(root) if e["kind"] == "tool")
    assert ticket not in (root / "world-state/campaigns/alpha/screen" / masterlog.LOG).read_text(encoding="utf-8")


def test_refused_calls_are_console_notes_and_run_nothing(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        ticket = bridge.issue()
        await ask(sock, ticket, ["dm-screen.sh", "start"])
        await ask(sock, ticket, ["evil.sh"])
        await ask(sock, "wrong", ["dm-roll.sh", "1d20"])

    with_bridge(root, sock, scenario)
    log = [(e["kind"], e["text"]) for e in console_of(root)]
    assert [kind for kind, _ in log] == ["note", "note", "note"]
    assert "dm-screen.sh start" in log[0][1] and "belongs to the driver" in log[0][1]
    assert "evil.sh" in log[1][1] and "unknown tool" in log[1][1]
    assert "dm-roll.sh 1d20" in log[2][1] and "отозван" in log[2][1]


def test_say_writes_the_hub_masters_words_with_the_current_ticket_only(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        ticket = bridge.issue()
        results = [await ask(sock, ticket, ["say", "Бросаю Внимательность за Брама."]),
                   await ask(sock, ticket, ["say"], stdin="Длинная мысль\nв две строки\n"),
                   await ask(sock, ticket, ["say", "a"], stdin="b"),
                   await ask(sock, ticket, ["say", "a", "b"]),
                   await ask(sock, ticket, ["say"]),
                   await ask(sock, ticket, ["say", "я" * 4001]),
                   await ask(sock, ticket, ["say", "я" * 4000]),
                   await ask(sock, None, ["say", "без билета"])]
        await bridge.revoke()
        results.append(await ask(sock, ticket, ["say", "после отзыва"]))
        return results

    results = with_bridge(root, sock, scenario)
    assert [r["code"] for r in results] == [0, 0, 2, 2, 2, 2, 0, 3, 3]
    assert "4000" in results[5]["output"]
    texts = [(e["master"], e["text"]) for e in console_of(root) if e["kind"] == "text"]
    assert texts == [("hub", "Бросаю Внимательность за Брама."), ("hub", "Длинная мысль\nв две строки"), ("hub", "я" * 4000)]


def test_say_does_not_wait_for_a_running_call(root, short_dir, monkeypatch):
    sock, log = short_dir / "hub.sock", short_dir / "calls.log"
    monkeypatch.setenv("LOG_FILE", str(log))

    async def scenario(bridge):
        ticket = bridge.issue()
        running = asyncio.ensure_future(ask(sock, ticket, ["dm-sleep.sh", "1"]))
        while not log.exists():
            await asyncio.sleep(0.01)
        said = await ask(sock, ticket, ["say", "пока ждём картинку"])
        done_before = "end" in log.read_text()
        await running
        return said, done_before

    said, done_before = with_bridge(root, sock, scenario, lock_wait=0.05)
    assert said == {"code": 0, "output": "ok"} and not done_before
    assert [e["kind"] for e in console_of(root)] == ["tool", "text", "result"]


def test_ticket_refused_notes_are_throttled_so_a_flood_cannot_push_history_out(root, short_dir):
    sock = short_dir / "hub.sock"

    async def scenario(bridge):
        bridge.issue()
        for _ in range(20):
            await ask(sock, "forged", ["dm-roll.sh", "1d20"])
        bridge._revoked_noted -= hub_master.REVOKED_NOTE_EVERY + 1   # the window passed
        await ask(sock, None, ["dm-roll.sh", "2d6"])

    with_bridge(root, sock, scenario)
    notes = [e["text"] for e in console_of(root) if e["kind"] == "note"]
    assert len(notes) == 2 and "1d20" in notes[0] and "2d6" in notes[1]


def test_the_bridge_redacts_the_project_env_keys_literally(root, short_dir):
    sock = short_dir / "hub.sock"
    (root / ".env").write_text("ELEVENLABS_API_KEY=plainlowercasekey1\n", encoding="utf-8")

    async def scenario(bridge):
        ticket = bridge.issue()
        await ask(sock, ticket, ["say", "ключ plainlowercasekey1 в тексте"])

    with_bridge(root, sock, scenario)
    assert [e["text"] for e in console_of(root)] == ["ключ [скрыто] в тексте"]
