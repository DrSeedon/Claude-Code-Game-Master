"""The hub master of an online table (owner decision 2026-10-28): a Claude agent in a T3 thread on the hub plays the
table instead of the SDK master, and the SDK master takes a batch the hub did not answer in time.

The driver (backend.screen_driver) POSTs each batch to the table's T3 webhook (post_event) with a one-turn ticket. The
hub agent runs engine tools on the VPS through `ssh kesha@VPS` with a restricted key whose forced command is the
root-owned gate (ops/play/hub-gate.py); the gate forwards each call over this module's unix socket (HubBridge), and the
driver runs the tool inside the table's sandbox. The gate never runs repository code itself: the sandboxed masters
can edit the repository. Runbook: ops/play/README.md, "Hub master (play table)".
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import hmac
import json
import logging
import os
import re
import secrets
import shlex
import signal
import stat
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from backend.providers.claude_screen import API_ROUTE_ENV, screen_tool_env

logger = logging.getLogger("dnd-play")

WEBHOOK_ENV = "DM_PLAY_HUB_WEBHOOK"
MAX_REQUEST = 2 * 1024 * 1024
MAX_ARGS = 64 * 1024
MAX_STDIN = 1024 * 1024
MAX_OUTPUT = 64 * 1024
MAX_READ = 256 * 1024
MAX_CONNECTIONS = 4
READ_TIMEOUT = 15.0
TOOL_TIMEOUT = 300.0          # dm-art.sh waits up to five minutes for a picture
HOOK_TIMEOUT = 20.0
LOCK_WAIT = 5.0               # a call waits this long for the one before it, then answers busy without running:
                              # 5 + 300 (tool) + 20 (hook) stays inside the gate's 330 s, so the gate never gives up on
                              # a call that still runs later
SLOW_TOOLS = {"dm-art.sh"}    # their run time extends the hub deadline (a new act waits 1-5 minutes for its picture)
BUSY = ("busy: another call of this turn is still running, so this call did NOT run. Run the calls one at a time and "
        "run this one again when the other has finished.")
CUT = "\n[... cut ...]\n"
REVOKED = ("ticket revoked: this turn went to the VPS master (the hub did not publish in time, or a newer event "
           "replaced it). Stop working on it and wait for the next event.")

_TOOL_NAME = re.compile(r"dm-[a-z0-9-]+\.sh")
# What the contract (.claude/additional/infrastructure/screen-driver-contract.md) forbids the master, enforced here
# because the hub master's calls pass this bridge anyway. dm-screen.sh: the screen and the waiting belong to the
# driver, and nothing spends credits or changes the shared audio library or the voice setup.
SCREEN_DENIED = {"start", "stop", "restart", "serve", "listen", "wait", "enable", "speak", "audition", "key", "hook"}
SCREEN_SUB_DENIED = {"audio": {"make", "add", "seed", "remove", "normalize"},
                     "voice": {"design", "keep", "delete", "model", "narrator", "default", "cast", "set"}}
# dm-campaign.sh: reading only (switch, create, delete and reset change which campaign plays or destroy one).
CAMPAIGN_ALLOWED = {"list", "info", "status", "active", "path", "help", "-h", "--help"}
# Whole tools that move, migrate, extract into or reset campaigns.
TOOLS_DENIED = {"dm-migrate-campaigns.sh", "dm-migrate-worldgraph.sh", "dm-extract.sh"}


def _env_number(environ, name, default, cast=float):
    try:
        return cast(environ.get(name) or default)
    except (TypeError, ValueError):
        logger.warning("%s=%r is not a number; using %s", name, environ.get(name), default)
        return default


@dataclass
class HubSettings:
    master: str = "sdk"                              # "hub": the batches go to the hub first
    webhook: str | None = field(default=None, repr=False)   # holds a token: never logged
    timeout: float = 300.0                           # a batch the hub has not published by then goes to the SDK master
    fails: int = 2                                   # consecutive hub failures before a pause
    pause: float = 900.0
    socket: Path | None = None
    poll: float = 1.0

    @property
    def hub(self):
        return self.master == "hub"

    @classmethod
    def from_env(cls, environ=os.environ):
        master = (environ.get("DM_PLAY_MASTER") or "sdk").strip().lower()
        if master not in ("hub", "sdk"):
            logger.warning("DM_PLAY_MASTER=%r is neither hub nor sdk: the table plays with the sdk master", master)
            master = "sdk"
        runtime = (environ.get("RUNTIME_DIRECTORY") or "").split(":")[0]
        socket = environ.get("DM_PLAY_HUB_SOCKET") or (str(Path(runtime) / "hub.sock") if runtime else None)
        webhook = environ.get(WEBHOOK_ENV) or None
        if master == "hub" and not (webhook and socket):
            logger.error("DM_PLAY_MASTER=hub needs %s and a socket (DM_PLAY_HUB_SOCKET or RUNTIME_DIRECTORY): "
                         "the table plays with the sdk master", WEBHOOK_ENV)
            master = "sdk"
        return cls(master=master, webhook=webhook, timeout=_env_number(environ, "DM_PLAY_HUB_TIMEOUT", cls.timeout),
                   fails=max(1, _env_number(environ, "DM_PLAY_HUB_FAILS", cls.fails, int)),
                   pause=_env_number(environ, "DM_PLAY_HUB_PAUSE", cls.pause), socket=Path(socket) if socket else None)


def post_event(url, payload, timeout=20):
    """POST the payload as JSON; (True, None) on a 2xx answer, else (False, error). The error never holds the URL:
    its path is the webhook's token."""
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"unreachable: {type(exc.reason).__name__}"
    except Exception as exc:
        return False, type(exc).__name__
    return (True, None) if 200 <= status < 300 else (False, f"HTTP {status}")


