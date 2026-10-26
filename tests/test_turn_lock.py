"""One master turn per campaign across processes: the web GameSession and the online screen driver."""

import asyncio
import subprocess
import sys
import textwrap

import pytest

import backend.game_session as game_session_module
from backend.event_log import read_events
from backend.game_session import ONLINE_TABLE_BUSY, GameSession
from backend.runtime.turn_lock import CampaignTurnLock, TurnLockBusy, campaign_turn_lock, try_campaign_turn_lock


def test_two_holders_exclude_each_other_and_release_frees(tmp_path):
    first = CampaignTurnLock(tmp_path)
    assert first.acquire(blocking=False)

    assert try_campaign_turn_lock(tmp_path) is None
    with pytest.raises(TurnLockBusy):
        with campaign_turn_lock(tmp_path, blocking=False):
            pass

    first.release()
    second = try_campaign_turn_lock(tmp_path)
    assert second is not None and second.held
    second.release()
    assert (tmp_path / ".turn.lock").is_file()


def test_lock_held_by_another_process_is_busy(tmp_path):
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import fcntl, sys, time
        handle = open({str(tmp_path / '.turn.lock')!r}, 'a+')
        fcntl.flock(handle, fcntl.LOCK_EX)
        print('locked', flush=True)
        sys.stdin.readline()
    """)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        assert try_campaign_turn_lock(tmp_path) is None
    finally:
        holder.communicate("\n", timeout=10)
    lock = try_campaign_turn_lock(tmp_path)
    assert lock is not None
    lock.release()


def test_acquire_async_waits_for_the_holder(tmp_path):
    async def scenario():
        holder = CampaignTurnLock(tmp_path)
        holder.acquire()
        waiter = CampaignTurnLock(tmp_path)
        task = asyncio.ensure_future(waiter.acquire_async(poll=0.01))
        await asyncio.sleep(0.05)
        assert not task.done()
        holder.release()
        await asyncio.wait_for(task, 2)
        assert waiter.held
        waiter.release()

    asyncio.run(scenario())


def test_acquire_async_is_cancellable(tmp_path):
    async def scenario():
        holder = CampaignTurnLock(tmp_path)
        holder.acquire()
        task = asyncio.ensure_future(CampaignTurnLock(tmp_path).acquire_async(poll=0.01))
        await asyncio.sleep(0.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        holder.release()

    asyncio.run(scenario())


def test_game_session_refuses_a_turn_while_the_online_table_plays(tmp_path, monkeypatch):
    game_session_module._sessions.clear()
    session = GameSession("online-camp", tmp_path, "claude-sonnet-5")
    calls = []

    async def events(*args, **kwargs):
        calls.append(args)
        yield {"type": "text", "content": "the DM speaks"}

    session.provider.process_message = events
    published = []
    monkeypatch.setattr(game_session_module.broker, "publish", lambda campaign, payload: published.append(payload))
    usage = []
    monkeypatch.setattr(game_session_module, "record_usage", lambda **kw: usage.append(kw))
    driver_lock = CampaignTurnLock(session.campaign_dir)
    assert driver_lock.acquire(blocking=False)

    async def turn(text):
        assert session.send(text, "system prompt") is True
        await session._turn_task

    asyncio.run(turn("hello"))

    assert calls == [] and usage == []
    errors = [e for e in read_events(session.campaign_dir) if e["type"] == "error"]
    assert [e["content"] for e in errors] == [ONLINE_TABLE_BUSY]
    assert any(p.get("type") == "error" and p.get("content") == ONLINE_TABLE_BUSY for p in published)
    assert published[-1] == {"type": "done"} and session.running is False

    driver_lock.release()
    asyncio.run(turn("again"))

    assert len(calls) == 1 and len(usage) == 1
    free = try_campaign_turn_lock(session.campaign_dir)   # released after the turn
    assert free is not None
    free.release()


def test_game_session_leaves_the_campaign_a_live_driver_plays_alone_between_its_turns(tmp_path, monkeypatch):
    """The driver holds the turn lock only during a turn; its campaign's screen and cursor are its own all along."""
    import json
    import os

    game_session_module._sessions.clear()
    session = GameSession("online-camp", tmp_path, "claude-sonnet-5")
    calls = []

    async def events(*args, **kwargs):
        calls.append(args)
        yield {"type": "text", "content": "the DM speaks"}

    session.provider.process_message = events
    monkeypatch.setattr(game_session_module.broker, "publish", lambda campaign, payload: None)
    monkeypatch.setattr(game_session_module, "record_usage", lambda **kw: None)
    status = tmp_path / "world-state" / "online-play-status.json"
    status.parent.mkdir(parents=True, exist_ok=True)

    async def turn(text):
        assert session.send(text, "system prompt") is True
        await session._turn_task

    status.write_text(json.dumps({"pid": os.getpid(), "campaign": "online-camp", "state": "idle"}))
    asyncio.run(turn("hello"))
    assert calls == [] and [e["content"] for e in read_events(session.campaign_dir) if e["type"] == "error"] == [ONLINE_TABLE_BUSY]

    status.write_text(json.dumps({"pid": os.getpid(), "campaign": "online-camp", "state": "offline"}))   # stopped cleanly
    asyncio.run(turn("again"))
    status.write_text(json.dumps({"pid": os.getpid(), "campaign": "other-camp", "state": "idle"}))
    asyncio.run(turn("and again"))
    assert len(calls) == 2
