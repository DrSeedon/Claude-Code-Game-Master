"""Act art for the online screen table, drawn through the MultiCode hub (dnd-play-art.service).

The online masters (dnd-play@.service: dnd-play@play, dnd-play@demo) are reachable by guests through prompts, so
they never hold the hub ssh key or the MultiCode token. This separate service holds them: a master only sends a
prompt to POST http://127.0.0.1:$DM_ART_PORT/generate {campaign, prompt} and gets back a PNG path inside the
campaign.

  serve     the HTTP service (one generation at a time, a daily cap in the ledger $DM_ART_LEDGER)
  request   the client a master runs (bash tools/dm-art.sh --prompt "..."): prints the PNG path or a reason

A master can write the whole repository, so the service never runs or reads repository code or state it trusts:
it runs as "/usr/bin/python3 -I /opt/dnd-play-art/screen_art.py serve" from a root-owned copy of this file, which
is therefore stdlib-only (no lib/ or backend/ imports; the campaign-name rule of lib/screen/online.py is inlined
and a test keeps the two in agreement). The repository it writes into is $DM_ART_ROOT, its ledger lives outside
the repository, and the picture is written through directory fds that refuse symlinks on every path component.

The hub call speaks MCP to Orchestra's stdio server app.hub_image_mcp (tool hub_generate_image), the same
interface the Kesha bot uses. With DM_ART_CODEX_FALLBACK=1 a hub outage (provider_limit, hub_unavailable,
timeout, not_configured) falls back to a local "codex exec" with only its built-in image generation tool.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 18117
DEFAULT_DAILY_LIMIT = 10
DEFAULT_TIMEOUT = 300
DEFAULT_LEDGER = "/var/lib/dnd-play-art/art-spend.json"
# The MCP tool bounds its own work by timeout_seconds plus up to 60 s of cleanup, and our clock starts before uv
# starts the server; past timeout_seconds + KILL_GRACE the server's process group is killed.
KILL_GRACE = 100
CLIENT_READ_TIMEOUT = 480
MAX_CONNECTIONS, REQUEST_READ_TIMEOUT = 8, 15
# One wall-clock budget per request, with room for the reply before the client gives up reading.
REQUEST_BUDGET = CLIENT_READ_TIMEOUT - 20
# The Codex fallback only runs with at least this much of the budget left.
MIN_FALLBACK_SECONDS = 90
PROMPT_MIN, PROMPT_MAX = 10, 4000
MAX_IMAGE_BYTES = 32 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# Hub outcomes that say nothing about the prompt itself, so the local Codex may try instead.
FALLBACK_CODES = frozenset({"provider_limit", "hub_unavailable", "timeout", "not_configured"})
HTTP_STATUS = {"bad_request": 400, "bad_campaign": 400, "bad_prompt": 400, "busy": 409, "daily_limit": 429,
               "internal": 500}

STYLE = ("Wide cinematic 16:9 landscape composition for a full-screen stage backdrop. The picture must contain "
         "no text of any kind: no letters, words, captions, labels, signs with writing, logos or watermark.")


class ArtError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class CampaignError(ValueError):
    """A campaign name that is not a valid campaign of the repository."""


def check_campaign(name, root):
    """The campaign name when world-state/campaigns/<name>/campaign-overview.json exists, else CampaignError.
    The same rule as lib.screen.online.check_campaign (inlined: this module is stdlib-only; a test compares them)."""
    name = str(name or "").strip()
    if not name or name.startswith(".") or ".." in name or "/" in name or "\\" in name:
        raise CampaignError(f"invalid campaign name {name!r}")
    if not (Path(root) / "world-state" / "campaigns" / name / "campaign-overview.json").is_file():
        raise CampaignError(f"no campaign {name!r} (world-state/campaigns/{name}/campaign-overview.json is missing)")
    return name


def wrap_prompt(prompt):
    return f"{STYLE}\n\nScene: {prompt.strip()}"


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(env, name, default):
    try:
        return int(str(env.get(name, "")).strip() or default)
    except ValueError:
        return default


# ---------------------------------------------------------------- hub (stdio MCP)

def hub_command(env):
    """argv and child env for app.hub_image_mcp, or ArtError(not_configured) naming the missing variables."""
    names = ("DM_ART_ORCHESTRA_DIR", "DM_ART_HUB_MCP_BASE", "DM_ART_HUB_TOKEN_FILE", "DM_ART_HUB_SSH",
             "DM_ART_HUB_SSH_KEY", "DM_ART_HUB_BASE_DIR", "DM_ART_PYTHON")
    values = {name: str(env.get(name, "")).strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ArtError("not_configured", "missing " + ", ".join(missing))
    # Orchestra's own venv interpreter, never "uv run": uv would reinstall from ~/.cache/uv, which other kesha
    # processes can write, and the server holds the hub key and token.
    argv = [values["DM_ART_PYTHON"], "-m", "app.hub_image_mcp"]
    # The unit's own environment (no secrets in it) minus our variables, plus the server's MULTICODE_* settings.
    child = {key: value for key, value in os.environ.items() if not key.startswith("DM_ART_")}
    child.update({
        "MULTICODE_MCP_BASE": values["DM_ART_HUB_MCP_BASE"],
        "MULTICODE_MCP_TOKEN_FILE": values["DM_ART_HUB_TOKEN_FILE"],
        "MULTICODE_HUB_SSH": values["DM_ART_HUB_SSH"],
        "MULTICODE_HUB_SSH_KEY": values["DM_ART_HUB_SSH_KEY"],
        "MULTICODE_HUB_BASE_DIR": values["DM_ART_HUB_BASE_DIR"],
        "PYTHONUNBUFFERED": "1",
    })
    return argv, child


def _tool_result(result):
    """The hub_generate_image dict from a tools/call result (structuredContent or its JSON text)."""
    if isinstance(result.get("structuredContent"), dict) and "ok" in result["structuredContent"]:
        return result["structuredContent"]
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                parsed = json.loads(item.get("text") or "")
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and "ok" in parsed:
                return parsed
            if result.get("isError"):   # an argument validation error has plain text
                return {"ok": False, "paths": [],
                        "error": {"code": "invalid_request", "message": str(item.get("text"))[:200]}}
    return {"ok": False, "paths": [], "error": {"code": "invalid_output", "message": "unexpected MCP tool result"}}


def call_hub(prompt, env, timeout_seconds):
    """Run one hub_generate_image call over newline-delimited JSON-RPC on the server's stdio. The whole call,
    from before uv starts, is bounded by timeout_seconds + KILL_GRACE; past that the process group is killed."""
    deadline = time.monotonic() + timeout_seconds + KILL_GRACE
    argv, child_env = hub_command(env)
    # stderr carries the tool's progress lines (workspace ids, hub paths): not logged, not needed.
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=child_env, cwd=env.get("DM_ART_ORCHESTRA_DIR"), text=True, bufsize=1,
                                start_new_session=True)
    except OSError as exc:
        raise ArtError("not_configured", f"cannot start the hub image server ({type(exc).__name__})")
    lines = queue.Queue()

    def pump():
        try:
            for line in proc.stdout:
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def wait_for(request_id):
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise ArtError("timeout", "hub image server did not answer in time")
            try:
                line = lines.get(timeout=left)
            except queue.Empty:
                continue
            if line is None:
                raise ArtError("hub_unavailable", "hub image server exited early")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise ArtError("hub_unavailable", "hub image server refused the request")
                return message.get("result") or {}

    timed_out = False
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "dnd-screen-art", "version": "1"}}})
        wait_for(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "hub_generate_image",
                         "arguments": {"prompt": prompt, "count": 1, "size": "16:9",
                                       "timeout_seconds": timeout_seconds}}})
        return _tool_result(wait_for(2))
    except ArtError as exc:
        timed_out = exc.code == "timeout"
        raise
    except (BrokenPipeError, OSError) as exc:
        raise ArtError("hub_unavailable", f"hub image server pipe failed ({type(exc).__name__})")
    finally:
        _stop(proc, grace=0 if timed_out else 5)


def _kill_group(proc):
    """SIGKILL the child's whole process group (uv, the server, its ssh), before the leader is reaped."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


