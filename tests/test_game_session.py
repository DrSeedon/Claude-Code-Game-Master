"""Unit tests for GameSession — registry, double-send guard, idle hibernate.

No pytest-asyncio in this project — tests drive the event loop manually via
asyncio.run() to await GameSession's background turn task.
"""

import asyncio
import pytest

import backend.game_session as game_session_module
from backend.game_session import GameSession, get_or_create_session


@pytest.fixture(autouse=True)
def clear_registry():
    """Session registry is module-level global state — reset between tests."""
    game_session_module._sessions.clear()
    yield
    game_session_module._sessions.clear()


async def _fake_events(*_a, **_kw):
    yield {"type": "text", "content": "the DM speaks"}


def test_get_or_create_session_creates_new(tmp_path):
    session = get_or_create_session("camp-a", tmp_path, "claude-sonnet-4-6")

    assert isinstance(session, GameSession)
    assert session.campaign == "camp-a"


def test_get_or_create_session_returns_existing(tmp_path):
    first = get_or_create_session("camp-a", tmp_path, "claude-sonnet-4-6")
    second = get_or_create_session("camp-a", tmp_path, "claude-sonnet-4-6")

    assert first is second


def test_get_or_create_session_different_campaigns_are_isolated(tmp_path):
    a = get_or_create_session("camp-a", tmp_path, "claude-sonnet-4-6")
    b = get_or_create_session("camp-b", tmp_path, "claude-sonnet-4-6")

    assert a is not b


def test_send_starts_turn_and_marks_running(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-4-6")
    session.provider.process_message = _fake_events

    async def scenario():
        ok = session.send("hello", "system prompt")
        assert ok is True
        assert session.running is True
        await session._turn_task

    asyncio.run(scenario())

    assert session.running is False


def test_send_rejects_while_turn_running(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-4-6")

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
    session = GameSession("camp-a", tmp_path, "claude-sonnet-4-6")
    session.provider.process_message = _fake_events

    async def scenario():
        session.send("first", "system prompt")
        await session._turn_task
        return session.send("second", "system prompt")

    second_ok = asyncio.run(scenario())

    assert second_ok is True


def test_hibernate_closes_provider_after_idle_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(game_session_module, "HIBERNATE_IDLE_SECONDS", 0)
    session = GameSession("camp-a", tmp_path, "claude-sonnet-4-6")
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
    session = GameSession("camp-a", tmp_path, "claude-sonnet-4-6")
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