def scrub_exec_environ(name):
    """Remove `name` from os.environ and overwrite its value in the process's exec environment block. Popping it
    alone leaves the bytes that /proc/<pid>/environ reads (the kernel shows the original block, not os.environ)."""
    if name not in os.environ:
        return False
    try:
        import ctypes

        libc = ctypes.CDLL(None)
        libc.getenv.restype, libc.getenv.argtypes = ctypes.c_void_p, [ctypes.c_char_p]
        libc.strlen.restype, libc.strlen.argtypes = ctypes.c_size_t, [ctypes.c_void_p]
        value = libc.getenv(name.encode())
        if value:
            ctypes.memset(value, 0, libc.strlen(value))
    except Exception as exc:    # never stops the driver; the variable still leaves os.environ
        logger.warning("could not wipe %s from the exec environment: %s", name, type(exc).__name__)
    os.environ.pop(name, None)
    return True


def tool_env(campaign, sdir, environ=os.environ):
    """The SDK master's tool environment (claude_screen.screen_tool_env) over the driver's scrubbed environment."""
    env = {k: v for k, v in environ.items() if k not in API_ROUTE_ENV and k != WEBHOOK_ENV}
    env.update(screen_tool_env(campaign, sdir))
    return env


def deny_reason(name, args):
    """Why a tool call is refused, or None."""
    if name in TOOLS_DENIED:
        return f"{name} is not for the online table"
    words = [a for a in args if not a.startswith("-")]
    sub = words[0] if words else None
    if name == "dm-screen.sh":
        if sub in SCREEN_DENIED:
            return f"dm-screen.sh {sub} belongs to the driver or spends credits"
        denied = SCREEN_SUB_DENIED.get(sub, set()) & set(args[1:])
        if denied:
            return f"dm-screen.sh {sub} {sorted(denied)[0]} is not allowed online (credits, the shared library, the voice setup)"
    elif name == "dm-campaign.sh":
        if args and args[0] not in CAMPAIGN_ALLOWED:
            return f"dm-campaign.sh {args[0]} is not allowed: the table's campaign changes only with the players, through the VPS master"
    elif name == "dm-play.sh":
        if args != ["status"]:
            return "only dm-play.sh status is allowed"
    elif name == "dm-reset.sh":
        if args != ["preview"]:
            return "only dm-reset.sh preview is allowed"
    return None


def cap_output(data: bytes, limit=MAX_OUTPUT):
    if len(data) <= limit:
        return data.decode("utf-8", errors="replace")
    half = limit // 2
    return data[:half].decode("utf-8", errors="replace") + CUT + data[-half:].decode("utf-8", errors="replace")


