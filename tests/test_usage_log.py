"""Usage accounting tests exercise the GameSession turn lifecycle."""

import asyncio
import json

from backend.config import Config
from backend.game_session import GameSession
from backend.usage_log import usage_log_path, usage_totals


async def _text_events(*_args, **_kwargs):
    yield {"type": "text", "content": "The DM speaks."}


def _run_turn(session: GameSession, message: str) -> None:
    async def scenario():
        assert session.send(message, "system prompt") is True
        await session._turn_task

    asyncio.run(scenario())


def test_completed_turn_appends_usage_and_second_turn_does_not_overwrite(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _text_events
    usages = iter(
        [
            {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 30},
            {"input_tokens": 2, "output_tokens": 4, "cache_creation_input_tokens": 100},
        ]
    )
    session.provider.get_turn_usage = lambda: next(usages)

    _run_turn(session, "first")
    _run_turn(session, "second")

    path = usage_log_path(tmp_path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["input_tokens"] == 10
    assert rows[1]["cache_write_tokens"] == 100
    assert rows[0]["duration_seconds"] >= 0
    assert path.stat().st_size > 0


def test_usage_totals_group_campaigns_and_models_and_price_cache_tokens(tmp_path):
    first = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    first.provider.process_message = _text_events
    first.provider.get_turn_usage = lambda: {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
    }
    _run_turn(first, "one")

    second = GameSession("camp-b", tmp_path, "claude-opus-5")
    second.provider.process_message = _text_events
    second.provider.get_turn_usage = lambda: {"input_tokens": 2}
    _run_turn(second, "two")

    totals = usage_totals(tmp_path)
    assert totals["campaigns"]["camp-a"]["turns"] == 1
    assert totals["models"]["claude-sonnet-5"]["input_tokens"] == 1_000_000
    assert totals["campaigns"]["camp-a"]["price_usd"] == 14.7
    assert totals["total"]["turns"] == 2


def test_unknown_model_price_is_unknown_but_turn_completes(tmp_path):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.model_name = "future-model"
    session.provider.process_message = _text_events
    session.provider.get_turn_usage = lambda: {"input_tokens": 9, "output_tokens": 3}

    _run_turn(session, "unknown")

    row = json.loads(usage_log_path(tmp_path).read_text(encoding="utf-8"))
    assert row["price_usd"] is None
    assert row["price_status"] == "unknown_model"
    assert usage_totals(tmp_path)["total"]["price_usd"] is None


def test_missing_usage_does_not_create_usage_catalog(tmp_path, caplog):
    session = GameSession("camp-a", tmp_path, "claude-sonnet-5")
    session.provider.process_message = _text_events
    session.provider.get_turn_usage = lambda: None

    _run_turn(session, "no accounting")

    assert not usage_log_path(tmp_path).exists()
    assert "provider returned no usage" in caplog.text


def test_api_usage_endpoint_uses_authenticated_api_path(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import server

    config = Config(
        project_root=tmp_path,
        world_state_base=tmp_path / "world-state",
        campaigns_dir=tmp_path / "world-state" / "campaigns",
    )
    monkeypatch.setenv("DND_AUTH_PASSWORD", "test-password")
    monkeypatch.setattr(server, "get_config", lambda: config)
    with TestClient(server.app) as client:
        assert client.post(
            "/auth/login",
            data={"password": "test-password"},
            follow_redirects=False,
        ).status_code == 302
        response = client.get("/api/usage")

    assert response.status_code == 200
    assert response.json() == {
        "campaigns": {},
        "models": {},
        "total": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "price_usd": 0.0,
            "price_known": True,
            "turns": 0,
        },
    }