def _stop(proc, grace=5):
    """Close the server's stdin and give it `grace` seconds to exit; then kill its process group."""
    try:
        proc.stdin.close()
    except OSError:
        pass
    if grace > 0:
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
    _kill_group(proc)   # also after a clean exit: the server's ssh must not outlive the call with the key
    proc.wait()


# ---------------------------------------------------------------- local Codex fallback

def codex_command(env, workdir, prompt):
    codex = str(env.get("DM_ART_CODEX", "")).strip() or "/usr/bin/codex"
    # Only the built-in image tool: no shell, no apps, plugins, browsers, sub-agents or user MCP servers, so a
    # prompt from a guest cannot make it read files (the hub key is visible to this unit).
    disabled = ("shell_tool", "unified_exec", "apps", "plugins", "browser_use", "browser_use_external",
                "in_app_browser", "computer_use", "multi_agent", "hooks", "code_mode_host")
    argv = [codex, "exec", "--json", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "-C", str(workdir), "--enable", "image_generation"]
    for feature in disabled:
        argv += ["--disable", feature]
    instruction = ("Generate exactly one image with your built-in image generation tool and nothing else. "
                   "Do not run commands, read files or browse. After the image is generated, reply DONE.\n\n"
                   f"Image prompt:\n{prompt}")
    return argv + [instruction]