async def _read_capped(stream, limit=MAX_OUTPUT):
    """Everything the tool prints, keeping only the head and the tail of a long output in memory."""
    half = limit // 2
    head, tail, total = bytearray(), bytearray(), 0
    while chunk := await stream.read(65536):
        total += len(chunk)
        if len(head) < half:
            take = half - len(head)
            head += chunk[:take]
            chunk = chunk[take:]
        tail += chunk
        if len(tail) > half:
            del tail[:-half]
    if total <= limit:
        return (bytes(head) + bytes(tail)).decode("utf-8", errors="replace")
    return head.decode("utf-8", errors="replace") + CUT + tail.decode("utf-8", errors="replace")


def _kill_group(pid):
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


class HubBridge:
    """The driver's side of the gate: one unix socket, one JSON line in, one JSON line out.

    `context()` returns the table's current {"campaign", "sdir", "turn"}. Calls run one at a time (engine writes are not
    concurrent-safe) and only with the current ticket; revoke() waits for a running call, so nothing of the hub runs
    after the turn went to the SDK master."""

    def __init__(self, path, root, table, context, *, tool_timeout=TOOL_TIMEOUT, read_timeout=READ_TIMEOUT,
                 hook_timeout=HOOK_TIMEOUT, hook_argv=None, max_connections=MAX_CONNECTIONS, lock_wait=LOCK_WAIT):
        self.path = Path(path)
        self.root = Path(root)
        self.table = table
        self.context = context
        self.tool_timeout = tool_timeout
        self.read_timeout = read_timeout
        self.hook_timeout = hook_timeout
        self.hook_argv = hook_argv or [sys.executable, "-m", "lib.screen.cli", "hook"]
        self.max_connections = max_connections
        self.lock_wait = lock_wait
        self.ticket = None
        self.slow_seconds = 0.0     # run time of SLOW_TOOLS under the current ticket
        self.slow_since = None
        self.lock = asyncio.Lock()
        self.server = None
        self.active = 0

    # ---- lifecycle and tickets

    async def start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_socket() or self.path.is_symlink():   # left by a driver that was killed
            self.path.unlink()
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.path), limit=MAX_REQUEST + 1)
        os.chmod(self.path, 0o600)
        logger.info("hub bridge listening on %s", self.path)

    async def stop(self):
        self.ticket = None
        if self.server is not None:
            self.server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.server.wait_closed(), 5)
            self.server = None
        with contextlib.suppress(OSError):
            self.path.unlink()

    def issue(self):
        """A new ticket for one turn; the previous one stops working."""
        self.ticket = secrets.token_urlsafe(18)
        self.slow_seconds = 0.0
        return self.ticket

    def extension(self):
        """Seconds the current ticket spent in SLOW_TOOLS (the running one included): the driver adds them to the
        hub deadline, so a batch that opens a new act is not lost to the picture's wait."""
        running = time.monotonic() - self.slow_since if self.slow_since is not None else 0.0
        return self.slow_seconds + running

    async def revoke(self):
        """No call runs with the old ticket after this returns."""
        self.ticket = None
        async with self.lock:
            pass

    def ticket_ok(self, ticket):
        current = self.ticket
        return bool(current) and isinstance(ticket, str) and hmac.compare_digest(ticket.encode(), current.encode())

    # ---- the socket

    async def _handle(self, reader, writer):
        if self.active >= self.max_connections:
            await self._reply(writer, {"code": 4, "output": "busy: too many calls at once; run one call at a time"})
            return
        self.active += 1
        try:
            try:
                line = await asyncio.wait_for(reader.readline(), self.read_timeout)
            except asyncio.TimeoutError:
                return await self._reply(writer, {"code": 2, "output": "bad request: no request line in time"})
            except (ValueError, asyncio.LimitOverrunError):
                return await self._reply(writer, {"code": 2, "output": "bad request: over 2 MiB"})
            try:
                request = self._parse(line)
            except ValueError as exc:
                return await self._reply(writer, {"code": 2, "output": f"bad request: {exc}"})
            response = await self._watched(reader, self.call(request["ticket"], request["argv"], request["stdin"]),
                                           request["argv"])
            if response is not None:
                await self._reply(writer, response)
        except Exception:
            logger.exception("hub call failed")
            with contextlib.suppress(Exception):
                await self._reply(writer, {"code": 1, "output": "the bridge failed on this call (see the driver journal)"})
        finally:
            self.active -= 1

    @staticmethod
    async def _watched(reader, coro, argv):
        """Run the call while watching its connection: the gate sends one line and keeps the socket open until the
        answer, so EOF means it left (its ssh session died, the agent's Bash timed out). Then the call stops (its
        process group is killed, a queued call never runs): nothing of an abandoned call runs later with a valid
        ticket, and the agent's retry does not repeat it. None when the gate left."""
        call = asyncio.ensure_future(coro)
        gone = asyncio.ensure_future(reader.read(1))
        try:
            while True:
                done, _ = await asyncio.wait({call, gone}, return_when=asyncio.FIRST_COMPLETED)
                if call in done:
                    return call.result()
                try:
                    left = gone.result() == b""
                except Exception:
                    left = True
                if left:
                    break
                gone = asyncio.ensure_future(reader.read(1))    # stray bytes after the line: ignored
            logger.warning("hub call %s abandoned by the gate: stopped", shlex.join(argv)[:200])
            call.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await call
            return None
        finally:
            gone.cancel()
            call.cancel()

    @staticmethod
    async def _reply(writer, response):
        try:
            writer.write(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
            await writer.drain()
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    @staticmethod
    def _parse(line):
        if len(line) > MAX_REQUEST:
            raise ValueError("over 2 MiB")
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("not one JSON line") from None
        if not isinstance(request, dict):
            raise ValueError("not a JSON object")
        argv, stdin, ticket = request.get("argv"), request.get("stdin"), request.get("ticket")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise ValueError("argv must be a non-empty list of strings")
        if stdin is not None and not isinstance(stdin, str):
            raise ValueError("stdin must be a string or null")
        return {"ticket": ticket if isinstance(ticket, str) else None, "argv": argv, "stdin": stdin}

    # ---- the calls

    async def call(self, ticket, argv, stdin=None):
        op = argv[0]
        if op == "status":
            ctx = self.context()
            return {"code": 0, "output": json.dumps({"table": self.table, "campaign": ctx["campaign"], "turn": ctx["turn"],
                                                     "ticket_ok": self.ticket_ok(ticket)}, ensure_ascii=False)}
        if not self.ticket_ok(ticket):      # a revoked call answers so at once, not busy after the lock wait
            logger.info("hub call %s refused: ticket revoked", op[:60])
            return {"code": 3, "output": REVOKED}
        try:
            await asyncio.wait_for(self.lock.acquire(), self.lock_wait)
        except asyncio.TimeoutError:
            logger.info("hub call %s refused: busy", op[:60])
            return {"code": 4, "output": BUSY}
        try:
            if not self.ticket_ok(ticket):  # the check that counts: revoke() may have come while this call waited
                logger.info("hub call %s refused: ticket revoked", op[:60])
                return {"code": 3, "output": REVOKED}
            started = time.monotonic()
            if op == "prompt":
                response = self._prompt()
            elif op == "read":
                response = self._read(argv[1:])
            else:
                response = await self._tool(argv, stdin)
            logger.info("hub call %s: exit %s, %.1fs", shlex.join(argv)[:200], response["code"], time.monotonic() - started)
            return response
        finally:
            self.lock.release()

    def _prompt(self):
        path = Path(self.context()["sdir"]) / "gm-system-prompt.md"
        try:
            return {"code": 0, "output": path.read_text(encoding="utf-8")}
        except OSError:
            return {"code": 1, "output": "no system prompt yet (the driver writes it when the campaign opens)"}

    def _read(self, args):
        if len(args) != 1:
            return {"code": 2, "output": "usage: read <path inside the campaign directory>"}
        parts = [p for p in args[0].split("/") if p not in ("", ".")]
        if not parts or args[0].startswith("/") or ".." in parts or "\0" in args[0]:
            return {"code": 2, "output": "read: only files inside the campaign directory"}
        base = self.root / "world-state" / "campaigns" / self.context()["campaign"]
        # One component at a time from the campaign directory, none of them a symlink: a path checked first and opened
        # later could be swapped for a symlink in between by a process of the sandbox (the SDK master).
        fds = []
        try:
            try:
                fds.append(os.open(base, os.O_RDONLY | os.O_DIRECTORY))
                for part in parts[:-1]:
                    fds.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1]))
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fds[-1])
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    return {"code": 2, "output": "read: only files inside the campaign directory (no symlinks)"}
                return {"code": 1, "output": f"read: {exc.strerror or 'cannot open'}"}
        finally:
            for opened in fds:
                os.close(opened)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                return {"code": 2, "output": "read: not a regular file"}
            if info.st_size > MAX_READ:
                return {"code": 2, "output": f"read: over {MAX_READ // 1024} KiB"}
            data = handle.read(MAX_READ + 1)
        if len(data) > MAX_READ:
            return {"code": 2, "output": f"read: over {MAX_READ // 1024} KiB"}
        try:
            return {"code": 0, "output": data.decode("utf-8")}
        except UnicodeDecodeError:
            return {"code": 2, "output": "read: not a UTF-8 text file"}

    async def _tool(self, argv, stdin):
        argv = list(argv)
        if argv[0] == "bash":
            argv = argv[1:]
        if not argv:
            return {"code": 2, "output": "usage: <dm-tool.sh> [args...]"}
        name, args = argv[0].removeprefix("tools/"), argv[1:]
        if not _TOOL_NAME.fullmatch(name) or not (self.root / "tools" / name).is_file():
            return {"code": 2, "output": f"unknown tool {argv[0][:80]!r}: only tools/dm-*.sh, prompt, read <path>, status"}
        if reason := deny_reason(name, args):
            return {"code": 2, "output": f"refused: {reason}"}
        if any("\0" in a for a in args) or sum(len(a.encode("utf-8")) for a in args) > MAX_ARGS:
            return {"code": 2, "output": "refused: arguments with NUL or over 64 KiB"}
        data = stdin.encode("utf-8") if stdin is not None else None
        if data is not None and len(data) > MAX_STDIN:
            return {"code": 2, "output": "refused: stdin over 1 MiB"}
        ctx = self.context()
        env = tool_env(ctx["campaign"], ctx["sdir"])
        slow = name in SLOW_TOOLS
        if slow:
            self.slow_since = time.monotonic()
        try:
            code, output = await self._run(["bash", f"tools/{name}", *args], data, env)
        finally:
            if slow:
                self.slow_seconds += time.monotonic() - self.slow_since
                self.slow_since = None
        output += await self._hook(name, args, output, env)
        return {"code": code, "output": output}

    async def _run(self, argv, data, env):
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=self.root, env=env, stdin=asyncio.subprocess.PIPE if data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        reader = asyncio.ensure_future(_read_capped(proc.stdout))
        feeder = asyncio.ensure_future(self._feed(proc.stdin, data)) if data is not None else None
        note = ""
        try:
            try:
                code = await asyncio.wait_for(proc.wait(), self.tool_timeout)
            except asyncio.TimeoutError:
                _kill_group(proc.pid)
                code = await proc.wait()
                code, note = 124, f"\n[timed out after {self.tool_timeout:.0f}s: the tool was stopped]"
            try:
                output = await asyncio.wait_for(asyncio.shield(reader), 0.5)
            except asyncio.TimeoutError:
                # The tool exited but something of its group still holds the output open: it dies with the tool.
                _kill_group(proc.pid)
                output = await asyncio.wait_for(reader, 5)
        except BaseException:
            _kill_group(proc.pid)
            reader.cancel()
            raise
        finally:
            if feeder is not None:
                feeder.cancel()
        return code, output + note

    @staticmethod
    async def _feed(stdin, data):
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            stdin.write(data)
            await stdin.drain()
            stdin.close()

    async def _hook(self, name, args, output, env):
        """The project's PostToolUse hook, as Claude Code would run it for this Bash call: dice and changes go to
        the live feed, and its act nudge comes back to the hub master. A failing hook never fails the call."""
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": shlex.join(["bash", f"tools/{name}", *args])},
                   "tool_response": {"stdout": output, "stderr": "", "interrupted": False}}
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.hook_argv, cwd=self.root, env={**env, "DM_PLAY_TABLE": self.table}, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
            out, _ = await asyncio.wait_for(proc.communicate(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                                            self.hook_timeout)
            context = json.loads(out.decode("utf-8"))["hookSpecificOutput"]["additionalContext"] if out.strip() else None
        except asyncio.CancelledError:
            if proc is not None:
                _kill_group(proc.pid)
            raise
        except Exception as exc:
            if proc is not None and proc.returncode is None:
                _kill_group(proc.pid)
            logger.info("screen hook after %s skipped: %s", name, type(exc).__name__)
            return ""
        return f"\n\n[screen hook] {context}" if isinstance(context, str) and context else ""
