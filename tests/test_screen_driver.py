"""The online screen driver and its master provider, with a fake master, a fake screen server and no real CLI."""

import asyncio
import contextlib
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage, SystemMessage
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

import backend.providers.claude_screen as claude_screen
import backend.screen_driver as driver_module
from backend.providers.claude_screen import ScreenGMProvider, scrub_api_route_env
from backend.runtime import AgentEvent
from backend.runtime.session_store import load_runtime_session, save_runtime_session
from backend.runtime.turn_lock import try_campaign_turn_lock
from backend.hub_master import HubSettings
from backend.screen_driver import (CARRIED, FAILED_LINE, FRESH, GM_SESSION, HUB_CATCH_UP, HUB_FAILED_LINE, HUB_FALLBACK,
                                   HUB_PAUSED_LINE, LIMIT_LINE, NOT_PUBLISHED, REST_LINE, RESTARTED, SDK_CATCH_UP, SWITCHED,
                                   TAKEOVER, ScreenDriver, Settings, build_prompt, spawn_screen_server)
from lib.screen import activity, cli as screen_cli, inbox, masterlog, online

MODEL = "claude-sonnet-5-5"
TURN = {"blocks": ["<p>Дождь стучит по крыше.</p>"], "question": "Что делаете?", "options": ["Ждать"]}


# ---- fakes

class FakeClock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class FakeChild:
    pids = itertools.count(4000)

    def __init__(self, campaign, port):
        self.pid, self.campaign, self.port = next(self.pids), campaign, port
        self.code = None
        self.terminated = False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated, self.code = True, -15

    def kill(self):
        self.code = -9

    def wait(self, timeout=None):
        return self.code


def publish(provider, text="ok"):
    screen_cli.set_turn(provider.sdir, TURN)
    return [AgentEvent("text", text), AgentEvent("turn_end", "Turn completed", {"ok": True})]


class FakeProvider:
    """Plays a script: script(provider, message) returns events, or a coroutine that returns them."""

    def __init__(self, campaign, sdir, prompt_file, resume, script):
        self.campaign, self.sdir, self.prompt_file, self.resume = campaign, Path(sdir), Path(prompt_file), resume
        self.session_id = resume
        self.script = script
        self.messages = []
        self.interrupted = self.closed = 0

    async def process_message(self, message, system_prompt, model_name, mcp_servers=None):
        self.messages.append(message)
        self.session_id = self.session_id or f"sess-{self.campaign}"
        events = self.script(self, message)
        if asyncio.iscoroutine(events):
            events = await events
        for event in events:
            yield event

    async def interrupt(self):
        self.interrupted += 1
        return True

    async def close(self):
        self.closed += 1

    def get_turn_usage(self):
        return {"input_tokens": 100, "output_tokens": 20}


class Table:
    """A temp project with campaigns alpha and beta, a driver wired to fakes, and the records the fakes keep."""

    def __init__(self, root, script=publish, clock=None, **settings):
        self.root = root
        for name in ("alpha", "beta"):
            campaign = root / "world-state" / "campaigns" / name
            campaign.mkdir(parents=True, exist_ok=True)
            (campaign / "campaign-overview.json").write_text("{}", encoding="utf-8")
        self.script = script
        self.clock = clock or FakeClock()
        self.settings = Settings(**{"model": MODEL, "settle": 0.01, "batch_timeout": 0.05, "tick": 0.01,
                                    "turn_timeout": 5.0, **settings})
        self.providers, self.children, self.prompts = [], [], []

    def driver(self, campaign=None, **hub):
        def provider_factory(name, sdir, prompt_file, resume):
            provider = FakeProvider(name, sdir, prompt_file, resume, self.script)
            self.providers.append(provider)
            return provider

        def spawn(root, sdir, name, port):
            child = FakeChild(name, port)
            self.children.append(child)
            return child

        def prompt_builder(root, name, sdir):
            self.prompts.append(name)
            path = Path(sdir) / "gm-system-prompt.md"
            path.write_text(f"prompt for {name}", encoding="utf-8")
            return path

        return ScreenDriver(self.root, campaign=campaign, settings=self.settings, provider_factory=provider_factory,
                            spawn=spawn, prompt_builder=prompt_builder, clock=self.clock, **hub)

    def sdir(self, name="alpha"):
        return self.root / "world-state" / "campaigns" / name / "screen"

    def act(self, text, name="alpha", who="Катя"):
        return inbox.append_event(self.sdir(name), who, "button", text)

    def feed(self, name="alpha"):
        return [a["text"] for a in activity.read_activity(self.sdir(name))]

    def status(self):
        return online.read_status(self.root)


@pytest.fixture(autouse=True)
def no_config_override(monkeypatch):
    monkeypatch.delenv("DM_PLAY_CONFIG", raising=False)
    monkeypatch.delenv("DM_SCREEN_SPEND_FILE", raising=False)
    for key in ("DM_PLAY_MASTER", "DM_PLAY_HUB_WEBHOOK", "DM_PLAY_HUB_SOCKET"):
        monkeypatch.delenv(key, raising=False)


def run(coro):
    return asyncio.run(coro)


async def started(table, campaign="alpha", resume=None):
    if resume:
        save_runtime_session(table.sdir(campaign), runtime_id="claude", model_name=MODEL, session_id=resume, filename=GM_SESSION)
    driver = table.driver(campaign)
    await driver.start()
    return driver


# ---- delivery

def test_fresh_start_sends_the_opening_notice_then_batches(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table)
        await driver.step()
        table.act("1. Осмотреться")
        await driver.step()
        return driver

    driver = run(scenario())
    provider = table.providers[0]
    assert provider.resume is None and table.prompts == ["alpha"]
    assert provider.messages == [FRESH.format(name="alpha"), "[screen #1] Катя (button): 1. Осмотреться"]
    assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 1
    assert load_runtime_session(table.sdir(), GM_SESSION).session_id == "sess-alpha"
    status = table.status()
    assert status["state"] == "idle" and status["campaign"] == "alpha" and status["pid"] == os.getpid()
    assert status["session_id"] == "sess-alpha" and status["turns_hour"] == 2 and status["turns_day"] == 2
    assert status["port"] == online.DEFAULT_PORT and status["last_turn_at"] and status["last_error"] is None
    assert table.children[0].campaign == "alpha" and not table.children[0].terminated
    usage = [json.loads(line) for line in (tmp_path / "world-state/usage/game-turns.jsonl").read_text().splitlines()]
    assert [(u["campaign"], u["runtime"], u["model"], u["input_tokens"]) for u in usage] == [("alpha", "claude", MODEL, 100)] * 2


def test_cursor_is_written_before_sending_and_a_restart_answers_the_batch_once(tmp_path):
    """A driver killed mid-turn: the next one finds the delivered but unanswered actions and sends them once more."""
    seen = {}
    entered = asyncio.Event

    async def hang(provider, message):
        seen["cursor"] = screen_cli.read_cursor(provider.sdir)
        seen["entered"].set()
        await asyncio.sleep(30)
        return []

    table = Table(tmp_path, script=hang)

    async def first_life():
        seen["entered"] = entered()
        driver = await started(table, resume="sess-old")
        table.act("1. Открыть дверь")
        table.act("2. Позвать трактирщика", who="Миша")
        step = asyncio.ensure_future(driver.step())
        await asyncio.wait_for(seen["entered"].wait(), 5)
        step.cancel()   # the process dies mid-turn
        with pytest.raises(asyncio.CancelledError):
            await step

    run(first_life())
    assert seen["cursor"] == 2
    assert table.providers[0].messages == ["[screen #1] Катя (button): 1. Открыть дверь\n[screen #2] Миша (button): 2. Позвать трактирщика"]
    assert try_campaign_turn_lock(table.sdir().parent) is not None   # the lock went with the turn

    table.script = publish

    async def second_life():
        driver = await started(table)
        for _ in range(3):
            await driver.step()

    run(second_life())
    lines = "[screen #1] Катя (button): 1. Открыть дверь\n[screen #2] Миша (button): 2. Позвать трактирщика"
    assert table.providers[1].resume == "sess-old" and table.providers[1].messages == [f"{RESTARTED}\n{lines}"]
    assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 2

    run(second_life())                                  # answered now: a third start sends nothing
    assert table.providers[2].messages == []