def _thread_id(stdout):
    """The thread id of a "codex exec --json" run (its thread.started event), or "" when it has none."""
    thread_id = ""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "").strip()
    if thread_id in (".", "..") or "/" in thread_id or "\\" in thread_id or "\0" in thread_id:
        return ""
    return thread_id


def call_codex(prompt, env, timeout_seconds):
    """One "codex exec" run, killed (its whole process group) after timeout_seconds of wall clock. The picture
    is taken only from generated_images/<thread id>/ of this run: without a thread id there is no image."""
    codex_home = Path(str(env.get("CODEX_HOME", "")).strip() or Path.home() / ".codex")
    with tempfile.TemporaryDirectory(prefix="dnd-art-codex-") as workdir:
        argv = codex_command(env, workdir, prompt)
        child = {key: value for key, value in os.environ.items() if not key.startswith("DM_ART_")}
        child["CODEX_HOME"] = str(codex_home)
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, env=child, cwd=workdir,
                                    start_new_session=True)
        except OSError as exc:
            raise ArtError("not_configured", f"cannot start codex ({type(exc).__name__})")
        try:
            stdout, _ = proc.communicate(timeout=max(1, timeout_seconds))
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.communicate()
            raise ArtError("timeout", "codex image generation exceeded the timeout")
        except BaseException:
            _kill_group(proc)
            proc.wait()
            raise
    thread_id = _thread_id(stdout or "")
    candidates = sorted((codex_home / "generated_images" / thread_id).glob("*.png")) if thread_id else []
    if not candidates:
        code = "no_image" if proc.returncode == 0 or not thread_id else "codex_failed"
        raise ArtError(code, f"codex produced no image (exit {proc.returncode}, "
                             f"{'thread id' if thread_id else 'no thread id'})")
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return {"ok": True, "paths": [str(newest)]}


# ---------------------------------------------------------------- symlink-safe output

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _open_dir(name, dir_fd, create=False):
    """An fd of the real directory `name` inside dir_fd (never through a symlink); mkdir it first if asked."""
    if create:
        try:
            os.mkdir(name, 0o755, dir_fd=dir_fd)   # mkdir never follows a symlink: an existing link is EEXIST
        except FileExistsError:
            pass
    try:
        return os.open(name, _DIR_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise ArtError("bad_output", f"{name} is not a plain directory ({type(exc).__name__})")


def _stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_incoming(root, campaign, data):
    """Write data to world-state/campaigns/<campaign>/screen/art-incoming/<stamp>[-n].png under root, walking
    every component with O_NOFOLLOW dir fds and creating the file with O_EXCL|O_NOFOLLOW, so a symlink planted
    anywhere on the path (by a master that can write the repository) cannot redirect the write. The relative
    path of the new file, or ArtError(bad_output)."""
    fds = []
    try:
        fds.append(os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)))
        for name, create in (("world-state", False), ("campaigns", False), (campaign, False),
                             ("screen", True), ("art-incoming", True)):
            fds.append(_open_dir(name, fds[-1], create))
        stamp, n = _stamp(), 1
        while True:
            filename = f"{stamp}.png" if n == 1 else f"{stamp}-{n}.png"
            try:
                fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                             | getattr(os, "O_CLOEXEC", 0), 0o644, dir_fd=fds[-1])
                break
            except FileExistsError:   # also a planted (dangling) symlink of that name: O_EXCL never follows it
                n += 1
                if n > 1000:
                    raise ArtError("bad_output", "art-incoming has no free file name")
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
        except OSError:
            os.close(fd)
            fd = None
            os.unlink(filename, dir_fd=fds[-1])   # a full disk must not leave a broken picture in the campaign
            raise
        finally:
            if fd is not None:
                os.close(fd)
        return "/".join(("world-state", "campaigns", campaign, "screen", "art-incoming", filename))
    except ArtError:
        raise
    except OSError as exc:
        raise ArtError("bad_output", f"cannot write the picture into the campaign ({type(exc).__name__})")
    finally:
        for fd in fds:
            os.close(fd)


