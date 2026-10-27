"""backend.screen_art: the act art service, against a fake stdio MCP server (never the real hub)."""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from backend import screen_art
from backend.screen_art import ArtError, ArtService

REPO = Path(__file__).resolve().parent.parent
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
PROMPT = "A misty harbour at dawn, fishing boats"

# A stand-in for "uv run ... python -m app.hub_image_mcp": answers initialize and tools/call over stdio.
# FAKE_MODE: ok (writes a PNG), error:<code>, text (plain-text isError), exit (dies before answering).
FAKE_SERVER = r'''
import json, os, sys
from pathlib import Path
mode = os.environ.get("FAKE_MODE", "ok")
out = Path(os.environ["FAKE_OUT"])
log = out / "calls.jsonl"
with log.open("a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "env": {k: os.environ.get(k, "") for k in (
        "MULTICODE_MCP_BASE", "MULTICODE_MCP_TOKEN_FILE", "MULTICODE_HUB_SSH", "MULTICODE_HUB_SSH_KEY",
        "MULTICODE_HUB_BASE_DIR")}}) + "\n")
for line in sys.stdin:
    msg = json.loads(line)
    if mode == "exit":
        sys.exit(3)
    if mode == "hang" and msg.get("method") == "tools/call":
        import subprocess, time
        # A grandchild in the same process group, like the ssh the real server runs.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        (out / "pids.json").write_text(json.dumps([os.getpid(), child.pid]))
        time.sleep(60)
    if msg.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {
            "protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake", "version": "0"}}}), flush=True)
    elif msg.get("method") == "tools/call":
        with log.open("a") as f:
            f.write(json.dumps({"call": msg["params"]}) + "\n")
        print(json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {}}), flush=True)
        if mode == "ok":
            png = out / "hub-1.png"
            png.write_bytes(bytes.fromhex(os.environ["FAKE_PNG"]))
            result = {"ok": True, "paths": [str(png)]}
        elif mode == "text":
            print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {
                "content": [{"type": "text", "text": "validation error"}], "isError": True}}), flush=True)
            continue
        else:
            result = {"ok": False, "paths": [], "error": {"code": mode.split(":", 1)[1], "message": "fake"}}
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {
            "content": [{"type": "text", "text": json.dumps(result)}], "isError": not result["ok"],
            "structuredContent": result}}), flush=True)
'''

# A stand-in for "codex exec --json": prints thread.started and saves a PNG where Codex does.
FAKE_CODEX = r'''
import json, os, sys
from pathlib import Path
home = Path(os.environ["CODEX_HOME"])
home.mkdir(parents=True, exist_ok=True)
(home / "argv.json").write_text(json.dumps(sys.argv[1:]))
tid = "0199-fake-thread"
print(json.dumps({"type": "thread.started", "thread_id": tid}), flush=True)
d = home / "generated_images" / tid
d.mkdir(parents=True, exist_ok=True)
(d / "exec-1.png").write_bytes(bytes.fromhex(os.environ["FAKE_PNG"]))
print(json.dumps({"type": "turn.completed"}), flush=True)
'''


def _script(path, body):
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)
    return str(path)


@pytest.fixture(autouse=True)
def ledger_file(tmp_path, monkeypatch):
    """Every test's ledger is in tmp, never /var/lib/dnd-play-art."""
    path = tmp_path / "state" / "art-spend.json"
    monkeypatch.setattr(screen_art, "DEFAULT_LEDGER", str(path))
    return path


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "repo"
    camp = r / "world-state" / "campaigns" / "harbour"
    camp.mkdir(parents=True)
    (camp / "campaign-overview.json").write_text("{}")
    return r


