"""Unit tests for GameSession — registry, double-send guard, idle hibernate.

No pytest-asyncio in this project — tests drive the event loop manually via
asyncio.run() to await GameSession's background turn task.
"""

import asyncio
import pytest

import backend.game_session as game_session_module
from backend.event_log import append_event, read_events
from backend.game_session import GameSession, get_or_create_session
from backend.runtime import AgentEvent


@pytest.fixture(autouse=True)
def clear_registry():
    """Session registry is module-level global state — reset between tests."""
    game_session_module._sessions.clear()
    yield
    game_session_module._sessions.clear()


async def _fake_events(*_a, **_kw):
    yield {"type": "text", "content": "the DM speaks"}


def test_get_or_create_session_creates_new(tmp_path):
    session = get_or_create_session("camp-a", tmp_path, "claude-sonnet-5")

    assert isinstance(session, GameSession)
    assert session.campaign == "camp-a"


def test_get_or_create_session_returns_existing(tmp_path):
    first = get_or_create_session("camp-a", tmp_path, "claude-sonnet-5")
    second = get_or_create_session("camp-a", tmp_path, "claude-sonnet-5")

    assert first is second


def test_get_or_create_session_rebuilds_provider_when_effort_changes(tmp_path):
    async def scenario():
        session = get_or_create_session(
            "camp-a",
            tmp_path,
            "gpt-5.6-terra",
            "codex",
            reasoning_effort="medium",
        )
        old_provider = session.provider

        same = get_or_create_session(
            "camp-a",
            tmp_path,
            "gpt-5.6-terra",
            "codex",
            reasoning_effort="high",
        )
        await asyncio.sleep(0)

        assert same is session
        assert session.reasoning_effort == "high"
        assert session.provider is not old_provider
        assert session.provider.reasoning_effort == "high"

    asyncio.run(scenario())


def test_get_or_create_session_different_campaigns_are_isolated(tmp_path):
    a = get_or_create_session("camp-a", tmp_path, "claude-sonnet-5")
    b = get_or_create_session("camp-b", tmp_path, "claude-sonnet-5")

    assert a is not b
    assert a.provider.campaign_name == "camp-a"
    assert b.provider.campaign_name == "camp-b"