# ---------------------------------------------------------------- the service

class ArtService:
    def __init__(self, root, env=None, hub=call_hub, codex=call_codex, budget=None):
        self.root = Path(root)
        self.env = dict(os.environ if env is None else env)
        self.hub, self.codex = hub, codex
        self.budget = REQUEST_BUDGET if budget is None else budget
        self.lock = threading.Lock()          # one generation at a time
        self.ledger_lock = threading.Lock()

    @property
    def ledger_path(self):
        return Path(str(self.env.get("DM_ART_LEDGER", "")).strip() or DEFAULT_LEDGER)

    def _ledger(self):
        try:
            data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _count(self):
        """Reserve one of today's generations, or ArtError(daily_limit). Attempts count: a failed hub run
        may have spent the subscription as well."""
        limit = _int_env(self.env, "DM_ART_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)
        today = datetime.now().date().isoformat()
        with self.ledger_lock:
            data = self._ledger()
            used = data.get(today, 0) if isinstance(data.get(today), int) else 0
            if used >= limit:
                raise ArtError("daily_limit", f"daily art limit reached ({used}/{limit})")
            data[today] = used + 1
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.ledger_path.parent, prefix=".art-spend.")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    json.dump(data, out, indent=2, sort_keys=True)
                os.replace(tmp, self.ledger_path)
            finally:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ArtError("bad_request", "body must be a JSON object")
        try:
            campaign = check_campaign(payload.get("campaign"), self.root)
        except CampaignError as exc:
            raise ArtError("bad_campaign", str(exc))
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not PROMPT_MIN <= len(prompt.strip()) <= PROMPT_MAX:
            raise ArtError("bad_prompt", f"prompt must contain {PROMPT_MIN}..{PROMPT_MAX} characters")
        return campaign, prompt.strip()

    def generate(self, payload):
        """(HTTP status, response dict) for one /generate request; logs one line."""
        started = time.monotonic()
        campaign = payload.get("campaign") if isinstance(payload, dict) else None
        code = "internal"   # until the request has an outcome: an unexpected exception is never logged "ok"
        try:
            campaign, prompt = self.validate(payload)
            if not self.lock.acquire(blocking=False):
                raise ArtError("busy", "another picture is being drawn; try again in a few minutes")
            try:
                self._count()
                source = self._draw(wrap_prompt(prompt), started + self.budget)
                result = self._store(campaign, source)
            finally:
                self.lock.release()
            code = ""
            return 200, result
        except ArtError as exc:
            code = exc.code
            return HTTP_STATUS.get(exc.code, 502), {"ok": False, "code": exc.code, "error": str(exc)}
        except Exception as exc:
            code = "internal"
            return 500, {"ok": False, "code": "internal", "error": f"internal error ({type(exc).__name__})"}
        finally:
            text = payload.get("prompt") if isinstance(payload, dict) and isinstance(payload.get("prompt"), str) else ""
            print(json.dumps({"campaign": str(campaign)[:80], "outcome": "error" if code else "ok",
                              "code": code, "seconds": round(time.monotonic() - started, 1),
                              "prompt": " ".join(text.split())[:120]}, ensure_ascii=False), flush=True)

    def split_budget(self, deadline):
        """The hub's timeout_seconds: min(DM_ART_TIMEOUT, what is left of the request budget minus KILL_GRACE),
        so the hub call with its kill grace fits the budget; the Codex fallback gets only what remains after it."""
        left = deadline - time.monotonic()
        wanted = max(1, min(1800, _int_env(self.env, "DM_ART_TIMEOUT", DEFAULT_TIMEOUT)))
        return max(1, min(wanted, int(left - KILL_GRACE)))

    def _draw(self, prompt, deadline):
        timeout = self.split_budget(deadline)
        try:
            result = self.hub(prompt, self.env, timeout)
        except ArtError as exc:
            result = {"ok": False, "paths": [], "error": {"code": exc.code, "message": str(exc)}}
        if not isinstance(result, dict):
            result = {"ok": False, "paths": [], "error": {"code": "invalid_output", "message": "bad hub result"}}
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        paths = [p for p in result.get("paths") or [] if isinstance(p, str)]
        # cleanup_failed after a fetched picture: the picture is good, the hub leftovers are Orchestra's concern.
        if paths and (result.get("ok") or error.get("code") == "cleanup_failed"):
            return Path(paths[0])
        code = str(error.get("code") or "no_image")
        message = str(error.get("message") or "the hub returned no image")[:300]
        if code in FALLBACK_CODES and _truthy(self.env.get("DM_ART_CODEX_FALLBACK")):
            # Codex gets only the remainder of the budget; too little left and it does not start.
            remainder = int(deadline - time.monotonic())
            if remainder < MIN_FALLBACK_SECONDS:
                raise ArtError(code, f"{message} (no time left for the codex fallback)")
            try:
                fallback = self.codex(prompt, self.env, remainder)
            except ArtError as exc:
                raise ArtError(exc.code, f"hub: {code}; codex fallback: {exc}")
            return Path(fallback["paths"][0])
        raise ArtError(code, message)

    def _store(self, campaign, source):
        try:
            with source.open("rb") as handle:
                data = handle.read(MAX_IMAGE_BYTES + 1)
        except OSError:
            raise ArtError("invalid_output", "generated image is not readable")
        if len(data) > MAX_IMAGE_BYTES:
            raise ArtError("invalid_output", "image is too large")
        if data[:8] != PNG_MAGIC:
            raise ArtError("invalid_output", "image is not a PNG")
        relative = write_incoming(self.root, campaign, data)
        return {"ok": True, "path": relative, "absolute_path": str(self.root / relative)}