@pytest.fixture
def hub_env(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setenv("FAKE_OUT", str(out))
    monkeypatch.setenv("FAKE_PNG", PNG.hex())
    monkeypatch.setenv("FAKE_MODE", "ok")
    env = {
        "DM_ART_PYTHON": _script(tmp_path / "fake-python", FAKE_SERVER),
        "DM_ART_ORCHESTRA_DIR": str(tmp_path),
        "DM_ART_HUB_MCP_BASE": "http://127.0.0.1:1",
        "DM_ART_HUB_TOKEN_FILE": "/nonexistent/token",
        "DM_ART_HUB_SSH": "user@hub.invalid",
        "DM_ART_HUB_SSH_KEY": "/nonexistent/key",
        "DM_ART_HUB_BASE_DIR": "/nonexistent/.t3",
        "DM_ART_TIMEOUT": "5",
    }
    return env, out


def _calls(out):
    return [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]


def _ledger(path):
    return json.loads(path.read_text())


def test_success_copies_png_and_counts(root, hub_env, ledger_file, capsys):
    env, out = hub_env
    status, body = ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 200 and body["ok"] is True
    target = root / body["path"]
    assert body["path"].startswith("world-state/campaigns/harbour/screen/art-incoming/")
    assert Path(body["absolute_path"]) == target and target.read_bytes() == PNG
    assert _ledger(ledger_file) == {datetime.now().date().isoformat(): 1}
    assert not (root / "world-state" / "usage").exists()
    calls = _calls(out)
    assert calls[0]["argv"] == ["-m", "app.hub_image_mcp"]          # Orchestra's venv python, never "uv run"
    assert calls[0]["env"]["MULTICODE_HUB_SSH_KEY"] == "/nonexistent/key"
    assert calls[0]["env"]["MULTICODE_MCP_TOKEN_FILE"] == "/nonexistent/token"
    call = calls[1]["call"]
    assert call["name"] == "hub_generate_image"
    args = call["arguments"]
    assert args["count"] == 1 and args["size"] == "16:9" and args["timeout_seconds"] == 5
    assert PROMPT in args["prompt"] and "16:9" in args["prompt"] and "no text" in args["prompt"]
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["campaign"] == "harbour" and line["outcome"] == "ok" and line["code"] == ""


def test_two_successes_get_distinct_files(root, hub_env, ledger_file):
    env, _ = hub_env
    svc = ArtService(root, env)
    a = svc.generate({"campaign": "harbour", "prompt": PROMPT})[1]["path"]
    b = svc.generate({"campaign": "harbour", "prompt": PROMPT})[1]["path"]
    assert a != b and _ledger(ledger_file)[datetime.now().date().isoformat()] == 2


@pytest.mark.parametrize("code", ["provider_limit", "hub_unavailable", "no_image", "timeout"])
def test_hub_error_passes_through(root, hub_env, monkeypatch, code):
    env, _ = hub_env
    monkeypatch.setenv("FAKE_MODE", f"error:{code}")
    status, body = ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 502 and body == {"ok": False, "code": code, "error": "fake"}
    assert not (root / "world-state" / "campaigns" / "harbour" / "screen" / "art-incoming").exists()


def test_plain_text_tool_error_and_early_exit(root, hub_env, monkeypatch):
    env, _ = hub_env
    monkeypatch.setenv("FAKE_MODE", "text")
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "invalid_request"
    monkeypatch.setenv("FAKE_MODE", "exit")
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "hub_unavailable"


def _dead(pid, wait=5.0):
    """True once pid is gone (or a zombie waiting for init to reap it)."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:
            if Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                return True
        except (OSError, IndexError):
            return True
        time.sleep(0.05)
    return False


def test_overall_timeout_kills_the_server(root, hub_env, monkeypatch):
    env, out = hub_env
    monkeypatch.setenv("FAKE_MODE", "hang")
    monkeypatch.setattr(screen_art, "KILL_GRACE", 0)
    env["DM_ART_TIMEOUT"] = "1"
    started = time.monotonic()
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "timeout"
    assert time.monotonic() - started < 10
    server_pid, grandchild_pid = json.loads((out / "pids.json").read_text())
    assert _dead(server_pid) and _dead(grandchild_pid)   # the whole process group, not just the leader


def test_kill_grace_covers_the_tool_cleanup():
    assert screen_art.KILL_GRACE == 100
    assert screen_art.DEFAULT_TIMEOUT + screen_art.KILL_GRACE <= screen_art.REQUEST_BUDGET
    assert screen_art.REQUEST_BUDGET < screen_art.CLIENT_READ_TIMEOUT


def test_not_configured(root, hub_env):
    env, _ = hub_env
    del env["DM_ART_HUB_SSH_KEY"]
    status, body = ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 502 and body["code"] == "not_configured" and "DM_ART_HUB_SSH_KEY" in body["error"]
    env["DM_ART_HUB_SSH_KEY"] = "/k"
    env["DM_ART_PYTHON"] = "/nonexistent/python"
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "not_configured"


def test_daily_limit(root, hub_env, ledger_file):
    env, _ = hub_env
    env["DM_ART_DAILY_LIMIT"] = "2"
    ledger = ledger_file
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"2000-01-01": 99, datetime.now().date().isoformat(): 1}))
    svc = ArtService(root, env)
    assert svc.generate({"campaign": "harbour", "prompt": PROMPT})[0] == 200
    status, body = svc.generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 429 and body["code"] == "daily_limit"
    assert _ledger(ledger)[datetime.now().date().isoformat()] == 2 and _ledger(ledger)["2000-01-01"] == 99
    assert [p.name for p in ledger.parent.iterdir()] == ["art-spend.json"]   # no temp file left


def test_busy_refuses_second_request(root, ledger_file):
    started, release = threading.Event(), threading.Event()

    def slow_hub(prompt, env, timeout):
        started.set()
        release.wait(5)
        return {"ok": False, "paths": [], "error": {"code": "no_image", "message": "x"}}

    svc = ArtService(root, {}, hub=slow_hub)
    first = threading.Thread(target=svc.generate, args=({"campaign": "harbour", "prompt": PROMPT},))
    first.start()
    assert started.wait(5)
    status, body = svc.generate({"campaign": "harbour", "prompt": PROMPT})
    release.set()
    first.join(5)
    assert status == 409 and body["code"] == "busy"
    assert _ledger(ledger_file)[datetime.now().date().isoformat()] == 1   # the refused request is not counted


@pytest.mark.parametrize("name", ["../x", "/etc", "", "  ", ".hidden", "a/b", "a\\b", None, 5, "missing"])
def test_bad_campaign(root, name):
    status, body = ArtService(root, {}, hub=None).generate({"campaign": name, "prompt": PROMPT})
    assert status == 400 and body["code"] == "bad_campaign"


@pytest.mark.parametrize("prompt,ok", [("x" * 9, False), ("x" * 10, True), ("x" * 4000, True),
                                       ("x" * 4001, False), ("   short   ", False), (None, False)])
def test_prompt_bounds(root, prompt, ok):
    svc = ArtService(root, {}, hub=lambda p, e, t: {"ok": False, "paths": [], "error": {"code": "no_image"}})
    status, body = svc.generate({"campaign": "harbour", "prompt": prompt})
    assert (body["code"] != "bad_prompt") is ok
    if not ok:
        assert status == 400


def test_non_png_is_rejected(root, tmp_path):
    fake = tmp_path / "x.png"
    fake.write_bytes(b"GIF89a....")
    svc = ArtService(root, {}, hub=lambda p, e, t: {"ok": True, "paths": [str(fake)]})
    assert svc.generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "invalid_output"


def test_cleanup_failed_with_picture_is_success(root, tmp_path):
    png = tmp_path / "p.png"
    png.write_bytes(PNG)
    svc = ArtService(root, {}, hub=lambda p, e, t: {"ok": False, "paths": [str(png)],
                                                    "error": {"code": "cleanup_failed", "message": "m"}})
    assert svc.generate({"campaign": "harbour", "prompt": PROMPT})[0] == 200


def test_codex_fallback_only_when_enabled(root, hub_env, tmp_path, monkeypatch):
    env, _ = hub_env
    monkeypatch.setenv("FAKE_MODE", "error:provider_limit")
    env["DM_ART_CODEX"] = _script(tmp_path / "fake-codex", FAKE_CODEX)
    env["CODEX_HOME"] = str(tmp_path / "codex-home")
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "provider_limit"
    env["DM_ART_CODEX_FALLBACK"] = "1"
    status, body = ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 200 and (root / body["path"]).read_bytes() == PNG
    argv = json.loads((tmp_path / "codex-home" / "argv.json").read_text())
    assert argv[0] == "exec" and "--json" in argv and "--ignore-user-config" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    disabled = {argv[i + 1] for i, a in enumerate(argv) if a == "--disable"}
    assert {"shell_tool", "unified_exec", "apps", "plugins"} <= disabled
    # A prompt-shaped failure is not retried on Codex.
    monkeypatch.setenv("FAKE_MODE", "error:no_image")
    assert ArtService(root, env).generate({"campaign": "harbour", "prompt": PROMPT})[1]["code"] == "no_image"


def test_http_and_client_exit_codes(root, tmp_path, capsys):
    png = tmp_path / "p.png"
    png.write_bytes(PNG)
    svc = ArtService(root, {}, hub=lambda p, e, t: {"ok": True, "paths": [str(png)]})
    server = screen_art.ThreadingHTTPServer(("127.0.0.1", 0), screen_art.make_handler(svc))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        code, line = screen_art.request("harbour", PROMPT, port, timeout=10)
        assert code == 0 and line.startswith("world-state/campaigns/harbour/screen/art-incoming/")
        code, line = screen_art.request("../x", PROMPT, port, timeout=10)
        assert code == 1 and line.startswith("art failed (bad_campaign)")
        assert screen_art.main(["request", "--campaign", "harbour", "--prompt", "short", "--port", str(port)]) == 1
        assert "bad_prompt" in capsys.readouterr().out
    finally:
        server.shutdown()
        server.server_close()
    code, line = screen_art.request("harbour", PROMPT, port, timeout=2)
    assert code == 1 and "unavailable" in line


def test_client_needs_a_campaign(monkeypatch, capsys):
    monkeypatch.delenv("DM_ACTIVE_CAMPAIGN", raising=False)
    assert screen_art.main(["request", "--prompt", PROMPT, "--port", "1"]) == 1
    assert "no campaign" in capsys.readouterr().out


def test_dm_art_wrapper_runs_client():
    env = {k: v for k, v in os.environ.items() if not k.startswith("DM_")}
    env.update({"DM_ART_PORT": "1", "DM_ACTIVE_CAMPAIGN": "harbour"})
    run = subprocess.run(["bash", str(REPO / "tools" / "dm-art.sh"), "--prompt", PROMPT],
                         capture_output=True, text=True, env=env, timeout=120)
    assert run.returncode == 1 and "art service unavailable on 127.0.0.1:1" in run.stdout


# ---------------------------------------------------------------- review findings (security rework)

def test_unexpected_exception_is_internal(root, capsys):
    def broken_hub(prompt, env, timeout):
        raise RuntimeError("boom")

    status, body = ArtService(root, {}, hub=broken_hub).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 500 and body["ok"] is False and body["code"] == "internal" and "boom" not in body["error"]
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["outcome"] == "error" and line["code"] == "internal"


def test_ledger_write_failure_is_internal_and_leaves_no_temp(root, ledger_file, monkeypatch, capsys):
    def failing_replace(src, dst):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(screen_art.os, "replace", failing_replace)
    status, body = ArtService(root, {}, hub=None).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 500 and body["code"] == "internal"
    assert list(ledger_file.parent.iterdir()) == []
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["code"] == "internal"


def test_ledger_path_from_env(root, tmp_path, ledger_file):
    png = tmp_path / "p.png"
    png.write_bytes(PNG)
    custom = tmp_path / "elsewhere" / "spend.json"
    svc = ArtService(root, {"DM_ART_LEDGER": str(custom)}, hub=lambda p, e, t: {"ok": True, "paths": [str(png)]})
    assert svc.ledger_path == custom
    assert svc.generate({"campaign": "harbour", "prompt": PROMPT})[0] == 200
    assert _ledger(custom) == {datetime.now().date().isoformat(): 1} and not ledger_file.exists()
    assert ArtService(root, {}).ledger_path == Path(screen_art.DEFAULT_LEDGER)


def test_default_ledger_is_outside_the_repository():
    source = Path(screen_art.__file__).read_text()
    assert 'DEFAULT_LEDGER = "/var/lib/dnd-play-art/art-spend.json"' in source


def _png_hub(tmp_path):
    png = tmp_path / "p.png"
    png.write_bytes(PNG)
    return lambda p, e, t: {"ok": True, "paths": [str(png)]}


def test_symlinked_art_incoming_is_refused(root, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    screen = root / "world-state" / "campaigns" / "harbour" / "screen"
    screen.mkdir()
    (screen / "art-incoming").symlink_to(elsewhere)
    status, body = ArtService(root, {}, hub=_png_hub(tmp_path)).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 502 and body["code"] == "bad_output"
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize("link", ["world-state", "campaigns", "campaign", "screen"])
def test_symlink_anywhere_on_the_path_is_refused(root, tmp_path, link):
    elsewhere = tmp_path / "elsewhere"
    camp = root / "world-state" / "campaigns" / "harbour"
    (camp / "screen" / "art-incoming").mkdir(parents=True)
    moved = {"world-state": root / "world-state", "campaigns": root / "world-state" / "campaigns",
             "campaign": camp, "screen": camp / "screen"}[link]
    moved.rename(elsewhere)
    moved.symlink_to(elsewhere)   # the campaign still validates through the link; the write must not follow it
    status, body = ArtService(root, {}, hub=_png_hub(tmp_path)).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 502 and body["code"] == "bad_output"
    assert not [p for p in elsewhere.rglob("*.png")]


def test_dangling_stamp_link_is_not_followed(root, tmp_path, monkeypatch):
    monkeypatch.setattr(screen_art, "_stamp", lambda: "20261027-120000")
    incoming = root / "world-state" / "campaigns" / "harbour" / "screen" / "art-incoming"
    incoming.mkdir(parents=True)
    target = tmp_path / "planted.png"
    (incoming / "20261027-120000.png").symlink_to(target)
    status, body = ArtService(root, {}, hub=_png_hub(tmp_path)).generate({"campaign": "harbour", "prompt": PROMPT})
    assert status == 200 and body["path"].endswith("art-incoming/20261027-120000-2.png")
    assert not target.exists() and (incoming / "20261027-120000-2.png").read_bytes() == PNG
    assert not (incoming / "20261027-120000-2.png").is_symlink()
    assert (os.stat(incoming / "20261027-120000-2.png").st_mode & 0o777) == 0o644 & ~_umask()


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


FAKE_CODEX_NO_THREAD = r'''
import json, os
from pathlib import Path
home = Path(os.environ["CODEX_HOME"])
# No thread.started event, yet some PNG appears in generated_images (another run's, say).
d = home / "generated_images" / "other-thread"
d.mkdir(parents=True, exist_ok=True)
(d / "exec-1.png").write_bytes(bytes.fromhex(os.environ["FAKE_PNG"]))
print(json.dumps({"type": "turn.completed"}), flush=True)
'''


def test_codex_without_thread_id_is_no_image(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PNG", PNG.hex())
    env = {"DM_ART_CODEX": _script(tmp_path / "fake-codex", FAKE_CODEX_NO_THREAD),
           "CODEX_HOME": str(tmp_path / "codex-home")}
    with pytest.raises(ArtError) as exc:
        screen_art.call_codex(PROMPT, env, 30)
    assert exc.value.code == "no_image"


@pytest.mark.parametrize("line,expected", [
    ('{"type": "thread.started", "thread_id": "abc-1"}', "abc-1"),
    ('{"type": "thread.started", "thread_id": "../x"}', ""),
    ('{"type": "thread.started", "thread_id": ".."}', ""),
    ('{"type": "thread.started"}', ""),
    ("not json", ""),
])
def test_thread_id_parsing(line, expected):
    assert screen_art._thread_id(line) == expected


def test_budget_split(root, monkeypatch):
    seen = {}

    def hub(prompt, env, timeout):
        seen["hub"] = timeout
        return {"ok": False, "paths": [], "error": {"code": "provider_limit", "message": "m"}}

    def codex(prompt, env, timeout):
        seen["codex"] = timeout
        raise ArtError("no_image", "x")

    env = {"DM_ART_TIMEOUT": "300", "DM_ART_CODEX_FALLBACK": "1"}
    # A fast hub failure: the hub was offered min(DM_ART_TIMEOUT, budget - KILL_GRACE), Codex the remainder.
    ArtService(root, env, hub=hub, codex=codex, budget=460).generate({"campaign": "harbour", "prompt": PROMPT})
    assert seen["hub"] == 300 and 455 <= seen["codex"] <= 460
    # A small budget caps the hub's timeout_seconds so the hub call with its kill grace still fits.
    seen.clear()
    ArtService(root, env, hub=hub, codex=codex, budget=250).generate({"campaign": "harbour", "prompt": PROMPT})
    assert seen["hub"] in (149, 150) and 245 <= seen["codex"] <= 250


def test_no_fallback_when_the_remainder_is_small(root):
    called = []

    def slow_hub(prompt, env, timeout):
        time.sleep(0.2)
        return {"ok": False, "paths": [], "error": {"code": "timeout", "message": "m"}}

    svc = ArtService(root, {"DM_ART_CODEX_FALLBACK": "1"}, hub=slow_hub,
                     codex=lambda *a: called.append(a), budget=screen_art.MIN_FALLBACK_SECONDS)
    status, body = svc.generate({"campaign": "harbour", "prompt": PROMPT})
    assert body["code"] == "timeout" and "no time left" in body["error"] and called == []


@pytest.mark.parametrize("name", ["harbour", " harbour ", "", "  ", None, 0, 5, ".hidden", "a..b", "..", "a/b",
                                  "a\\b", "/etc", "missing", "Harbour", "harbour/", "x.y"])
def test_inlined_campaign_rule_matches_lib(root, name):
    from lib.screen.online import CampaignError as LibError, check_campaign as lib_check

    (root / "world-state" / "campaigns" / "x.y").mkdir()
    (root / "world-state" / "campaigns" / "x.y" / "campaign-overview.json").write_text("{}")

    def outcome(check, error):
        try:
            return "ok", check(name, root)
        except error as exc:
            return "error", str(exc)

    assert outcome(screen_art.check_campaign, screen_art.CampaignError) == outcome(lib_check, LibError)


def test_module_is_stdlib_only():
    """The service runs as /usr/bin/python3 -I from a root-owned copy: no repository imports may creep in."""
    source = Path(screen_art.__file__).read_text()
    assert "from lib" not in source and "import lib" not in source and "from backend" not in source
    run = subprocess.run([sys.executable, "-I", "-c",
                          "import runpy, sys; runpy.run_path(sys.argv[1], run_name='not_main'); print('ok')",
                          screen_art.__file__], capture_output=True, text=True, cwd="/", timeout=60)
    assert run.returncode == 0 and run.stdout.strip() == "ok", run.stderr


def test_serve_needs_dm_art_root(monkeypatch, capsys):
    monkeypatch.delenv("DM_ART_ROOT", raising=False)
    assert screen_art.main(["serve", "--port", "1"]) == 2
    monkeypatch.setenv("DM_ART_ROOT", "relative/path")
    assert screen_art.main(["serve", "--port", "1"]) == 2
    assert "DM_ART_ROOT" in capsys.readouterr().err


def test_unit_runs_the_root_owned_copy():
    unit = (REPO / "ops" / "play" / "dnd-play-art.service").read_text()
    directives = dict(line.split("=", 1) for line in unit.splitlines() if "=" in line and not line.startswith("#")
                      and not line.startswith("Environment"))
    assert directives["ExecStart"] == "/usr/bin/python3 -I /opt/dnd-play-art/screen_art.py serve"
    assert directives["WorkingDirectory"] == "/opt/dnd-play-art"
    assert directives["StateDirectory"] == "dnd-play-art"
    assert "Environment=DM_ART_ROOT=/home/kesha/projects/dnd-game-master" in unit
    assert "Environment=DM_ART_LEDGER=/var/lib/dnd-play-art/art-spend.json" in unit
    assert "dnd-game-master/.venv" not in "".join(l for l in unit.splitlines() if not l.startswith("#"))
    assert "Environment=DM_ART_PYTHON=/home/kesha/orchestra/.venv/bin/python" in unit and "uv" not in unit.split("ExecStart=")[1].split("\n")[0]
    # the repository root: the master can swap any directory below it for a symlink systemd would follow at a start
    assert directives["ReadWritePaths"].split()[0] == "/home/kesha/projects/dnd-game-master"
    assert "-/home/kesha/.cache" not in directives["ReadWritePaths"]
    assert "dnd-play.service" not in unit


def test_a_stalled_client_neither_blocks_nor_starves_the_service(root, hub_env, ledger_file, monkeypatch):
    import socket
    hub_env, _ = hub_env
    monkeypatch.setattr(screen_art, "REQUEST_READ_TIMEOUT", 1)
    monkeypatch.setattr(screen_art, "MAX_CONNECTIONS", 2)
    server = screen_art._Server(("127.0.0.1", 0), screen_art.make_handler(ArtService(root, hub_env)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        stalled = socket.create_connection(("127.0.0.1", port))
        stalled.sendall(b"POST /generate HTTP/1.1\r\nContent-Length: 60000\r\n\r\n{")   # and then nothing
        flood = [socket.create_connection(("127.0.0.1", port)) for _ in range(5)]          # over the cap: closed
        time.sleep(1.5)                                                                     # the stalled read times out
        code, line = screen_art.request("harbour", PROMPT, port, timeout=20)
        assert code == 0 and line.endswith(".png")
        for sock in [stalled, *flood]:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()


def test_a_failed_write_leaves_no_broken_picture(root, monkeypatch):
    real_write = os.write

    def full_disk(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(screen_art.os, "write", full_disk)
    with pytest.raises(screen_art.ArtError) as err:
        screen_art.write_incoming(root, "harbour", PNG)
    monkeypatch.setattr(screen_art.os, "write", real_write)
    assert err.value.code == "bad_output"
    incoming = root / "world-state" / "campaigns" / "harbour" / "screen" / "art-incoming"
    assert list(incoming.iterdir()) == []


def test_the_hub_server_runs_without_uv(hub_env):
    hub_env, _ = hub_env
    argv, child = screen_art.hub_command(hub_env)
    assert argv == [hub_env["DM_ART_PYTHON"], "-m", "app.hub_image_mcp"] and "UV_FROZEN" not in child
