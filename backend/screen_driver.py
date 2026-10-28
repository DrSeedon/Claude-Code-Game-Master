"""The online screen table (owner decision 2026-10-26): one shared HTML screen, one Claude Code master.

The driver owns the screen server (a child process), collects the players' actions from the screen inbox and sends
them to the master in batches; the master answers each message with a screen turn (dm-screen.sh turn). Between
batches it follows world-state/online-<table>.json (pause, campaign switch, screen restart, see lib/screen/online.py)
and writes world-state/online-<table>-status.json, which the page shows. The table is DM_PLAY_TABLE (default "play");
each table is its own unit, port and campaign. Run: python -m backend.screen_driver.

With DM_PLAY_MASTER=hub (owner decision 2026-10-28, backend/hub_master.py) a batch goes to the hub master first, a T3
thread on the hub that plays through the gate; a batch it has not published in time goes to the SDK master.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.hub_master import TOOL_TIMEOUT, WEBHOOK_ENV, HubBridge, HubSettings, post_event, scrub_exec_environ
from backend.providers.claude_screen import ScreenGMProvider, scrub_api_route_env
from backend.runtime.session_store import clear_runtime_session, load_runtime_session, save_runtime_session
from backend.runtime.turn_lock import CampaignTurnLock
from backend.usage_log import record_usage
from lib.screen import activity, inbox, online
from lib.screen import cli as screen_cli

logger = logging.getLogger("dnd-play")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = "claude"
GM_SESSION = "gm-session.json"
PROMPT_FILE = "gm-system-prompt.md"
CARRY_MAX = 12
CHILD_BACKOFF_MAX = 60.0
RATE_LIMIT_WAIT = 300.0       # a limit that names no reset time: the first wait, doubled while the limit lasts
RATE_LIMIT_MAX = 3600.0
SWITCH_RETRY_MAX = 300.0
SCREEN_CAPS = ("DM_SCREEN_DAILY_CREDITS", "DM_SCREEN_TURN_CREDITS", "DM_SCREEN_SOUND_GENERATION", "DM_SCREEN_MAX_PENDING",
               "DM_SCREEN_DAILY_VOICE_MB", "DM_SCREEN_SPEND_FILE")

PUBLISH = "Publish it now with bash tools/dm-screen.sh turn --file <json>."
NOT_PUBLISHED = f"[system] The turn was not published. {PUBLISH}"
# The music line is here, not only in the contract: after a switch the master took the rule for fresh sessions only
# and the table stayed silent (2026-10-27).
STANDS = ("Show where the story stands now: publish a turn that keeps the current act (a campaign without one gets an act "
          "with its picture from bash tools/dm-art.sh). Give this turn audio.music and audio.ambience from the library "
          "(bash tools/dm-screen.sh audio find \"<cue>\" --kind music, \"generate\": false): the table is silent until "
          "a turn sets them.")
FRESH = "[system] A fresh session starts at the online table, campaign {name}. " + STANDS
SWITCHED = "[system] The table switched to campaign {name}. " + STANDS
CARRIED = "[system] The previous message hit a usage limit and got no answer. Answer these actions now."
RESTARTED = ("[system] These actions reached the master before, but no turn answered them (the driver restarted or the turn "
             "failed). Check the world state for what was already applied, then answer them in this turn.")
# Shown in the screen's live feed (players' language).
REST_LINE = "Мастер отдыхает: лимит ходов"
LIMIT_LINE = "Мастер отдыхает: лимит подписки, скоро вернётся"
FAILED_LINE = "Мастер споткнулся: ход не вышел, повторите действие"
HUB_FAILED_LINE = "Мастер на хабе не ответил: ход играет запасной мастер"
HUB_PAUSED_LINE = "Мастер на хабе недоступен: пока играет запасной мастер"
# The hub master (DM_PLAY_MASTER=hub): what each master is told when the other one played in between.
TAKEOVER = "[system] You take over this table from the VPS master. " + STANDS
HUB_CATCH_UP = ("[system] The VPS master played the turns since your last answer (or the table's driver restarted). Catch "
                "up first: run status and dm-screen.sh log --kind turn --tail 3 --json through the gate (dm-session.sh "
                "context when the scene is unclear), then answer.")
SDK_CATCH_UP = ("[system] Another master played the turns since your last answer. Catch up first: bash tools/dm-session.sh "
                "context and bash tools/dm-screen.sh log --kind turn --tail 3 --json, then answer.")
HUB_FALLBACK = ("[system] The hub master did not answer this batch in time, so it comes to you. The engine may already "
                "hold part of it: check the world state before you apply anything.")


def _env_number(environ, name, default, cast=int):
    try:
        return cast(environ.get(name) or default)
    except (TypeError, ValueError):
        logger.warning("%s=%r is not a number; using %s", name, environ.get(name), default)
        return default


@dataclass
class Settings:
    model: str = "claude-sonnet-5-5"
    effort: str = "medium"
    max_turns_hour: int = 30          # 0 = no cap
    max_turns_day: int = 200          # 0 = no cap
    turn_timeout: float = 600.0
    idle_disconnect: float = 20 * 60.0
    settle: float = 1.5
    max_events: int = 6
    batch_timeout: float = 1.0
    tick: float = 1.0

    @classmethod
    def from_env(cls, environ=os.environ):
        return cls(model=environ.get("DM_PLAY_MODEL") or cls.model, effort=environ.get("DM_PLAY_EFFORT") or cls.effort,
                   max_turns_hour=_env_number(environ, "DM_PLAY_MAX_TURNS_PER_HOUR", cls.max_turns_hour),
                   max_turns_day=_env_number(environ, "DM_PLAY_MAX_TURNS_PER_DAY", cls.max_turns_day),
                   turn_timeout=_env_number(environ, "DM_PLAY_TURN_TIMEOUT", cls.turn_timeout, float))


@dataclass
class TurnResult:
    text: list = field(default_factory=list)
    error: str | None = None
    rate_limited: bool = False
    retry_after: float | None = None
    timed_out: bool = False


LIMIT_SIGNALS = ("usage limit", "rate limit", "rate_limit", "too many requests", "session limit", "hit your limit",
                 "limit reached", "overloaded", " 429")


_RESET = re.compile(r"\|(\d{10})\b")
_WAIT = re.compile(r"\b(?:retry[- ]after|try again in|wait)\D{0,12}?(\d+)\s*(h(?:ours?|rs?)?|m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)?\b")
_UNITS = {"h": 3600, "m": 60, "s": 1}


def clamp_wait(seconds):
    return min(max(float(seconds), 60.0), 6 * 3600.0)


def usage_limit(text, now):
    """(True, seconds to wait or None) when an error result is a subscription or rate limit, else (False, None).

    The CLI reports the subscription limit as an error result, not an exception ("Claude AI usage limit
    reached|<reset epoch>" or "You've hit your limit"), which the base provider passes on as a plain error.
    A wait in words keeps its unit ("try again in 5 hours"); a bare number is seconds."""
    low = f" {text}".lower()
    if not any(signal in low for signal in LIMIT_SIGNALS):
        return False, None
    if found := _RESET.search(text):
        return True, clamp_wait(int(found.group(1)) - now)
    if found := _WAIT.search(low):
        return True, clamp_wait(int(found.group(1)) * _UNITS[(found.group(2) or "s")[0]])
    return True, None


def unanswered_lines(sdir):
    """Actions the master was given that no published turn answered (newest CARRY_MAX): the driver stopped mid-turn
    or in a usage-limit rest (whose carry lived in memory), or the turn failed. The cursor is written before a send."""
    try:
        answered = int((online.read_json(Path(sdir) / "turn.json") or {}).get("answered") or 0)
        cursor = screen_cli.read_cursor(sdir)
        return [inbox.format_line(e) for e in inbox.read_events(sdir, after_id=answered) if e["id"] <= cursor][-CARRY_MAX:]
    except (OSError, ValueError, KeyError, TypeError) as exc:   # a broken inbox: the loop reports it
        logger.warning("unanswered actions of %s not checked: %s", sdir, exc)
        return []


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def turn_id(sdir):
    return int((online.read_json(Path(sdir) / "turn.json") or {}).get("id") or 0)


def session_context(root, campaign, timeout=60):
    """`bash tools/dm-session.sh context` for the campaign; empty when it fails."""
    try:
        done = subprocess.run(["bash", "tools/dm-session.sh", "context"], cwd=root, capture_output=True, text=True,
                              timeout=timeout, env={**os.environ, "DM_ACTIVE_CAMPAIGN": campaign})
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("session context for %s skipped: %s", campaign, exc)
        return ""
    if done.returncode != 0:
        logger.warning("session context for %s skipped: exit %s %s", campaign, done.returncode, done.stderr.strip()[-300:])
        return ""
    return done.stdout.strip()


def build_prompt(root, campaign, sdir, base_prompt=None, context=None):
    """The master's appended system prompt in <screen>/gm-system-prompt.md (0600): DM rules and campaign rules,
    audio direction, the online contract, the session handoff and the session context. Missing parts are skipped."""
    root, sdir = Path(root), Path(sdir)
    if base_prompt is None:
        from backend.claude_dm import load_system_prompt
        base_prompt = load_system_prompt(campaign, include_cinematic=False)   # the scene-art MCP tool is web-only
    parts = [base_prompt.strip()]
    infra = root / ".claude" / "additional" / "infrastructure"
    for path in (infra / "audio-direction.md", infra / "screen-driver-contract.md",
                 root / "world-state" / "campaigns" / campaign / "session-handoff.md"):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    context = session_context(root, campaign) if context is None else context
    if context:
        parts.append("# Session context at the start of this session (bash tools/dm-session.sh context)\n\n" + context)
    sdir.mkdir(parents=True, exist_ok=True)
    path = sdir / PROMPT_FILE
    tmp = path.with_name(f".{PROMPT_FILE}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write("\n\n---\n\n".join(p for p in parts if p) + "\n")
    os.replace(tmp, path)
    return path


def spawn_screen_server(root, sdir, campaign, port):
    """The screen server for one campaign; it reads its keys and caps itself (project .env, DM_SCREEN_* env). The
    daily spend ledger is shared by every table and campaign: a switch must not reset the day's budget, and a second
    table must not double it."""
    sdir.mkdir(parents=True, exist_ok=True)
    spend = os.environ.get("DM_SCREEN_SPEND_FILE") or str(Path(root) / "world-state" / "usage" / "screen-spend.json")
    with open(sdir / "server.log", "ab") as log:
        return subprocess.Popen([sys.executable, "-m", "lib.screen.cli", "serve", "--port", str(port)], cwd=root,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                env={**os.environ, "DM_SCREEN_DIR": str(sdir), "DM_ACTIVE_CAMPAIGN": campaign,
                                     "DM_SCREEN_SPEND_FILE": spend})


def _is_screen_server(pid):
    try:
        return b"lib.screen.cli" in Path(f"/proc/{int(pid)}/cmdline").read_bytes()
    except (OSError, ValueError, TypeError):
        return False


class ScreenDriver:

    def __init__(self, root=PROJECT_ROOT, campaign=None, settings=None, provider_factory=None, spawn=None,
                 prompt_builder=None, clock=time.time, hub=None, poster=None, bridge_factory=None):
        self.root = Path(root)
        self.campaign_arg = campaign
        self.settings = settings or Settings.from_env()
        self.provider_factory = provider_factory or self._make_provider
        self.spawn = spawn or spawn_screen_server
        self.prompt_builder = prompt_builder or build_prompt
        self.clock = clock
        self.campaign = None
        self.port = online.default_port()
        self.paused = False
        self.screen_restart_seen = 0
        self.provider = None
        self.connected = False
        self.persisted_session = None
        self.child = None
        self.child_started = 0.0
        self.child_next_start = 0.0
        self.child_backoff = 1.0
        self.child_reported = False
        self.child_lock = asyncio.Lock()
        self.state = "starting"
        self.last_error = None
        self.last_turn_at = None
        self.turn_times: list[float] = []
        self.notices: list[str] = []
        self.carry: list[str] = []
        self.retry_at = 0.0
        self.limit_streak = 0
        self.rest_posted = False
        self.session_reset_seen = 0
        self.switch_retry_at = 0.0
        self.switch_backoff = 0.0
        self.failed = False
        self.last_used = clock()
        self.bad_campaign = None
        self.stopping = False
        self.hub = hub or HubSettings.from_env()
        self.poster = poster or post_event
        self.bridge_factory = bridge_factory or HubBridge
        self.bridge = None
        self.hub_fails = 0
        self.hub_paused_until = 0.0
        self.hub_last_result = None
        self.hub_last_turn_at = None
        self.hub_takeover = False
        self.hub_behind = True      # the hub has not seen what happened before this driver started
        self.sdk_behind = False     # the hub published turns the SDK master's session has not seen

    # ---- paths and small helpers

    @property
    def campaign_dir(self):
        return online.campaigns_dir(self.root) / self.campaign

    @property
    def sdir(self):
        return self.campaign_dir / "screen"

    def _make_provider(self, campaign, sdir, prompt_file, resume):
        return ScreenGMProvider(self.root, self.settings.model, campaign, prompt_file=prompt_file, screen_dir=sdir,
                                effort=self.settings.effort, resume_session_id=resume)

    def _activity(self, text):
        try:
            activity.append_activity(self.sdir, "info", text)
        except Exception:
            logger.exception("activity line failed")

    def _turns_within(self, seconds, now=None):
        now = self.clock() if now is None else now
        return sum(1 for t in self.turn_times if now - t < seconds)

    def capped(self, now=None):
        s = self.settings
        return bool((s.max_turns_hour and self._turns_within(3600, now) >= s.max_turns_hour)
                    or (s.max_turns_day and self._turns_within(86400, now) >= s.max_turns_day))

    def status(self):
        now = self.clock()
        self.turn_times = [t for t in self.turn_times if now - t < 86400]
        return {"pid": os.getpid(), "campaign": self.campaign, "port": self.port, "state": self.state,
                "session_id": self.provider.session_id if self.provider else None,
                "turns_hour": self._turns_within(3600, now), "turns_day": len(self.turn_times),
                "last_turn_at": self.last_turn_at, "last_error": self.last_error,
                "turn_times": [round(t, 3) for t in self.turn_times],
                "retry_at": round(self.retry_at, 3) if self.retry_at > now else None,
                "master": self.hub.master,
                "hub": {"fails": self.hub_fails,
                        "paused_until": round(self.hub_paused_until, 3) if self.hub_paused_until > now else None,
                        "last_result": self.hub_last_result, "last_turn_at": self.hub_last_turn_at} if self.hub.hub else None}

    def write_status(self):
        try:
            online.write_status(self.status(), self.root)
        except OSError:
            logger.exception("status write failed")

    def set_state(self, state):
        if state != self.state:
            logger.info("[%s] state %s -> %s", self.campaign, self.state, state)
        self.state = state
        self.write_status()

    # ---- start, campaign, child process

    def _bridge_context(self):
        return {"campaign": self.campaign, "sdir": self.sdir, "turn": turn_id(self.sdir)}

    async def start(self):
        # Its URL holds a token: no child (the CLI, the screen server, tools) inherits it, and it is wiped from the
        # exec environment too, which /proc/<driver pid>/environ shows to every process with ptrace read access.
        scrub_exec_environ(WEBHOOK_ENV)
        removed = scrub_api_route_env()
        if removed:
            logger.warning("removed %s from the environment: the master thinks on the subscription", ", ".join(removed))
        config = online.load_config(self.root, campaign=self.campaign_arg, create=True)
        campaign = online.check_campaign(config["campaign"], self.root)
        if busy := online.other_table_with(campaign, self.root):   # two masters writing one campaign
            raise online.CampaignError(f"table {busy!r} plays {campaign}: give this table another campaign (a copy)")
        self.port, self.paused, self.screen_restart_seen = config["port"], config["paused"], config["screen_restart"]
        self.session_reset_seen = config.get("session_reset", 0)
        previous = online.read_status(self.root) or {}
        now = self.clock()
        self.turn_times = [float(t) for t in previous.get("turn_times") or [] if isinstance(t, (int, float)) and now - t < 86400]
        self.last_turn_at = previous.get("last_turn_at")
        s = self.settings
        logger.info("driver pid %s: table %s, campaign %s, port %s, model %s, effort %s, caps %s/hour %s/day, turn timeout %ss",
                    os.getpid(), online.table_name(), campaign, self.port, s.model, s.effort, s.max_turns_hour, s.max_turns_day, s.turn_timeout)
        logger.info("screen limits: %s", ", ".join(f"{key}={os.environ.get(key, 'unset')}" for key in SCREEN_CAPS))
        async with self.child_lock:
            await self.open_campaign(campaign, fresh=False)
            self.start_child()
        retry_at = previous.get("retry_at")
        if isinstance(retry_at, (int, float)) and retry_at > now:
            self.retry_at, self.limit_streak = float(retry_at), 1   # a usage-limit rest outlives a restart
        # The SDK master's resumed session missed what the hub played before this start.
        self.sdk_behind = bool(self.persisted_session) and previous.get("master") == "hub"
        if self.hub.hub:
            self.hub_takeover = previous.get("master") != "hub"
            before = previous.get("hub") if isinstance(previous.get("hub"), dict) else {}
            paused = before.get("paused_until")
            if isinstance(paused, (int, float)) and paused > now:   # a hub pause outlives a restart
                self.hub_paused_until, self.hub_fails = float(paused), int(before.get("fails") or 0)
            self.hub_last_turn_at = before.get("last_turn_at")
            self.bridge = self.bridge_factory(self.hub.socket, self.root, online.table_name(), self._bridge_context)
            await self.bridge.start()
        logger.info("master: %s%s", self.hub.master, f" (webhook {'set' if self.hub.webhook else 'unset'}, timeout "
                    f"{self.hub.timeout:.0f}s, pause {self.hub.pause:.0f}s after {self.hub.fails} failures, socket "
                    f"{self.hub.socket})" if self.hub.hub else "")
        self.write_status()

    async def open_campaign(self, name, fresh, notice=FRESH):
        """Point the driver at a campaign: delivery cursor, prompt, provider (resumed unless `fresh`).
        Nothing changes when a step fails, so a failed switch is retried later. Actions delivered before but never
        answered (unanswered_lines) go to the master again with the first message."""
        sdir = online.campaigns_dir(self.root) / name / "screen"
        sdir.mkdir(parents=True, exist_ok=True)
        if (sdir / screen_cli.WAIT_CURSOR).is_file():
            missed = unanswered_lines(sdir)
        else:
            events = inbox.read_events(sdir)
            screen_cli.write_cursor(sdir, events[-1]["id"] if events else 0)
            logger.info("[%s] delivery cursor starts at %s: older actions count as handled", name, screen_cli.read_cursor(sdir))
            missed = []
        if fresh:
            clear_runtime_session(sdir, GM_SESSION)
        stored = load_runtime_session(sdir, GM_SESSION)
        resume = stored.session_id if stored and stored.runtime_id == RUNTIME and stored.model_name == self.settings.model else None
        prompt_file = await asyncio.to_thread(self.prompt_builder, self.root, name, sdir)
        logger.info("[%s] prompt %s (%d bytes), %s", name, prompt_file, Path(prompt_file).stat().st_size,
                    f"resuming session {resume}" if resume else "fresh session")
        provider = self.provider_factory(name, sdir, prompt_file, resume)
        self.campaign, self.provider = name, provider
        self.persisted_session = resume
        self.connected = False
        self.failed = False
        self.carry = [RESTARTED, *missed] if missed else []   # retry_at stays: a usage limit is the account's
        self.notices = [] if resume else [notice.format(name=name)]
        if not resume:
            self.sdk_behind = False     # a fresh session loads the context itself
        if missed:
            logger.warning("[%s] %d delivered actions got no turn: they go to the master again", name, len(missed))

    def _stop_foreign_server(self):
        """A screen server of this campaign that is not ours (a laptop `dm-screen.sh start`) would fight over server.json."""
        info = screen_cli.server_info(self.sdir)
        if not info or (self.child and info.get("pid") == self.child.pid) or not _is_screen_server(info.get("pid")):
            return
        logger.warning("[%s] stopping a screen server this driver did not start (pid %s)", self.campaign, info["pid"])
        with contextlib.suppress(OSError):
            os.kill(info["pid"], signal.SIGTERM)
        for _ in range(30):
            if not screen_cli.server_info(self.sdir):
                break
            time.sleep(0.1)

    def start_child(self):
        self._stop_foreign_server()
        self.child = self.spawn(self.root, self.sdir, self.campaign, self.port)
        self.child_started = self.clock()
        self.child_reported = False
        logger.info("[%s] screen server pid %s on 127.0.0.1:%s", self.campaign, self.child.pid, self.port)

    async def stop_child(self):
        child, self.child = self.child, None
        if child is None or child.poll() is not None:
            return
        child.terminate()
        for _ in range(50):
            if child.poll() is not None:
                return
            await asyncio.sleep(0.1)
        logger.warning("[%s] screen server pid %s ignored SIGTERM: killing it", self.campaign, child.pid)
        child.kill()
        with contextlib.suppress(Exception):
            await asyncio.to_thread(child.wait, 5)

    async def check_child(self):
        """Config changes that touch the screen server, and a server that died (restarted with backoff)."""
        raw = online.read_json(online.config_path(self.root))
        if raw is not None:
            config = online.normalize(raw, self.campaign)
            if config["port"] != self.port or config["screen_restart"] != self.screen_restart_seen:
                logger.info("[%s] screen server restart (%s)", self.campaign,
                            "port %s" % config["port"] if config["port"] != self.port else "requested")
                self.port, self.screen_restart_seen = config["port"], config["screen_restart"]
                await self.stop_child()
                self.child_backoff = 1.0
                self.start_child()
                return
        now = self.clock()
        if self.child is not None and self.child.poll() is None:
            if now - self.child_started > 60:
                self.child_backoff = 1.0
            return
        if not self.child_reported:
            code = self.child.poll() if self.child is not None else None
            logger.error("[%s] screen server exited (code %s); restart in %.0fs", self.campaign, code, self.child_backoff)
            self.child_reported = True
            self.child_next_start = now + self.child_backoff
            self.child_backoff = min(self.child_backoff * 2, CHILD_BACKOFF_MAX)
        if now >= self.child_next_start:
            self.start_child()

    async def supervise(self):
        while True:
            await asyncio.sleep(self.settings.tick)
            try:
                if not self.child_lock.locked():
                    async with self.child_lock:
                        await self.check_child()
                self.write_status()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("supervisor tick failed")

    async def switch(self, name):
        """The new campaign's prompt and provider come first: when that fails the old campaign has lost nothing."""
        logger.info("[%s] switching the table to %s", self.campaign, name)
        old = self.provider
        if self.bridge is not None:     # a trailing hub call must not land in the new campaign
            await self.bridge.revoke()
        async with self.child_lock:
            await self.open_campaign(name, fresh=True, notice=SWITCHED)
            await self.stop_child()
            if old is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(old.close(), 10)
            self.start_child()
        self.write_status()

    async def renew(self):
        """A fresh master session on the same campaign (dm-play.sh new-session), for a session the API keeps refusing."""
        logger.info("[%s] a fresh master session was requested", self.campaign)
        old = self.provider
        try:
            await self.open_campaign(self.campaign, fresh=True)
        except Exception as exc:
            logger.exception("[%s] the fresh session did not start", self.campaign)
            self.last_error = f"new session failed: {type(exc).__name__}: {exc}"[:300]
            return
        if old is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(old.close(), 10)
        self.write_status()

    async def reconcile(self):
        """Between turns: pause, the campaign switch and a fresh session from world-state/online-<table>.json."""
        raw = online.read_json(online.config_path(self.root))
        if raw is None:
            return
        config = online.normalize(raw, self.campaign)
        self.paused = config["paused"]
        reset = config.get("session_reset", 0)
        target = config["campaign"]
        if target == self.campaign:
            self.bad_campaign = None
            if reset != self.session_reset_seen:
                self.session_reset_seen = reset
                await self.renew()
            return
        if target == self.bad_campaign and self.clock() < self.switch_retry_at:
            return
        try:
            name = online.check_campaign(target, self.root)
            if busy := online.other_table_with(name, self.root):   # a hand edit past dm-play.sh switch's check
                raise online.CampaignError(f"table {busy!r} plays {name}")
        except ValueError as exc:
            if self.bad_campaign != target:
                logger.error("[%s] switch refused: %s", self.campaign, exc)
                self.bad_campaign, self.last_error = target, f"switch refused: {exc}"
            return
        try:
            await self.switch(name)
        except Exception as exc:   # the current campaign plays on; the switch is tried again with a backoff
            again = self.bad_campaign == name
            self.switch_backoff = min(self.switch_backoff * 2, SWITCH_RETRY_MAX) if again else 5.0
            self.bad_campaign, self.switch_retry_at = name, self.clock() + self.switch_backoff
            self.last_error = f"switch to {name} failed: {type(exc).__name__}: {exc}"[:300]
            (logger.warning if again else logger.exception)("[%s] switch to %s failed, next try in %.0fs: %s",
                                                             self.campaign, name, self.switch_backoff, exc)
            return
        self.bad_campaign, self.session_reset_seen = None, reset   # the switch started a fresh session already
        if (self.last_error or "").startswith("switch"):
            self.last_error = None

    # ---- the loop

    async def step(self):
        await self.reconcile()
        now = self.clock()
        if self.paused:
            self.set_state("paused")
            return await asyncio.sleep(self.settings.tick)
        if now < self.retry_at and not self.hub_ready(now):   # a usage limit: nothing goes to the SDK master until its reset
            self.set_state("resting")
            return await asyncio.sleep(self.settings.tick)
        if self.capped(now):
            if not self.rest_posted:
                logger.warning("[%s] turn cap reached (%s this hour, %s today): actions wait", self.campaign,
                               self._turns_within(3600, now), self._turns_within(86400, now))
                self._activity(REST_LINE)
                self.rest_posted = True
            self.set_state("resting")
            return await asyncio.sleep(self.settings.tick)
        self.rest_posted = False
        self.set_state("error" if self.failed else "idle")
        cursor = screen_cli.read_cursor(self.sdir)
        notices = self.notices + self.carry     # a carry starts with its own [system] line
        self.notices, self.carry = [], []
        if notices:
            events = inbox.read_events(self.sdir, after_id=cursor)[: self.settings.max_events]
        else:
            s = self.settings
            events = await asyncio.to_thread(screen_cli.next_batch, self.sdir, cursor, s.settle, s.max_events, s.batch_timeout)
        if not events and not notices:
            return await self.idle_check()
        await self.play(notices, events)

    async def idle_check(self):
        if self.connected and self.clock() - self.last_used > self.settings.idle_disconnect:
            logger.info("[%s] idle for %.0f min: disconnecting the master (the session resumes on the next action)",
                        self.campaign, (self.clock() - self.last_used) / 60)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.provider.close(), 10)
            self.connected = False

    def hub_ready(self, now=None):
        return self.hub.hub and (self.clock() if now is None else now) >= self.hub_paused_until

    async def play(self, notices, events):
        """One batch: cursor first (after a crash the batch goes again once, as unanswered), then one master message
        (the hub master first in hub mode); make sure a turn came out."""
        if events:
            screen_cli.write_cursor(self.sdir, events[-1]["id"])
        lines = [*notices, *(inbox.format_line(e) for e in events)]
        logger.info("[%s] batch %s%s", self.campaign, [e["id"] for e in events] or "-",
                    f" + {len(notices)} notice lines" if notices else "")
        before = turn_id(self.sdir)
        if not self.hub_ready():
            return await self.sdk_turn(self._sdk_message(lines), lines, before)
        head = ([TAKEOVER] if self.hub_takeover else []) + ([HUB_CATCH_UP] if self.hub_behind else [])
        if await self.hub_turn("\n".join([*head, *lines]), before):
            return self._published("hub")
        if self.stopping:
            return
        self._activity(HUB_FAILED_LINE)
        if self.clock() < self.retry_at:    # the SDK master rests on a usage limit: the lines wait
            self.carry = self._carried(lines)
            return self.set_state("resting")
        return await self.sdk_turn(self._sdk_message(lines, HUB_FALLBACK), lines, before)

    def _sdk_message(self, lines, note=None):
        head = ([SDK_CATCH_UP] if self.sdk_behind else []) + ([note] if note else [])
        self.sdk_behind = False
        return "\n".join([*head, *lines])

    async def sdk_turn(self, message, lines, before):
        """The SDK master's turn: one follow-up when nothing was published, then the failure line; a usage limit
        carries the lines."""
        result = await self.send(message)
        if turn_id(self.sdir) > before:
            return self._published()
        if result.rate_limited:
            return self._rate_limited(result, lines)
        if self.stopping:
            return
        reason = "timed out" if result.timed_out else "failed" if result.error else None
        follow = NOT_PUBLISHED if not reason else f"[system] The previous turn {reason} before a turn was published. {PUBLISH}"
        logger.warning("[%s] no turn published (%s): one follow-up", self.campaign, result.error or "the master did not publish")
        second = await self.send(follow)
        if turn_id(self.sdir) > before:
            return self._published()
        if second.rate_limited:
            return self._rate_limited(second, lines)
        self.failed = True
        self.last_error = second.error or result.error or "the master answered without publishing a turn"
        logger.error("[%s] still no turn after the follow-up: %s", self.campaign, self.last_error)
        self._activity(FAILED_LINE)
        self.set_state("error")

    async def hub_turn(self, message, before):
        """One batch for the hub master under the campaign turn lock: POST the event with a fresh ticket, wait for
        a published turn up to the hub timeout, else revoke the ticket. True when the hub published."""
        stamp = self.clock()
        self.turn_times.append(stamp)
        self.last_turn_at = _now_iso()
        self.set_state("thinking")
        lock = CampaignTurnLock(self.campaign_dir)
        await lock.acquire_async()
        published, reason, started = False, None, time.monotonic()
        try:
            ticket = self.bridge.issue()
            payload = {"table": online.table_name(), "campaign": self.campaign, "turn": before, "ticket": ticket,
                       "message": message}
            ok, error = await asyncio.to_thread(self.poster, self.hub.webhook, payload)
            if not ok:
                await self.bridge.revoke()      # a POST that timed out may still have reached the hub
                with contextlib.suppress(ValueError):   # nothing was played: no turn for the caps
                    self.turn_times.remove(stamp)
                reason = f"post failed: {error}"
            else:
                self.hub_takeover = self.hub_behind = False
                deadline = started + self.hub.timeout
                while not self.stopping and time.monotonic() < deadline + self._hub_extension():
                    if turn_id(self.sdir) > before:
                        published = True
                        break
                    await asyncio.sleep(self.hub.poll)
                if not published:
                    await self.bridge.revoke()
                    # A turn the last running call published counts: that call finished before revoke() returned.
                    published = turn_id(self.sdir) > before
                    reason = None if published else "stopped" if self.stopping else f"no turn in {self.hub.timeout:.0f}s"
        except asyncio.CancelledError:
            self.bridge.ticket = None
            raise
        except Exception as exc:
            logger.exception("[%s] hub turn failed", self.campaign)
            with contextlib.suppress(Exception):
                await self.bridge.revoke()
            reason = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            lock.release()
            self.last_used = self.clock()
        duration = time.monotonic() - started
        if published:
            self.hub_fails, self.hub_last_result, self.hub_last_turn_at = 0, "published", _now_iso()
            logger.info("[%s] hub master published turn %s in %.1fs", self.campaign, turn_id(self.sdir), duration)
        else:
            self._hub_failed(reason)
        return published

    def _hub_extension(self):
        """The hub's time in slow tools (dm-art.sh) under this ticket, up to one tool timeout: a batch that opens
        a new act waits 1-5 minutes for its picture before the turn can come."""
        extension = getattr(self.bridge, "extension", None)
        return min(max(float(extension()), 0.0), TOOL_TIMEOUT) if extension else 0.0

    def _hub_failed(self, reason):
        self.hub_fails += 1
        self.hub_last_result = reason
        logger.warning("[%s] hub master failed (%s, %d in a row): the SDK master plays this batch", self.campaign,
                       reason, self.hub_fails)
        if self.hub_fails >= self.hub.fails:
            self.hub_paused_until = self.clock() + self.hub.pause
            logger.warning("[%s] hub master paused for %.0fs after %d failures", self.campaign, self.hub.pause, self.hub_fails)
            if self.hub_fails == self.hub.fails:    # one feed line per outage, not per probe after a pause
                self._activity(HUB_PAUSED_LINE)

    def _published(self, master="sdk"):
        if master == "hub":
            self.sdk_behind = True
        else:
            self.hub_behind = True
        self.failed = False
        self.set_state("idle")

    @staticmethod
    def _carried(lines):
        header = RESTARTED if RESTARTED in lines else CARRIED
        return [header, *[line for line in lines if line not in (CARRIED, RESTARTED)][-CARRY_MAX:]]

    def _rate_limited(self, result, lines):
        self.limit_streak += 1
        wait = float(result.retry_after) if result.retry_after else min(RATE_LIMIT_WAIT * 2 ** (self.limit_streak - 1), RATE_LIMIT_MAX)
        self.carry = self._carried(lines)
        self.retry_at = self.clock() + wait
        self.last_error = f"usage limit: {result.error}"
        logger.error("[%s] usage limit (%s): %d lines wait %.0fs", self.campaign, result.error, len(self.carry) - 1, wait)
        if self.limit_streak == 1:      # one feed line per rest, however many retries it takes
            self._activity(LIMIT_LINE)
        self.set_state("resting")

    async def send(self, message):
        """One master turn under the campaign turn lock, with a time limit; never raises (except cancellation)."""
        provider = self.provider
        stamp = self.clock()
        self.turn_times.append(stamp)
        self.last_turn_at = _now_iso()
        self.set_state("thinking")
        lock = CampaignTurnLock(self.campaign_dir)
        await lock.acquire_async()
        result = TurnResult()
        started = time.monotonic()
        task = asyncio.ensure_future(self._consume(provider, message, result))
        try:
            done, _ = await asyncio.wait({task}, timeout=self.settings.turn_timeout)
            if done:
                task.result()
            else:
                result.timed_out = True
                result.error = f"the turn ran over {self.settings.turn_timeout:.0f}s and was interrupted"
                logger.error("[%s] %s", self.campaign, result.error)
                await self._abort(task, provider)
        except asyncio.CancelledError:
            await self._abort(task, provider)
            raise
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            logger.exception("[%s] turn failed", self.campaign)
        finally:
            lock.release()
            duration = time.monotonic() - started
            self.last_used = self.clock()
            self._persist_session(provider)
            self._record_usage(provider, duration)
        if result.rate_limited:     # a refused message did no work: it must not use up the turn caps
            with contextlib.suppress(ValueError):
                self.turn_times.remove(stamp)
        else:
            self.limit_streak = 0
        reply = " ".join(" ".join(result.text).split())
        logger.info("[%s] turn %.1fs%s: %s", self.campaign, duration, f", error: {result.error}" if result.error else "", reply[:300] or "-")
        return result

    async def _consume(self, provider, message, result):
        self.connected = True
        async with contextlib.aclosing(provider.process_message(message, "", self.settings.model)) as events:
            async for event in events:
                self._persist_session(provider)
                if event.type == "text":
                    result.text.append(event.content)
                elif event.type == "tool_use":
                    logger.info("[%s] tool %s", self.campaign, event.content[:300])
                elif event.type == "error":
                    result.error = event.content
                    logger.error("[%s] master error: %s", self.campaign, event.content[:500])
                    limited, wait = usage_limit(event.content, self.clock())
                    if limited:
                        result.rate_limited, result.retry_after = True, wait
                elif event.type == "rate_limit":
                    # The base provider's retry_after takes any number as seconds ("5 hours" -> 5): read the text again.
                    _, wait = usage_limit(event.content, self.clock())
                    hinted = event.metadata.get("retry_after")
                    result.rate_limited, result.error = True, event.content
                    result.retry_after = wait or (clamp_wait(hinted) if isinstance(hinted, (int, float)) and hinted > 0 else None)
                elif event.type == "turn_end" and not event.metadata.get("ok", True):
                    result.error = result.error or event.content

    async def _abort(self, task, provider):
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
        # Within systemd's 30 s stop timeout together with the screen server's stop.
        with contextlib.suppress(Exception):
            await asyncio.wait_for(provider.interrupt(), 5)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(provider.close(), 10)
        self.connected = False

    def _persist_session(self, provider):
        session_id = getattr(provider, "session_id", None)
        if not session_id or session_id == self.persisted_session or provider is not self.provider:
            return
        try:
            save_runtime_session(self.sdir, runtime_id=RUNTIME, model_name=self.settings.model, session_id=session_id,
                                 filename=GM_SESSION)
            self.persisted_session = session_id
            logger.info("[%s] master session %s", self.campaign, session_id)
        except OSError:
            logger.exception("session id not saved")

    def _record_usage(self, provider, duration):
        try:
            usage = provider.get_turn_usage() if hasattr(provider, "get_turn_usage") else None
            record_usage(project_root=self.root, campaign=self.campaign, runtime=RUNTIME, model_id=self.settings.model,
                         usage=usage, duration_seconds=duration)
        except Exception:
            logger.exception("usage accounting failed")

    async def run(self):
        supervisor = None
        try:
            await self.start()
            supervisor = asyncio.create_task(self.supervise())
            while True:
                try:
                    await self.step()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:   # a broken file must not crash-loop the service; the screen stays up
                    logger.exception("[%s] driver step failed", self.campaign)
                    self.last_error = f"driver: {type(exc).__name__}: {exc}"[:300]
                    self.set_state("error")
                    await asyncio.sleep(5)
        finally:
            if supervisor is not None:
                supervisor.cancel()
                with contextlib.suppress(BaseException):
                    await supervisor
            await self.shutdown()

    async def shutdown(self):
        self.stopping = True
        if self.campaign is None:   # never started: nothing runs and no status to leave
            return
        logger.info("[%s] stopping: master and screen server", self.campaign)
        if self.provider is not None:
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(self.provider.close(), 10)
        with contextlib.suppress(BaseException):
            await self.stop_child()
        if self.bridge is not None:
            with contextlib.suppress(BaseException):
                await self.bridge.stop()
        self.set_state("offline")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="screen_driver", description=__doc__.splitlines()[0])
    ap.add_argument("--campaign", help=f"campaign for a new world-state/online-<table>.json (default {online.DEFAULT_CAMPAIGN})")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    driver = ScreenDriver(campaign=args.campaign)

    async def runner():
        loop, task = asyncio.get_running_loop(), asyncio.current_task()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, task.cancel)
        try:
            await driver.run()
        except asyncio.CancelledError:
            logger.info("stopped")

    try:
        asyncio.run(runner())
    except online.CampaignError as exc:   # a configured campaign that does not exist
        logger.error("%s", exc)
        return 1
    except Exception:                     # anything else with its traceback, so the journal names the broken file
        logger.exception("the driver stopped")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