class _Server(ThreadingHTTPServer):
    """At most MAX_CONNECTIONS requests at once; more are closed at once, so idle sockets can never use up the
    service's file descriptors (both tables share it)."""
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        timeout = REQUEST_READ_TIMEOUT   # a client that stops sending mid-request is dropped

        def _reply(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/generate":
                return self._reply(404, {"ok": False, "code": "not_found", "error": "POST /generate only"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 < length <= 64 * 1024:
                return self._reply(400, {"ok": False, "code": "bad_request", "error": "body size"})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._reply(400, {"ok": False, "code": "bad_request", "error": "body is not JSON"})
            self._reply(*service.generate(payload))

        def do_GET(self):
            self._reply(404, {"ok": False, "code": "not_found", "error": "POST /generate only"})

        def log_message(self, *args):   # generate() logs one line per request itself
            pass

    return Handler


def serve(port, root, env=None):
    server = _Server(("127.0.0.1", port), make_handler(ArtService(root, env)))
    print(f"screen art service on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


# ---------------------------------------------------------------- client

def request(campaign, prompt, port, timeout=CLIENT_READ_TIMEOUT):
    """(exit code, line to print) for one generation request to the local service."""
    import urllib.error
    import urllib.request

    body = json.dumps({"campaign": campaign, "prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/generate", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            reply = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            reply = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            return 1, f"art service error: HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return 1, f"art service unavailable on 127.0.0.1:{port} ({type(reason).__name__})"
    if isinstance(reply, dict) and reply.get("ok") and reply.get("path"):
        return 0, str(reply["path"])
    if not isinstance(reply, dict):
        return 1, "art service error: bad reply"
    return 1, f"art failed ({reply.get('code') or 'error'}): {' '.join(str(reply.get('error') or '').split())}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Act art through the MultiCode hub (dnd-play-art.service).")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="run the HTTP service on 127.0.0.1")
    s.add_argument("--port", type=int, default=None)
    r = sub.add_parser("request", help="ask the service for one act picture; prints the PNG path")
    r.add_argument("--campaign", default=None, help="default: $DM_ACTIVE_CAMPAIGN")
    r.add_argument("--prompt", required=True, help="the scene, no text in the picture")
    r.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    port = args.port or _int_env(os.environ, "DM_ART_PORT", DEFAULT_PORT)
    if args.command == "serve":
        # The repository to write into comes from the unit, never from where this file lives (/opt/dnd-play-art).
        root = os.environ.get("DM_ART_ROOT", "").strip()
        if not root or not os.path.isabs(root) or not os.path.isdir(root):
            print("DM_ART_ROOT must name the repository directory (an absolute path)", file=sys.stderr)
            return 2
        serve(port, root)
        return 0
    campaign = args.campaign or os.environ.get("DM_ACTIVE_CAMPAIGN", "")
    if not campaign:
        print("no campaign: pass --campaign or set DM_ACTIVE_CAMPAIGN")
        return 1
    code, line = request(campaign, args.prompt, port)
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