def test_provider_process_environment_is_campaign_scoped(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")

    options = session.provider._make_options(
        "claude-sonnet-5", "system", None
    )

    assert options.env["DM_ACTIVE_CAMPAIGN"] == "camp-a"


def test_send_starts_turn_and_marks_running(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _fake_events

    async def scenario():
        ok = session.send("hello", "system prompt")
        assert ok is True
        assert session.running is True
        await session._turn_task

    asyncio.run(scenario())

    assert session.running is False


def test_send_publishes_running_then_idle_agent_status(tmp_path, monkeypatch):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _fake_events
    published = []
    monkeypatch.setattr(
        game_session_module.broker,
        "publish",
        lambda campaign, payload: published.append((campaign, payload)),
    )

    async def scenario():
        assert session.send("hello", "system prompt") is True
        await session._turn_task

    asyncio.run(scenario())

    statuses = [
        payload
        for campaign, payload in published
        if campaign == "camp-a" and payload["type"] == "agent_status"
    ]
    assert [event["status"] for event in statuses] == ["running", "idle"]
    assert statuses[0]["model"] == "claude-sonnet-5"
    assert statuses[0]["runtime"] == "claude"
    assert statuses[0]["started_at"]
    assert statuses[1]["started_at"] is None


def test_send_rejects_while_turn_running(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")

    async def slow_events(*_a, **_kw):
        await asyncio.sleep(0.05)
        yield {"type": "text", "content": "slow"}

    session.provider.process_message = slow_events

    async def scenario():
        first_ok = session.send("first", "system prompt")
        second_ok = session.send("second", "system prompt")  # turn still running
        assert first_ok is True
        assert second_ok is False
        await session._turn_task

    asyncio.run(scenario())


def test_send_after_turn_completes_is_allowed_again(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _fake_events

    async def scenario():
        session.send("first", "system prompt")
        await session._turn_task
        return session.send("second", "system prompt")

    second_ok = asyncio.run(scenario())

    assert second_ok is True


def test_tool_activity_metadata_survives_event_log_round_trip(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")

    async def tool_events(*_args, **_kwargs):
        yield AgentEvent(
            "tool_use",
            "Bash: pwd",
            {"tool_name": "Bash", "tool_use_id": "tool-1"},
        )
        yield AgentEvent(
            "tool_result",
            "/project",
            {"tool_use_id": "tool-1", "exit_code": 0},
        )

    session.provider.process_message = tool_events

    async def scenario():
        assert session.send("inspect", "system prompt") is True
        await session._turn_task

    asyncio.run(scenario())

    activities = [
        event
        for event in read_events(session.campaign_dir)
        if event["type"] == "activity"
    ]
    assert [event["metadata"]["activity_type"] for event in activities] == [
        "tool_use",
        "tool_result",
    ]
    assert activities[0]["metadata"]["tool_name"] == "Bash"
    assert activities[1]["metadata"]["exit_code"] == 0
    assert {
        event["metadata"]["tool_use_id"]
        for event in activities
    } == {"tool-1"}


def test_hibernate_closes_provider_after_idle_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(game_session_module, "HIBERNATE_IDLE_SECONDS", 0)
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _fake_events

    closed = []

    async def fake_close():
        closed.append(True)

    session.provider.close = fake_close

    async def scenario():
        session.send("first", "system prompt")
        await session._turn_task
        # second turn: idle_for computed from _last_turn_end_at, threshold is 0 → always hibernates
        session.send("second", "system prompt")
        await session._turn_task

    asyncio.run(scenario())

    assert closed == [True]


def test_no_hibernate_when_under_idle_threshold(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _fake_events

    closed = []

    async def fake_close():
        closed.append(True)

    session.provider.close = fake_close

    async def scenario():
        session.send("first", "system prompt")
        await session._turn_task
        session.send("second", "system prompt")  # immediately after — well under 5 min
        await session._turn_task

    asyncio.run(scenario())

    assert closed == []


def test_provider_switch_is_transactional_when_build_fails(tmp_path, monkeypatch):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    old_provider = session.provider

    def fail_build(_model_name=None, _reasoning_effort=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(session, "_build_provider", fail_build)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        session.configure("codex", "gpt-5.6-sol")

    assert session.runtime_id == "claude"
    assert session.model_name == "claude-sonnet-5"
    assert session.provider is old_provider


def test_reset_blocks_turn_and_provider_switch(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_reset():
            started.set()
            await release.wait()

        session.provider.reset = slow_reset
        reset_task = asyncio.create_task(session.reset_session())
        await started.wait()

        assert session.send("hello", "system prompt") is False
        with pytest.raises(RuntimeError, match="turn is in progress"):
            session.configure("codex", "gpt-5.6-sol")

        release.set()
        boundary = await reset_task
        assert boundary["type"] == "session_reset"

    asyncio.run(scenario())


def test_provider_switch_hands_recent_transcript_to_first_turn(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    append_event(session.campaign_dir, "user_message", "I open the vault.")
    append_event(session.campaign_dir, "text", "The alarm starts ringing.")
    captured = {}

    async def scenario():
        session.configure("codex", "gpt-5.6-sol")

        async def capture_turn(*_args, **kwargs):
            captured["system_prompt"] = kwargs["system_prompt"]
            yield {"type": "text", "content": "Guards arrive."}

        session.provider.process_message = capture_turn
        assert session.send("I hide.", "SYSTEM RULES") is True
        await session._turn_task

    asyncio.run(scenario())

    prompt = captured["system_prompt"]
    assert "SYSTEM RULES" in prompt
    assert "PLAYER: I open the vault." in prompt
    assert "GAME MASTER: The alarm starts ringing." in prompt
    assert "PLAYER: I hide." not in prompt
    assert session._history_handoff is None


def test_provider_switch_after_reset_does_not_restore_old_chat(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    append_event(session.campaign_dir, "user_message", "old question")
    append_event(session.campaign_dir, "text", "old answer")

    async def scenario():
        boundary = await session.reset_session()
        assert boundary["type"] == "session_reset"
        session.configure("codex", "gpt-5.6-terra")
        await asyncio.sleep(0)

    asyncio.run(scenario())

    assert session._history_handoff is None