def test_an_action_sent_during_a_turn_comes_in_the_next_batch(tmp_path):
    def script(provider, message):
        if "#1" in message:
            inbox.append_event(provider.sdir, "Миша", "text", "а я ухожу")   # a player acts while the master writes
        return publish(provider)

    table = Table(tmp_path, script=script)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Сесть")
        await driver.step()
        assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 1
        await driver.step()

    run(scenario())
    assert table.providers[0].messages == ["[screen #1] Катя (button): 1. Сесть", "[screen #2] Миша (text): а я ухожу"]
    assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 2


def test_batches_hold_at_most_six_actions_oldest_first(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        for n in range(8):
            table.act(f"действие {n + 1}")
        await driver.step()
        await driver.step()

    run(scenario())
    first, second = table.providers[0].messages
    assert [line.split("]")[0] for line in first.splitlines()] == [f"[screen #{n}" for n in range(1, 7)]
    assert [line.split("]")[0] for line in second.splitlines()] == ["[screen #7", "[screen #8"]


def test_old_actions_in_an_inbox_without_cursor_count_as_handled(tmp_path):
    table = Table(tmp_path)
    table.act("вчерашнее действие")

    async def scenario():
        driver = await started(table, resume="s1")
        await driver.step()

    run(scenario())
    assert screen_cli.read_cursor(table.sdir()) == 1 and table.providers[0].messages == []


def test_the_turn_lock_is_held_while_the_master_works(tmp_path):
    held = []

    def script(provider, message):
        held.append(try_campaign_turn_lock(provider.sdir.parent) is None)
        return publish(provider)

    table = Table(tmp_path, script=script)

    async def scenario():
        driver = await started(table)
        await driver.step()

    run(scenario())
    assert held == [True] and try_campaign_turn_lock(table.sdir().parent) is not None


# ---- caps and pause

def test_caps_keep_actions_pending_and_post_one_feed_line(tmp_path):
    table = Table(tmp_path, max_turns_hour=2)

    async def scenario():
        driver = await started(table)
        await driver.step()                 # opening notice: 1
        table.act("1. Пойти")
        await driver.step()                 # batch: 2, the cap is reached
        table.act("2. Ещё")
        table.act("3. И ещё")
        for _ in range(3):
            await driver.step()
        assert table.status()["state"] == "resting" and screen_cli.read_cursor(table.sdir()) == 1
        assert len(table.providers[0].messages) == 2

        restarted = table.driver()           # the window survives a restart
        await restarted.start()
        assert restarted.capped()
        table.clock.now += 3601
        await driver.step()

    run(scenario())
    assert table.feed().count(REST_LINE) == 1
    assert table.providers[0].messages[2] == "[screen #2] Катя (button): 2. Ещё\n[screen #3] Катя (button): 3. И ещё"


def test_daily_cap_counts_a_rolling_day(tmp_path):
    table = Table(tmp_path, max_turns_hour=0, max_turns_day=1)

    async def scenario():
        driver = await started(table)
        await driver.step()
        assert driver.capped()
        table.clock.now += 86_399
        assert driver.capped()
        table.clock.now += 2
        assert not driver.capped()

    run(scenario())


def test_pause_keeps_actions_pending_without_feed_lines(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        assert online.main(["pause"], root=tmp_path) == 0
        table.act("1. Подождать")
        for _ in range(3):
            await driver.step()
        assert table.status()["state"] == "paused" and table.providers[0].messages == []
        assert screen_cli.read_cursor(table.sdir()) == 0
        online.main(["resume"], root=tmp_path)
        await driver.step()

    run(scenario())
    assert table.feed() == [] and table.providers[0].messages == ["[screen #1] Катя (button): 1. Подождать"]


# ---- switch and screen server

def test_switch_restarts_the_server_and_starts_a_fresh_session_for_the_new_campaign(tmp_path):
    def script(provider, message):
        if "#1" in message:   # the master's last command of a farewell turn
            assert online.main(["switch", "beta"], root=tmp_path) == 0
        return publish(provider)

    table = Table(tmp_path, script=script)
    save_runtime_session(table.sdir("beta"), runtime_id="claude", model_name=MODEL, session_id="beta-stale", filename=GM_SESSION)

    async def scenario():
        driver = await started(table, resume="alpha-1")
        table.act("1. Да, в другую кампанию")
        await driver.step()   # the farewell turn finishes on alpha
        assert json.loads((table.sdir("alpha") / "turn.json").read_text())["id"] == 1
        await driver.step()   # reconcile: switch, then the notice turn on beta
        return driver

    driver = run(scenario())
    alpha, beta = table.providers
    assert alpha.closed >= 1 and beta.campaign == "beta" and beta.resume is None
    assert table.prompts == ["alpha", "beta"]
    assert [c.campaign for c in table.children] == ["alpha", "beta"] and table.children[0].terminated
    assert beta.messages == [SWITCHED.format(name="beta")]
    assert (table.sdir("beta") / "turn.json").is_file()
    assert load_runtime_session(table.sdir("beta"), GM_SESSION).session_id == "sess-beta"
    assert table.status()["campaign"] == "beta" and driver.campaign == "beta"


def test_switch_to_a_missing_campaign_is_refused(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        assert online.main(["switch", "nowhere"], root=tmp_path) == 1   # the CLI validates
        online.update_config(tmp_path, campaign="nowhere")                # a hand edit does not
        await driver.step()
        await driver.step()
        return driver

    driver = run(scenario())
    assert driver.campaign == "alpha" and len(table.children) == 1
    assert "nowhere" in driver.last_error


def test_screen_restart_and_a_dead_server_restart_the_child(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        assert online.main(["restart-screen"], root=tmp_path) == 0
        await driver.check_child()
        assert len(table.children) == 2 and table.children[0].terminated
        await driver.check_child()
        assert len(table.children) == 2                 # one restart per request

        table.children[1].code = 1                      # the server crashed
        await driver.check_child()
        assert len(table.children) == 2                 # backoff
        table.clock.now += 1.5
        await driver.check_child()
        assert len(table.children) == 3 and table.children[2].campaign == "alpha"

    run(scenario())


def test_supervisor_restarts_the_server_during_a_long_turn(tmp_path):
    async def slow(provider, message):
        online.main(["restart-screen"], root=tmp_path)
        await asyncio.sleep(0.2)
        return publish(provider)

    table = Table(tmp_path, script=slow)

    async def scenario():
        driver = await started(table)
        supervisor = asyncio.ensure_future(driver.supervise())
        await driver.step()
        supervisor.cancel()

    run(scenario())
    assert len(table.children) == 2 and table.children[0].terminated


def test_spawn_runs_the_screen_server_for_the_campaign(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(driver_module.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or "child")
    monkeypatch.setenv("DM_SCREEN_DAILY_CREDITS", "15000")
    sdir = tmp_path / "world-state" / "campaigns" / "alpha" / "screen"

    assert spawn_screen_server(tmp_path, sdir, "alpha", 18116) == "child"
    (args,), kw = calls[0]
    assert args == [sys.executable, "-m", "lib.screen.cli", "serve", "--port", "18116"] and kw["cwd"] == tmp_path
    assert kw["env"]["DM_SCREEN_DIR"] == str(sdir) and kw["env"]["DM_ACTIVE_CAMPAIGN"] == "alpha"
    assert kw["env"]["DM_SCREEN_DAILY_CREDITS"] == "15000" and kw["stdout"].name == str(sdir / "server.log")
    # one ledger for the table: a campaign switch must not start the day's speech budget again
    assert kw["env"]["DM_SCREEN_SPEND_FILE"] == str(tmp_path / "world-state" / "usage" / "screen-spend.json")


# ---- turns that go wrong

def test_an_unpublished_turn_gets_exactly_one_follow_up(tmp_path):
    table = Table(tmp_path, script=lambda provider, message: [AgentEvent("text", "готово")])

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Спеть")
        await driver.step()
        await driver.step()
        return driver

    driver = run(scenario())
    assert table.providers[0].messages == ["[screen #1] Катя (button): 1. Спеть", NOT_PUBLISHED]
    assert table.feed() == [FAILED_LINE] and table.status()["state"] == "error" and driver.last_error


def test_a_follow_up_that_publishes_clears_the_error(tmp_path):
    table = Table(tmp_path, script=lambda provider, message: publish(provider) if message == NOT_PUBLISHED else [])

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Спеть")
        await driver.step()

    run(scenario())
    assert len(table.providers[0].messages) == 2 and table.feed() == [] and table.status()["state"] == "idle"


def test_a_turn_over_the_time_limit_is_interrupted_and_followed_up(tmp_path):
    async def script(provider, message):
        if message.startswith("[screen"):
            await asyncio.sleep(30)
        return publish(provider)

    table = Table(tmp_path, script=script, turn_timeout=0.2)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Думать долго")
        await driver.step()
        return driver

    driver = run(scenario())
    provider = table.providers[0]
    assert provider.interrupted == 1 and provider.closed == 1
    assert provider.messages[1].startswith("[system] The previous turn timed out before a turn was published.")
    assert table.status()["state"] == "idle" and try_campaign_turn_lock(table.sdir().parent) is not None


def test_a_usage_limit_carries_the_actions_until_the_wait_ends(tmp_path):
    def script(provider, message):
        if len(provider.messages) == 1:
            return [AgentEvent("rate_limit", "usage limit reached", {"retry_after": 60})]
        return publish(provider)

    table = Table(tmp_path, script=script)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        await driver.step()
        await driver.step()
        assert table.status()["state"] == "resting" and len(table.providers[0].messages) == 1
        table.clock.now += 61
        await driver.step()

    run(scenario())
    assert table.providers[0].messages[1] == f"{CARRIED}\n[screen #1] Катя (button): 1. Бежать"
    assert table.feed() == [LIMIT_LINE] and table.status()["state"] == "idle"


def test_idle_master_is_disconnected_and_resumed_later(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Сидеть")
        await driver.step()
        table.clock.now += 19 * 60
        await driver.step()
        assert table.providers[0].closed == 0
        table.clock.now += 2 * 60
        await driver.step()
        assert table.providers[0].closed == 1 and not driver.connected
        table.act("2. Встать")
        await driver.step()

    run(scenario())
    assert len(table.providers) == 1 and len(table.providers[0].messages) == 2


def test_shutdown_stops_the_master_and_the_server(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="s1")
        task = asyncio.ensure_future(driver.run())   # run() calls start() again: one more provider and child
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert table.providers[-1].closed == 1 and table.children[-1].terminated
    assert table.status()["state"] == "offline"


def test_api_route_variables_are_removed_from_the_driver_environment(tmp_path, monkeypatch):
    for key in claude_screen.API_ROUTE_ENV:
        monkeypatch.setenv(key, "x")
    table = Table(tmp_path)
    run(started(table, resume="s1"))
    assert not [key for key in claude_screen.API_ROUTE_ENV if key in os.environ]
    assert scrub_api_route_env({"ANTHROPIC_API_KEY": "k", "HOME": "/h"}) == ["ANTHROPIC_API_KEY"]


def test_driver_imports_load_no_dotenv():
    """backend.config runs load_dotenv() on import, which would hand every .env key to the master's shell."""
    code = "import sys, backend.screen_driver, lib.screen.online; print('backend.config' in sys.modules, 'dotenv' in sys.modules)"
    done = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
    assert done.stdout.split() == ["False", "False"], done.stderr


# ---- the prompt file

def test_build_prompt_joins_rules_contract_handoff_and_context(tmp_path):
    infra = tmp_path / ".claude" / "additional" / "infrastructure"
    infra.mkdir(parents=True)
    (infra / "audio-direction.md").write_text("# Audio Direction", encoding="utf-8")
    campaign = tmp_path / "world-state" / "campaigns" / "alpha"
    campaign.mkdir(parents=True)
    (campaign / "session-handoff.md").write_text("# Session Handoff", encoding="utf-8")

    path = build_prompt(tmp_path, "alpha", campaign / "screen", base_prompt="# DM RULES", context="=== SESSION CONTEXT ===")

    text = path.read_text(encoding="utf-8")
    assert path == campaign / "screen" / "gm-system-prompt.md" and path.stat().st_mode & 0o777 == 0o600
    order = [text.index(p) for p in ("# DM RULES", "# Audio Direction", "# Session Handoff", "=== SESSION CONTEXT ===")]
    assert order == sorted(order) and "Online Table Contract" not in text   # a missing part is skipped

    (infra / "screen-driver-contract.md").write_text("# Online Table Contract", encoding="utf-8")
    text = build_prompt(tmp_path, "alpha", campaign / "screen", base_prompt="# DM RULES", context="").read_text()
    assert text.index("# Audio Direction") < text.index("# Online Table Contract") < text.index("# Session Handoff")


def test_session_context_failure_is_skipped(tmp_path):
    assert driver_module.session_context(tmp_path, "alpha", timeout=10) == ""   # no tools/ here: bash fails


# ---- the provider: CLI flags through the SDK's own command builder

def _command(options):
    return SubprocessCLITransport(prompt="", options=options)._build_command()


@pytest.fixture
def provider_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_screen, "_installed_cli_path", lambda: "/usr/bin/claude")
    prompt = tmp_path / "screen" / "gm-system-prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("x" * 150_000, encoding="utf-8")   # over one argv string's 128 KiB

    def make(resume=None, **kw):
        return ScreenGMProvider(tmp_path, MODEL, "alpha", prompt_file=prompt, screen_dir=prompt.parent, effort="medium",
                                resume_session_id=resume, **kw)

    make.prompt = prompt
    return make


@pytest.mark.parametrize("resume", [None, "sess-42"])
def test_cli_command_appends_the_prompt_file_on_fresh_and_resumed_sessions(provider_factory, resume):
    provider = provider_factory(resume)
    command = _command(provider._make_options(MODEL, "IGNORED INLINE PROMPT", None))

    flag = command.index("--append-system-prompt-file")
    assert command[flag + 1] == str(provider_factory.prompt.resolve())
    assert "--system-prompt" not in command and "--append-system-prompt" not in command
    assert "IGNORED INLINE PROMPT" not in command and len(" ".join(command)) < 10_000
    assert "--strict-mcp-config" in command and "--setting-sources=project" in command
    assert command[command.index("--permission-mode") + 1] == "bypassPermissions"
    assert command[command.index("--model") + 1] == MODEL and command[command.index("--effort") + 1] == "medium"
    assert command[command.index("--max-turns") + 1] == "60" and command[0] == "/usr/bin/claude"
    assert "--tools" not in command and "--allowedTools" not in command and "--mcp-config" not in command
    assert [c for c in command if c.startswith("--resume")] == ([f"--resume={resume}"] if resume else [])


def test_cli_environment_keeps_the_subscription_route(provider_factory, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    provider = provider_factory(environment={"ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "u", "KEEP": "1"})
    env = provider._make_options(MODEL, "", None).env

    assert not [k for k in claude_screen.API_ROUTE_ENV if k in env]
    assert env["KEEP"] == "1" and env["HTTPS_PROXY"] == "http://proxy:3128"
    assert env["DM_ACTIVE_CAMPAIGN"] == "alpha" and env["DM_SCREEN_DIR"] == str(provider_factory.prompt.parent)
    assert env["DM_SCREEN_AUTOSTART"] == "0" and env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false" and env["DISABLE_AUTOUPDATER"] == "1"


class FakeClient:
    def __init__(self, options, fail=None):
        self.options, self.fail = options, fail

    async def connect(self):
        if self.fail:
            raise RuntimeError(self.fail)
        self.connected = True

    async def query(self, message):
        self.message = message

    async def receive_messages(self):
        yield SystemMessage(subtype="init", data={"session_id": "s-new", "model": MODEL, "tools": ["Bash", "Read"],
                                                  "mcp_servers": [], "apiKeySource": "none", "permissionMode": "bypassPermissions"})
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                            session_id="s-new", usage={"input_tokens": 5})

    async def get_context_usage(self):
        return None

    async def disconnect(self):
        self.disconnected = True


def test_a_stale_resume_starts_fresh_and_the_init_message_is_logged(provider_factory, caplog):
    clients = []

    def factory(options):
        stale = "Claude Code returned an error result: No conversation found with session ID: gone (exit code: 1)"
        client = FakeClient(options, fail=stale if options.resume else None)
        clients.append(client)
        return client

    provider = provider_factory("gone", client_factory=factory)

    async def scenario():
        return [e.type async for e in provider.process_message("[screen #1] Катя (button): x", "", MODEL)]

    caplog.set_level("INFO", logger="backend.providers.claude_screen")
    assert run(scenario()) == ["turn_end"]
    assert [c.options.resume for c in clients] == ["gone", None]
    assert getattr(clients[0], "disconnected", False)   # the failed CLI was stopped
    assert "--append-system-prompt-file" in _command(clients[1].options)
    assert provider.session_id == "s-new" and provider.get_turn_usage() == {"input_tokens": 5}
    assert provider.init_info["tools"] == ["Bash", "Read"]
    assert any("2 tools [Bash, Read]" in r.getMessage() and "key source none" in r.getMessage() for r in caplog.records)


def test_usage_limit_reported_as_an_error_result_is_classified():
    now = 1_800_000_000.0
    assert driver_module.usage_limit("Claude AI usage limit reached|1800000600", now) == (True, 600.0)
    assert driver_module.usage_limit("You've hit your limit · resets 3pm", now) == (True, None)
    assert driver_module.usage_limit("API Error: 429 Too Many Requests, retry-after: 30", now) == (True, 60.0)
    assert driver_module.usage_limit("API Error: 429 Too Many Requests, try again in 5 hours", now) == (True, 18000.0)
    assert driver_module.usage_limit("rate limit: try again in 30 minutes", now) == (True, 1800.0)
    assert driver_module.usage_limit("Overloaded. Please wait 2 min", now) == (True, 120.0)
    assert driver_module.usage_limit("usage limit, try again in 90s", now) == (True, 90.0)
    assert driver_module.usage_limit("usage limit, try again in 40 hours", now) == (True, 6 * 3600.0)
    assert driver_module.usage_limit("Command failed with exit code 1", now) == (False, None)
    assert driver_module.usage_limit("[screen #429] text", now) == (False, None)


def test_a_limit_error_result_waits_instead_of_following_up(tmp_path):
    def script(provider, message):
        if len(provider.messages) == 1:
            return [AgentEvent("error", "Claude AI usage limit reached|1800000900"), AgentEvent("turn_end", "Turn failed", {"ok": False})]
        return publish(provider)

    table = Table(tmp_path, script=script)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        await driver.step()
        assert driver.retry_at == table.clock.now + 900
        table.clock.now += 901
        await driver.step()

    run(scenario())
    assert table.providers[0].messages == ["[screen #1] Катя (button): 1. Бежать", f"{CARRIED}\n[screen #1] Катя (button): 1. Бежать"]


def test_a_broken_inbox_line_does_not_stop_the_driver(tmp_path, monkeypatch):
    table = Table(tmp_path)
    monkeypatch.setattr(driver_module.asyncio, "sleep", _fast_sleep)

    async def scenario():
        driver = await started(table, resume="s1")
        (table.sdir() / "inbox.jsonl").write_text("{broken\n", encoding="utf-8")
        task = asyncio.ensure_future(driver.run())
        for _ in range(200):
            await _real_sleep(0.01)
            if (table.status() or {}).get("state") == "error":
                break
        (table.sdir() / "inbox.jsonl").unlink()
        table.act("1. Дальше")
        for _ in range(300):
            await _real_sleep(0.01)
            if table.providers[-1].messages:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return driver

    driver = run(scenario())
    assert "JSONDecodeError" in driver.last_error
    assert table.providers[-1].messages == ["[screen #1] Катя (button): 1. Дальше"]


_real_sleep = asyncio.sleep


async def _fast_sleep(delay, *args):
    await _real_sleep(min(delay, 0.01), *args)


def test_the_real_screen_server_runs_as_the_child_and_shows_the_master_state(tmp_path):
    """No master: the driver's spawn starts the real server, the page state carries the status file, SIGTERM stops it."""
    import time
    import urllib.request

    campaign = tmp_path / "world-state" / "campaigns" / "alpha"
    campaign.mkdir(parents=True)
    (campaign / "campaign-overview.json").write_text("{}", encoding="utf-8")
    sdir = campaign / "screen"
    online.write_status({"pid": os.getpid(), "campaign": "alpha", "state": "thinking", "last_error": None}, tmp_path)
    child = spawn_screen_server(driver_module.PROJECT_ROOT, sdir, "alpha", 0)
    try:
        for _ in range(100):
            info = screen_cli.server_info(sdir)
            if info:
                break
            time.sleep(0.1)
        assert info and info["pid"] == child.pid, (sdir / "server.log").read_text(errors="replace")
        request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/state", headers={"X-Screen-Token": info["token"]})
        with urllib.request.urlopen(request, timeout=5) as response:
            state = json.loads(response.read())
        assert state["master"] == {"state": "thinking", "last_error": None}
    finally:
        child.terminate()
        child.wait(10)
    assert not (sdir / "server.json").exists()


FAKE_CLI = r'''#!{python}
import json, os, sys
if "-v" in sys.argv or "--version" in sys.argv:
    print("2.1.310 (Claude Code)")
    sys.exit(0)
keys = ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "DM_ACTIVE_CAMPAIGN", "DM_SCREEN_DIR", "DM_SCREEN_AUTOSTART",
        "ENABLE_CLAUDEAI_MCP_SERVERS", "DISABLE_AUTOUPDATER", "CLAUDE_CODE_ENTRYPOINT"]
with open({record!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": {{k: os.environ.get(k) for k in keys}}}}) + "\n")

def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "control_request":
        out({{"type": "control_response", "response": {{"subtype": "success", "request_id": msg["request_id"], "response": {{}}}}}})
    elif msg.get("type") == "user":
        out({{"type": "system", "subtype": "init", "session_id": "fake-1", "model": "claude-sonnet-5-5", "tools": ["Bash", "Edit"],
             "mcp_servers": [], "apiKeySource": "none", "permissionMode": "bypassPermissions", "claude_code_version": "2.1.310"}})
        out({{"type": "assistant", "message": {{"role": "assistant", "model": "claude-sonnet-5-5",
             "content": [{{"type": "text", "text": "turn published"}}]}}, "parent_tool_use_id": None, "session_id": "fake-1"}})
        out({{"type": "result", "subtype": "success", "duration_ms": 5, "duration_api_ms": 3, "is_error": False, "num_turns": 1,
             "session_id": "fake-1", "usage": {{"input_tokens": 7, "output_tokens": 3}}}})
'''


def test_provider_through_the_real_sdk_transport_against_a_fake_cli(tmp_path, monkeypatch, caplog):
    """The SDK's own spawn and handshake: argv, environment, init log, session id and usage, twice (fresh, resume)."""
    record = tmp_path / "cli-calls.jsonl"
    cli = tmp_path / "claude"
    cli.write_text(FAKE_CLI.format(python=sys.executable, record=str(record)), encoding="utf-8")
    cli.chmod(0o755)
    monkeypatch.setattr(claude_screen, "_installed_cli_path", lambda: str(cli))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-the-cli")
    prompt = tmp_path / "screen" / "gm-system-prompt.md"
    prompt.parent.mkdir()
    prompt.write_text("x" * 150_000, encoding="utf-8")
    provider = ScreenGMProvider(tmp_path, MODEL, "alpha", prompt_file=prompt, screen_dir=prompt.parent, effort="medium")
    caplog.set_level("INFO", logger="backend.providers.claude_screen")

    async def turn(text):
        events = [e async for e in provider.process_message(text, "", MODEL)]
        await provider.close()
        return events

    first = run(turn("[screen #1] Катя (button): 1. Войти"))
    second = run(turn("[screen #2] Катя (button): 2. Сесть"))

    assert [e.type for e in first] == ["text", "turn_end"] and first[0].content == "turn published"
    assert [e.type for e in second] == ["text", "turn_end"]
    assert provider.session_id == "fake-1" and provider.get_turn_usage() == {"input_tokens": 7, "output_tokens": 3}
    calls = [json.loads(line) for line in record.read_text().splitlines()]
    assert len(calls) == 2
    for call, resume in zip(calls, [None, "fake-1"]):
        argv = call["argv"]
        assert argv[argv.index("--append-system-prompt-file") + 1] == str(prompt.resolve())
        assert "--system-prompt" not in argv and "--strict-mcp-config" in argv and "--setting-sources=project" in argv
        assert [a for a in argv if a.startswith("--resume")] == ([f"--resume={resume}"] if resume else [])
        assert call["cwd"] == str(tmp_path.resolve())
        env = call["env"]
        assert env["ANTHROPIC_API_KEY"] is None and env["DM_ACTIVE_CAMPAIGN"] == "alpha"
        assert env["DM_SCREEN_DIR"] == str(prompt.parent) and env["DM_SCREEN_AUTOSTART"] == "0"
        assert env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false" and env["DISABLE_AUTOUPDATER"] == "1"
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert any("2 tools [Bash, Edit]" in r.getMessage() for r in caplog.records)


PUBLISHING_CLI = r'''#!{python}
import json, os, subprocess, sys
if "-v" in sys.argv or "--version" in sys.argv:
    print("2.1.310 (Claude Code)")
    sys.exit(0)
with open({record!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "screen": os.environ.get("DM_SCREEN_DIR"),
                        "autostart": os.environ.get("DM_SCREEN_AUTOSTART")}}) + "\n")

def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "control_request":
        out({{"type": "control_response", "response": {{"subtype": "success", "request_id": msg["request_id"], "response": {{}}}}}})
    elif msg.get("type") == "user":
        text = msg["message"]["content"]
        text = text if isinstance(text, str) else json.dumps(text)
        turn = os.path.join(os.environ["DM_SCREEN_DIR"], "next-turn.json")
        with open(turn, "w") as f:
            json.dump({{"blocks": ["<p>" + text.splitlines()[-1].replace("<", "&lt;")[:200] + "</p>"], "question": "?", "options": ["a"]}}, f)
        done = subprocess.run([sys.executable, "-m", "lib.screen.cli", "turn", "--file", turn], cwd={repo!r}, capture_output=True, text=True)
        out({{"type": "assistant", "message": {{"role": "assistant", "model": "m", "content": [{{"type": "text", "text": done.stdout + done.stderr}}]}},
             "parent_tool_use_id": None, "session_id": "e2e-1"}})
        out({{"type": "result", "subtype": "success", "duration_ms": 5, "duration_api_ms": 3, "is_error": False, "num_turns": 1,
             "session_id": "e2e-1", "usage": {{"input_tokens": 7, "output_tokens": 3}}}})
'''


def test_end_to_end_driver_with_the_real_provider_server_and_a_publishing_cli(tmp_path, monkeypatch):
    record = tmp_path / "cli-calls.jsonl"
    cli = tmp_path / "claude"
    cli.write_text(PUBLISHING_CLI.format(python=sys.executable, record=str(record), repo=str(driver_module.PROJECT_ROOT)), encoding="utf-8")
    cli.chmod(0o755)
    monkeypatch.setattr(claude_screen, "_installed_cli_path", lambda: str(cli))
    campaign = tmp_path / "world-state" / "campaigns" / "alpha"
    campaign.mkdir(parents=True)
    (campaign / "campaign-overview.json").write_text("{}", encoding="utf-8")
    sdir = campaign / "screen"
    online.write_json(online.config_path(tmp_path), {"campaign": "alpha", "port": 0})

    def prompt_builder(root, name, screen):
        return build_prompt(root, name, screen, base_prompt="# DM RULES", context="")

    driver = ScreenDriver(tmp_path, settings=Settings(model=MODEL, settle=0.05, batch_timeout=0.1, tick=0.05, turn_timeout=60),
                          prompt_builder=prompt_builder)

    async def until(check, seconds=30):
        for _ in range(int(seconds / 0.05)):
            if check():
                return True
            await asyncio.sleep(0.05)
        raise AssertionError((sdir / "server.log").read_text(errors="replace") if (sdir / "server.log").exists() else "timeout")

    async def scenario():
        task = asyncio.ensure_future(driver.run())
        try:
            await until(lambda: turn_of(sdir).get("id") == 1)              # the opening turn
            assert screen_cli.server_info(sdir)["pid"] == driver.child.pid
            inbox.append_event(sdir, "Катя", "button", "1. Войти в таверну")
            await until(lambda: turn_of(sdir).get("id") == 2)
            await until(lambda: (online.read_status(tmp_path) or {}).get("state") == "idle")
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    run(scenario())
    second = turn_of(sdir)
    assert second["answered"] == 1 and "1. Войти в таверну" in second["blocks"][0]
    calls = [json.loads(line) for line in record.read_text().splitlines()]
    assert len(calls) == 1 and calls[0]["screen"] == str(sdir) and calls[0]["autostart"] == "0"   # one CLI for both turns
    assert "--append-system-prompt-file" in calls[0]["argv"]
    assert load_runtime_session(sdir, GM_SESSION).session_id == "e2e-1"
    assert not (sdir / "server.json").exists() and online.read_status(tmp_path)["state"] == "offline"
    assert not list(sdir.glob("chrome-profile"))   # no browser was opened


def turn_of(sdir):
    return online.read_json(sdir / "turn.json") or {}


def test_a_failed_switch_keeps_the_old_campaign_and_is_retried(tmp_path):
    table = Table(tmp_path)
    builder = {"fail": True}

    async def scenario():
        driver = await started(table, resume="s1")
        build = driver.prompt_builder

        def flaky(root, name, sdir):
            if name == "beta" and builder["fail"]:
                raise OSError("disk full")
            return build(root, name, sdir)

        driver.prompt_builder = flaky
        online.main(["switch", "beta"], root=tmp_path)
        table.act("1. Пока играем здесь")
        await driver.step()                              # the switch fails, alpha plays on
        assert driver.campaign == "alpha" and driver.provider is table.providers[0] and "disk full" in driver.last_error
        assert table.providers[0].closed == 0 and not table.children[0].terminated and len(table.children) == 1
        assert table.providers[0].messages == ["[screen #1] Катя (button): 1. Пока играем здесь"]
        builder["fail"] = False
        await driver.step()                              # not before the backoff
        assert driver.campaign == "alpha"
        table.clock.now += 6
        await driver.step()
        return driver

    driver = run(scenario())
    assert driver.campaign == "beta" and table.providers[-1].messages == [SWITCHED.format(name="beta")]
    assert table.providers[0].closed == 1 and table.children[0].terminated and driver.last_error is None


def test_the_driver_process_exits_cleanly_on_a_missing_campaign(tmp_path):
    """python -m backend.screen_driver: a configured campaign that does not exist is a clear error and leaves no files."""
    status = online.status_path(driver_module.PROJECT_ROOT)
    before = status.read_bytes() if status.exists() else None
    config = tmp_path / "table.json"
    config.write_text(json.dumps({"campaign": "no-such-campaign-here", "port": 0}), encoding="utf-8")
    env = {**os.environ, "DM_PLAY_CONFIG": str(config)}
    done = subprocess.run([sys.executable, "-m", "backend.screen_driver"], cwd=driver_module.PROJECT_ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 1 and "no campaign 'no-such-campaign-here'" in done.stderr
    assert (status.read_bytes() if status.exists() else None) == before


# ---- usage limits, restarts and recovery

def test_usage_limit_retries_use_no_turn_cap_and_post_one_feed_line(tmp_path):
    """A subscription limit with no reset time: waits double up to an hour, no turn is counted, one feed line."""
    table = Table(tmp_path, max_turns_hour=3, script=lambda provider, message: [
        AgentEvent("error", "You've hit your limit · resets 3pm"), AgentEvent("turn_end", "Turn failed", {"ok": False})])

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        waits = []
        for _ in range(6):
            await driver.step()
            waits.append(round(driver.retry_at - table.clock.now))
            table.clock.now = driver.retry_at + 1
        return driver, waits

    driver, waits = run(scenario())
    assert waits == [300, 600, 1200, 2400, 3600, 3600]
    assert len(table.providers[0].messages) == 6 and table.status()["turns_day"] == 0 and not driver.capped()
    assert table.feed() == [LIMIT_LINE]
    assert all(m == f"{CARRIED}\n[screen #1] Катя (button): 1. Бежать" for m in table.providers[0].messages[1:])


def test_a_limit_event_reads_the_unit_of_its_wait(tmp_path):
    """The base provider reads 'try again in 5 hours' as 5 seconds; the driver reads the text again."""
    table = Table(tmp_path, script=lambda provider, message: [
        AgentEvent("rate_limit", "API Error: 429 Too Many Requests, try again in 5 hours", {"retry_after": 5})])

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        await driver.step()
        return driver

    driver = run(scenario())
    assert driver.retry_at == table.clock.now + 5 * 3600


def test_a_short_unit_less_limit_hint_waits_at_least_a_minute(tmp_path):
    table = Table(tmp_path, script=lambda provider, message: [AgentEvent("rate_limit", "429", {"retry_after": 5})])

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        await driver.step()
        return driver

    assert run(scenario()).retry_at == table.clock.now + 60


def test_a_restart_during_a_usage_limit_rest_keeps_resting_then_answers(tmp_path):
    calls = []

    def script(provider, message):
        calls.append(message)
        if len(calls) == 1:
            return [AgentEvent("error", "Claude AI usage limit reached|1800000900"), AgentEvent("turn_end", "Turn failed", {"ok": False})]
        return publish(provider)

    table = Table(tmp_path, script=script)

    async def first_life():
        driver = await started(table, resume="s1")
        table.act("1. Бежать")
        await driver.step()
        assert table.status()["retry_at"] == 1800000900

    async def second_life():
        driver = await started(table)
        await driver.step()
        assert table.status()["state"] == "resting" and len(calls) == 1
        table.clock.now += 901
        await driver.step()

    run(first_life())
    run(second_life())
    assert calls[1] == f"{RESTARTED}\n[screen #1] Катя (button): 1. Бежать" and table.feed() == [LIMIT_LINE]
    assert table.status()["state"] == "idle" and table.status()["retry_at"] is None


def test_new_session_starts_a_fresh_master_on_the_same_campaign(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table, resume="stuck-1")
        assert online.main(["new-session"], root=tmp_path) == 0
        await driver.step()
        return driver

    driver = run(scenario())
    old, new = table.providers
    assert old.closed == 1 and new.resume is None and new.campaign == "alpha" and driver.campaign == "alpha"
    assert new.messages == [FRESH.format(name="alpha")] and len(table.children) == 1 and not table.children[0].terminated
    assert load_runtime_session(table.sdir(), GM_SESSION).session_id == "sess-alpha"


def test_the_session_notices_keep_the_act_and_ask_for_library_music():
    for notice in (FRESH, SWITCHED):
        assert "keeps the current act" in notice and "tools/dm-art.sh" in notice
        assert "audio.music" in notice and '"generate": false' in notice


def test_a_crash_outside_the_campaign_check_is_logged_with_its_traceback(monkeypatch, caplog):
    async def broken(self):
        raise RuntimeError("torn inbox line")

    monkeypatch.setattr(ScreenDriver, "run", broken)
    monkeypatch.setattr(driver_module.logging, "basicConfig", lambda **kw: None)
    caplog.set_level("ERROR", logger="dnd-play")

    assert driver_module.main([]) == 1
    record = next(r for r in caplog.records if "the driver stopped" in r.getMessage())
    assert record.exc_info and "torn inbox line" in str(record.exc_info[1])


class CutClient(FakeClient):
    """The CLI streams the start of a turn, then dies (OOM kill)."""

    queries = 0

    async def query(self, message):
        CutClient.queries += 1

    async def receive_messages(self):
        from claude_agent_sdk import AssistantMessage, TextBlock
        yield AssistantMessage(content=[TextBlock(text="Урон нанесён")], model=MODEL)
        raise RuntimeError("Command failed with exit code 137")


def test_a_cli_lost_mid_turn_is_not_sent_the_message_again(provider_factory, monkeypatch):
    monkeypatch.setattr(claude_screen.asyncio, "sleep", _fast_sleep)
    CutClient.queries = 0
    provider = provider_factory("s1", client_factory=lambda options: CutClient(options))

    async def scenario():
        return [(e.type, e.content) async for e in provider.process_message("[screen #1] Катя (button): удар", "", MODEL)]

    events = run(scenario())
    assert CutClient.queries == 1
    assert [t for t, _ in events] == ["text", "error", "turn_end"] and "not sent again" in events[1][1]


def test_a_cli_that_fails_before_working_is_still_retried(provider_factory, monkeypatch):
    monkeypatch.setattr(claude_screen.asyncio, "sleep", _fast_sleep)
    clients = []

    def factory(options):
        client = FakeClient(options, fail="Command failed with exit code 1" if not clients else None)
        clients.append(client)
        return client

    provider = provider_factory(client_factory=factory)

    async def scenario():
        return [e.type async for e in provider.process_message("[screen #1] Катя (button): x", "", MODEL)]

    assert run(scenario()) == ["turn_end"] and len(clients) == 2


# ---- the hub master (DM_PLAY_MASTER=hub, backend/hub_master.py)

WEBHOOK = "https://hub.example/hooks/SECRET-TOKEN"


class FakeBridge:
    def __init__(self, hub, path, root, table, context):
        self.hub, self.path, self.table, self.context = hub, path, table, context
        self.ticket, self.tickets, self.revoked = None, [], 0
        self.started = self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    def issue(self):
        self.ticket = f"ticket-{len(self.tickets) + 1}"
        self.tickets.append(self.ticket)
        return self.ticket

    def extension(self):
        return self.hub.extension

    async def revoke(self):
        self.revoked += 1
        self.ticket = None
        if self.hub.on_revoke:      # the last running call of the hub master finishes inside revoke()
            self.hub.on_revoke(self)


def hub_publishes(hub, payload):
    screen_cli.set_turn(hub.bridge.context()["sdir"], TURN)
    return True, None


def hub_silent(hub, payload):
    return True, None


def hub_down(hub, payload):
    return False, "HTTP 502"


class Hub:
    """The hub side of a driver test: settings, a webhook poster that plays a script per batch, the bridge."""

    def __init__(self, *plays, timeout=0.05, fails=2, pause=900.0, on_revoke=None, extension=0.0):
        self.settings = HubSettings(master="hub", webhook=WEBHOOK, timeout=timeout, fails=fails, pause=pause,
                                    socket=Path("/unused/hub.sock"), poll=0.01)
        self.plays = list(plays) or [hub_publishes]
        self.on_revoke = on_revoke
        self.extension = extension
        self.payloads, self.bridges, self.locked = [], [], []

    @property
    def bridge(self):
        return self.bridges[-1]

    def poster(self, url, payload):
        assert url == WEBHOOK
        self.payloads.append(payload)
        self.locked.append(try_campaign_turn_lock(self.bridge.context()["sdir"].parent) is None)
        play = self.plays.pop(0) if len(self.plays) > 1 else self.plays[0]
        return play(self, payload)

    def factory(self, path, root, table, context):
        self.bridges.append(FakeBridge(self, path, root, table, context))
        return self.bridge

    def kwargs(self):
        return {"hub": self.settings, "poster": self.poster, "bridge_factory": self.factory}


async def hub_started(table, hub, previous=None, resume=None):
    if previous is not None:
        online.write_status(previous, table.root)
    if resume:
        save_runtime_session(table.sdir(), runtime_id="claude", model_name=MODEL, session_id=resume, filename=GM_SESSION)
    driver = table.driver("alpha", **hub.kwargs())
    await driver.start()
    return driver


def line(n, text):
    return f"[screen #{n}] Катя (button): {text}"


def test_hub_mode_the_hub_publishes_and_the_sdk_master_is_never_called(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_publishes)

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Осмотреться")
        await driver.step()
        table.act("2. Идти")
        await driver.step()
        status = table.status()
        await driver.shutdown()
        return status

    status = run(scenario())
    assert table.providers[0].messages == []
    first, second = hub.payloads
    assert {k: first[k] for k in ("table", "campaign", "turn", "ticket")} == {"table": "play", "campaign": "alpha", "turn": 0, "ticket": "ticket-1"}
    assert first["message"].split("\n") == [TAKEOVER, HUB_CATCH_UP, FRESH.format(name="alpha"), line(1, "1. Осмотреться")]
    assert second == {"table": "play", "campaign": "alpha", "turn": 1, "ticket": "ticket-2", "message": line(2, "2. Идти")}
    assert hub.locked == [True, True] and hub.bridge.revoked == 0 and hub.bridge.started and hub.bridge.stopped
    assert status["master"] == "hub" and status["state"] == "idle" and status["turns_day"] == 2
    assert status["hub"]["fails"] == 0 and status["hub"]["last_result"] == "published" and status["hub"]["last_turn_at"]
    assert status["hub"]["paused_until"] is None and table.feed() == []
    assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 2
    assert not (tmp_path / "world-state/usage/game-turns.jsonl").exists()   # a hub turn reports no usage


def test_a_hub_timeout_revokes_the_ticket_and_the_sdk_master_plays_the_batch(tmp_path):
    hub = Hub(hub_silent)
    seen = []

    def sdk(provider, message):
        seen.append(hub.bridge.ticket)
        return publish(provider)

    table = Table(tmp_path, script=sdk)

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Осмотреться")
        await driver.step()

    run(scenario())
    assert hub.bridge.revoked == 1 and seen == [None]
    assert table.providers[0].messages == ["\n".join([HUB_FALLBACK, FRESH.format(name="alpha"), line(1, "1. Осмотреться")])]
    assert table.feed() == [HUB_FAILED_LINE]
    status = table.status()
    assert status["state"] == "idle" and status["hub"]["fails"] == 1 and status["hub"]["last_result"] == "no turn in 0s"
    assert json.loads((table.sdir() / "turn.json").read_text())["answered"] == 1


def test_a_failed_post_falls_back_at_once(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_down, timeout=30)

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Осмотреться")
        started = time.monotonic()
        await driver.step()
        return time.monotonic() - started

    assert run(scenario()) < 5
    assert table.providers[0].messages[0].startswith(HUB_FALLBACK + "\n")
    status = table.status()
    assert status["hub"]["last_result"] == "post failed: HTTP 502" and hub.bridge.revoked == 1
    assert status["turns_day"] == 1     # the failed POST played nothing: only the SDK turn counts


def test_two_hub_failures_pause_the_hub_then_it_plays_again(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_down, hub_silent, hub_publishes, pause=900)

    async def scenario():
        driver = await hub_started(table, hub, resume="s-old")
        for n in (1, 2, 3):
            table.act(f"{n}. Ход")
            await driver.step()
        paused = table.status()
        table.clock.now += 901
        table.act("4. Ход")
        await driver.step()
        return paused, table.status()

    paused, after = run(scenario())
    messages = table.providers[0].messages
    assert len(hub.payloads) == 3 and len(messages) == 3
    assert messages[0] == "\n".join([HUB_FALLBACK, line(1, "1. Ход")])
    assert messages[1] == "\n".join([HUB_FALLBACK, line(2, "2. Ход")])
    assert messages[2] == line(3, "3. Ход")     # straight to the SDK master during the pause
    assert table.feed().count(HUB_FAILED_LINE) == 2 and table.feed().count(HUB_PAUSED_LINE) == 1
    assert paused["hub"]["fails"] == 2 and paused["hub"]["paused_until"] == 1_800_000_900
    assert hub.payloads[2]["message"] == "\n".join([HUB_CATCH_UP, line(4, "4. Ход")])
    assert after["hub"]["fails"] == 0 and after["hub"]["paused_until"] is None and after["hub"]["last_result"] == "published"


def test_catch_up_notes_go_to_whichever_master_missed_turns(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_publishes, hub_silent, hub_publishes, hub_publishes)

    async def scenario():
        driver = await hub_started(table, hub, previous={"master": "hub"}, resume="s-old")
        for n in (1, 2, 3, 4):
            table.act(f"{n}. Ход")
            await driver.step()

    run(scenario())
    assert [p["message"] for p in hub.payloads] == ["\n".join([HUB_CATCH_UP, line(1, "1. Ход")]), line(2, "2. Ход"),
                                                    "\n".join([HUB_CATCH_UP, line(3, "3. Ход")]), line(4, "4. Ход")]
    assert table.providers[0].messages == ["\n".join([SDK_CATCH_UP, HUB_FALLBACK, line(2, "2. Ход")])]


def test_the_takeover_notice_comes_only_after_another_master(tmp_path):
    for previous, expected in (({"master": "sdk"}, True), ({}, True), ({"master": "hub"}, False)):
        root = tmp_path / str(len(previous) and previous["master"])
        root.mkdir()
        table, hub = Table(root), Hub(hub_publishes)

        async def scenario():
            driver = await hub_started(table, hub, previous=previous, resume="s-old")
            table.act("1. Ход")
            await driver.step()

        run(scenario())
        assert hub.payloads[0]["message"].startswith(TAKEOVER + "\n") is expected, previous


def test_a_restart_after_hub_turns_sends_no_fresh_session_notice(tmp_path):
    """Live 2026-10-28: with the hub playing, the SDK master never saves a session, so every restart opened a "fresh
    session" and the hub published a recap turn after each deploy."""
    table, hub = Table(tmp_path), Hub(hub_publishes)

    async def scenario():
        driver = await hub_started(table, hub, previous={"master": "hub"})
        await driver.step()                 # nothing waits: no notice, no batch
        quiet = list(hub.payloads)
        table.act("1. Ход")
        await driver.step()
        return quiet

    assert run(scenario()) == []
    assert [p["message"] for p in hub.payloads] == ["\n".join([HUB_CATCH_UP, line(1, "1. Ход")])]


def test_a_fresh_hub_table_still_announces_the_session(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_publishes)

    async def scenario():
        driver = await hub_started(table, hub, previous={"master": "sdk"})
        await driver.step()

    run(scenario())
    assert hub.payloads[0]["message"] == "\n".join([TAKEOVER, HUB_CATCH_UP, FRESH.format(name="alpha")])


def test_a_resumed_sdk_session_catches_up_after_the_hub_played(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        online.write_status({"master": "hub"}, tmp_path)
        driver = await started(table, resume="s-old")
        table.act("1. Ход")
        await driver.step()
        table.act("2. Ход")
        await driver.step()

    run(scenario())
    assert table.providers[0].messages == ["\n".join([SDK_CATCH_UP, line(1, "1. Ход")]), line(2, "2. Ход")]
    status = table.status()
    assert status["master"] == "sdk" and status["hub"] is None


def test_a_turn_published_during_revoke_counts_for_the_hub(tmp_path):
    table = Table(tmp_path)
    hub = Hub(hub_silent, on_revoke=lambda bridge: screen_cli.set_turn(bridge.context()["sdir"], TURN))

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Ход")
        await driver.step()

    run(scenario())
    assert hub.bridge.revoked == 1 and table.providers[0].messages == [] and table.feed() == []
    assert table.status()["hub"]["fails"] == 0 and table.status()["hub"]["last_result"] == "published"


def hub_publishes_late(hub, payload):
    """The hub publishes after the base timeout, as after a picture for a new act."""
    import threading

    sdir = hub.bridge.context()["sdir"]
    threading.Timer(0.3, screen_cli.set_turn, (sdir, TURN)).start()
    return True, None


@pytest.mark.parametrize("extension, hub_wins", [(2.0, True), (0.0, False)])
def test_the_hubs_time_in_slow_tools_extends_its_deadline(tmp_path, extension, hub_wins):
    table, hub = Table(tmp_path), Hub(hub_publishes_late, timeout=0.05, extension=extension)

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Новый акт")
        await driver.step()
        await asyncio.sleep(0.4)        # the late timer of the losing case lands before the next test

    run(scenario())
    assert (table.providers[0].messages == []) is hub_wins
    assert (table.status()["hub"]["last_result"] == "published") is hub_wins


def test_scrub_exec_environ_wipes_the_value_that_proc_environ_shows():
    code = ("import os, sys; from backend.hub_master import scrub_exec_environ; "
            "assert scrub_exec_environ('DM_PLAY_HUB_WEBHOOK'); assert 'DM_PLAY_HUB_WEBHOOK' not in os.environ; "
            "sys.stdout.write(open('/proc/self/environ', 'rb').read().decode('latin-1'))")
    if not Path("/proc/self/environ").exists():
        pytest.skip("no /proc")
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent, capture_output=True,
                         text=True, env={**os.environ, "DM_PLAY_HUB_WEBHOOK": WEBHOOK}, timeout=30)
    assert out.returncode == 0, out.stderr
    assert "SECRET-TOKEN" not in out.stdout and "PATH=" in out.stdout


def test_the_webhook_leaves_the_environment_and_never_reaches_the_log(tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO")
    monkeypatch.setenv("DM_PLAY_MASTER", "hub")
    monkeypatch.setenv("DM_PLAY_HUB_WEBHOOK", WEBHOOK)
    monkeypatch.setenv("DM_PLAY_HUB_SOCKET", "/unused/hub.sock")
    table, hub = Table(tmp_path), Hub(hub_publishes)
    scrubbed = []
    real_scrub = driver_module.scrub_exec_environ
    monkeypatch.setattr(driver_module, "scrub_exec_environ", lambda name: scrubbed.append(name) or real_scrub(name))

    async def scenario():
        driver = table.driver("alpha", poster=hub.poster, bridge_factory=hub.factory)
        await driver.start()
        assert "DM_PLAY_HUB_WEBHOOK" not in os.environ and scrubbed == ["DM_PLAY_HUB_WEBHOOK"]   # /proc's copy too
        table.act("1. Ход")
        await driver.step()
        return driver

    driver = run(scenario())
    assert driver.hub.master == "hub" and driver.hub.webhook == WEBHOOK and len(hub.payloads) == 1
    assert hub.bridge.path == Path("/unused/hub.sock")
    assert "webhook set" in caplog.text and "SECRET-TOKEN" not in caplog.text
    assert "SECRET-TOKEN" not in online.status_path(tmp_path).read_text()


def test_a_usage_limit_of_the_sdk_master_does_not_stop_the_hub(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_publishes, hub_silent)

    async def scenario():
        driver = await hub_started(table, hub, resume="s-old")
        driver.retry_at = table.clock.now + 1000
        table.act("1. Ход")
        await driver.step()             # the hub plays during the SDK master's rest
        table.act("2. Ход")
        await driver.step()             # the hub fails: the lines wait for the reset, the SDK master is not called
        return driver

    driver = run(scenario())
    assert len(hub.payloads) == 2 and table.providers[0].messages == []
    assert driver.carry == [CARRIED, line(2, "2. Ход")] and table.status()["state"] == "resting"


def test_sdk_mode_status_has_no_hub(tmp_path):
    table = Table(tmp_path)

    async def scenario():
        driver = await started(table)
        assert driver.bridge is None and driver.hub.master == "sdk"

    run(scenario())
    assert table.status()["master"] == "sdk" and table.status()["hub"] is None


# ---- the master console log (lib/screen/masterlog.py)

def console(table, name="alpha"):
    return [(e["kind"], e["master"], e["text"]) for e in masterlog.read(table.sdir(name), limit=0)]


def test_the_sdk_master_console_shows_the_batch_words_calls_results_and_the_turn(tmp_path):
    def script(provider, message):
        bash = AgentEvent("tool_use", 'Bash: {"command": "bash tools/dm-roll.sh 1d20+3", "description": "roll"}',
                          {"tool_name": "Bash", "short_name": "Bash"})
        read = AgentEvent("tool_use", 'Read: {"file_path": "/x/world.json"}', {"tool_name": "Read", "short_name": "Read"})
        return [AgentEvent("text_delta", "Бро"), AgentEvent("text", "Бросаю за Брама."), bash,
                AgentEvent("tool_result", "🎲 1d20+3: 17", {"is_error": False}), read,
                AgentEvent("tool_result", "no such file", {"is_error": True}), *publish(provider, "Готово.")]

    table = Table(tmp_path, script=script)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Осмотреться")
        await driver.step()

    run(scenario())
    assert console(table) == [
        ("batch", "sdk", "[screen #1] Катя (button): 1. Осмотреться"),
        ("text", "sdk", "Бросаю за Брама."),
        ("tool", "sdk", "bash tools/dm-roll.sh 1d20+3"),
        ("result", "sdk", "🎲 1d20+3: 17"),
        ("tool", "sdk", 'Read: {"file_path": "/x/world.json"}'),
        ("result", "sdk", "no such file"),
        ("text", "sdk", "Готово."),
        ("turn", "sdk", "Дождь стучит по крыше."),
    ]
    entries = masterlog.read(table.sdir(), limit=0)
    assert [e.get("name") for e in entries if e["kind"] == "tool"] == ["Bash", "Read"]
    assert [e["error"] for e in entries if e["kind"] == "result"] == [False, True]
    assert entries[-1]["turn"] == 1


def test_the_console_notes_a_follow_up_a_failure_a_timeout_a_limit_and_a_pause(tmp_path):
    async def script(provider, message):
        if "Ждать" in message:
            await asyncio.sleep(30)
        if "Бежать" in message:
            return [AgentEvent("rate_limit", "usage limit reached", {"retry_after": 120})]
        return [AgentEvent("text", "думаю")]

    table = Table(tmp_path, script=script, turn_timeout=0.2)

    async def scenario():
        driver = await started(table, resume="s1")
        table.act("1. Ждать")
        await driver.step()
        table.act("2. Бежать")
        await driver.step()
        online.main(["pause"], root=tmp_path)
        await driver.step()
        online.main(["resume"], root=tmp_path)
        table.clock.now += 200
        await driver.step()

    run(scenario())
    notes = [text for kind, master, text in console(table) if kind == "note"]
    assert all(master == "driver" for kind, master, _ in console(table) if kind == "note")
    assert notes[0] == driver_module.NOTE_TIMEOUT.format(seconds=0.2)
    assert notes[1].startswith("Ход не опубликован (the turn ran over")
    assert notes[2].startswith("Ход так и не вышел:")
    assert notes[3] == driver_module.NOTE_LIMIT.format(minutes=2)
    assert notes[4:6] == [driver_module.NOTE_PAUSED, driver_module.NOTE_RESUMED]


def test_the_hub_console_shows_its_batch_without_the_ticket_and_the_fallback_notes(tmp_path):
    hub = Hub(hub_silent)
    table = Table(tmp_path)

    async def scenario():
        driver = await hub_started(table, hub)
        table.act("1. Осмотреться")
        await driver.step()

    run(scenario())
    log = console(table)
    first = "\n".join([TAKEOVER, HUB_CATCH_UP, FRESH.format(name="alpha"), line(1, "1. Осмотреться")])
    assert log[0] == ("batch", "hub", first)
    assert log[1] == ("note", "driver", driver_module.NOTE_HUB_FAILED.format(reason="no turn in 0s"))
    assert log[2] == ("batch", "sdk", "\n".join([HUB_FALLBACK, FRESH.format(name="alpha"), line(1, "1. Осмотреться")]))
    assert log[-1] == ("turn", "sdk", "Дождь стучит по крыше.")
    raw = (table.sdir() / masterlog.LOG).read_text(encoding="utf-8")
    assert "ticket-1" not in raw and WEBHOOK not in raw and "SECRET-TOKEN" not in raw


def test_a_hub_turn_is_logged_for_the_hub_and_a_pause_gets_a_note(tmp_path):
    table, hub = Table(tmp_path), Hub(hub_down, hub_down, hub_publishes, pause=900)

    async def scenario():
        driver = await hub_started(table, hub, resume="s-old")
        for n in range(1, 3):
            table.act(f"{n}. Ход")
            await driver.step()
        table.clock.now += 901
        table.act("3. Ход")
        await driver.step()

    run(scenario())
    log = console(table)
    assert ("note", "driver", driver_module.NOTE_HUB_FAILED.format(reason="post failed: HTTP 502")) in log
    assert ("note", "driver", driver_module.NOTE_HUB_PAUSED.format(minutes=15, fails=2)) in log
    (kind, master, text), last = log[-2], log[-1]
    assert (kind, master) == ("batch", "hub") and text.endswith(line(3, "3. Ход"))
    assert last == ("turn", "hub", "Дождь стучит по крыше.")
