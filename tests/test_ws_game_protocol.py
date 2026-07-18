"""Integration tests for the /ws/game protocol contract.

Covers the AC from frontend-migration-blueprint.md §3.1/§5:
- campaign comes from the query string, not the global active-campaign config
- after_id filters replay to only unseen events
- receive_text() is always treated as a player turn (no in-band control msgs)
- two campaigns stream independently (no cross-talk)
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import backend.server as server_module
import backend.game_session as game_session_module
from backend.event_log import append_event, read_events


@pytest.fixture(autouse=True)
def clear_registry():
    game_session_module._sessions.clear()
    yield
    game_session_module._sessions.clear()


@pytest.fixture
def sent():
    return []


@pytest.fixture
def client(tmp_path, monkeypatch, sent):
    monkeypatch.setattr(server_module, "load_system_prompt", lambda *a, **k: "system prompt")

    class FakeConfig:
        project_root = tmp_path
        model_name = "claude-sonnet-5"
        campaigns_dir = tmp_path / "world-state" / "campaigns"
        backend_host = "127.0.0.1"
        backend_port = 18083
        campaign_name = None

    monkeypatch.setattr(server_module, "get_config", lambda: FakeConfig())

    # Prevent any real SDK connection — GameSession.send() is exercised in
    # test_game_session.py; here we only care about the WS transport contract.
    def fake_send(self, user_message, system_prompt, mcp_servers=None):
        sent.append((self.campaign, user_message))
        return True

    monkeypatch.setattr(game_session_module.GameSession, "send", fake_send)

    with TestClient(server_module.app) as c:
        yield c


def _campaign_dir(tmp_path, name):
    d = tmp_path / "world-state" / "campaigns" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_missing_campaign_query_param_closes_with_error(client):
    with client.websocket_connect("/ws/game") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "campaign" in msg["content"].lower()


def test_websocket_requires_auth_cookie_when_password_is_enabled(
    client, tmp_path, monkeypatch
):
    _campaign_dir(tmp_path, "blood-arena")
    monkeypatch.setenv("DND_AUTH_PASSWORD", "secret")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/game?campaign=blood-arena"):
            pass
    assert exc_info.value.code == 1008
    with pytest.raises(WebSocketDisconnect) as wizard_exc:
        with client.websocket_connect("/ws/wizard"):
            pass
    assert wizard_exc.value.code == 1008

    response = client.post(
        "/auth/login",
        data={"password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.websocket_connect("/ws/game?campaign=blood-arena"):
        pass


def test_campaign_from_query_not_global_config(client, tmp_path, sent):
    _campaign_dir(tmp_path, "blood-arena")

    with client.websocket_connect("/ws/game?campaign=blood-arena") as ws:
        ws.send_text("attack the goblin")

    assert ("blood-arena", "attack the goblin") in sent


def test_after_id_filters_replay(client, tmp_path):
    campaign_dir = _campaign_dir(tmp_path, "blood-arena")
    for i in range(7):
        append_event(campaign_dir, "text", f"event-{i}")

    with client.websocket_connect("/ws/game?campaign=blood-arena&after_id=5") as ws:
        history_msg = ws.receive_json()

    assert history_msg["type"] == "history"
    assert [m["content"] for m in history_msg["messages"]] == ["event-5", "event-6"]


def test_after_id_zero_returns_full_history(client, tmp_path):
    campaign_dir = _campaign_dir(tmp_path, "blood-arena")
    append_event(campaign_dir, "text", "only event")

    with client.websocket_connect("/ws/game?campaign=blood-arena") as ws:
        history_msg = ws.receive_json()

    assert len(history_msg["messages"]) == 1


def test_disconnect_during_initial_history_replay_is_clean(client, tmp_path):
    campaign_dir = _campaign_dir(tmp_path, "blood-arena")
    append_event(campaign_dir, "text", "large replay payload")

    class DisconnectingWebSocket:
        query_params = {"campaign": "blood-arena", "after_id": "0"}
        accepted = False

        async def accept(self):
            self.accepted = True

        async def send_text(self, _payload):
            raise WebSocketDisconnect(code=1006)

    websocket = DisconnectingWebSocket()
    asyncio.run(server_module.game_websocket(websocket))

    assert websocket.accepted


def test_new_session_boundary_hides_old_chat_without_truncating_log(
    client, tmp_path
):
    campaign_dir = _campaign_dir(tmp_path, "blood-arena")
    append_event(campaign_dir, "user_message", "old question")
    append_event(campaign_dir, "text", "old answer")

    response = client.post("/api/campaigns/blood-arena/reset-session")
    assert response.status_code == 200
    boundary_id = response.json()["after_id"]
    append_event(campaign_dir, "text", "new session answer")

    stored = read_events(campaign_dir)
    assert [event["type"] for event in stored] == [
        "user_message",
        "text",
        "session_reset",
        "text",
    ]
    assert stored[2]["id"] == boundary_id

    with client.websocket_connect("/ws/game?campaign=blood-arena") as ws:
        history_msg = ws.receive_json()

    assert [message["content"] for message in history_msg["messages"]] == [
        "new session answer"
    ]


def test_compact_endpoint_preserves_visible_chat(client, tmp_path):
    campaign_dir = _campaign_dir(tmp_path, "blood-arena")
    append_event(campaign_dir, "user_message", "keep this visible")
    session = game_session_module.get_or_create_session(
        "blood-arena",
        tmp_path,
        "claude-sonnet-5",
    )

    response = client.post("/api/campaigns/blood-arena/compact")

    assert response.status_code == 200
    assert response.json()["mode"] == "handoff_reset"
    assert not any(
        event["type"] == "session_reset"
        for event in read_events(campaign_dir)
    )
    assert session._history_handoff


def test_game_websocket_applies_valid_effort_and_rejects_invalid_one(
    client, tmp_path
):
    _campaign_dir(tmp_path, "blood-arena")
    url = (
        "/ws/game?campaign=blood-arena&provider=codex"
        "&model=gpt-5.6-terra&effort=xhigh"
    )
    with client.websocket_connect(url):
        pass

    session = game_session_module._sessions["blood-arena"]
    assert session.reasoning_effort == "xhigh"
    assert session.provider.reasoning_effort == "xhigh"

    game_session_module._sessions.clear()
    with client.websocket_connect(
        "/ws/game?campaign=blood-arena&provider=codex"
        "&model=gpt-5.6-terra&effort=impossible"
    ) as ws:
        error = ws.receive_json()
    assert error["type"] == "error"
    assert "unsupported reasoning effort" in error["content"]


def test_no_history_message_when_log_empty(client, tmp_path, sent):
    _campaign_dir(tmp_path, "fresh-campaign")

    with client.websocket_connect("/ws/game?campaign=fresh-campaign") as ws:
        status = ws.receive_json()
        assert status == {
            "type": "agent_status",
            "status": "idle",
            "runtime": "claude",
            "model": "claude-sonnet-5",
            "started_at": None,
        }
        ws.send_text("hello")
        # No history frame should have been queued before our own message round-trips —
        # nothing to assert-receive here since no history was sent; absence of a crash
        # and the send landing correctly is the behavior under test.

    assert ("fresh-campaign", "hello") in sent


def test_receive_text_is_always_a_player_turn_never_control_message(client, tmp_path, sent):
    _campaign_dir(tmp_path, "blood-arena")

    with client.websocket_connect("/ws/game?campaign=blood-arena") as ws:
        # Even JSON that looks like a control/replay message must be treated as
        # a plain player turn string — no special-casing in receive_text().
        ws.send_text('{"type": "replay", "after_id": 3}')

    assert ("blood-arena", '{"type": "replay", "after_id": 3}') in sent


def test_two_campaigns_stream_independently(client, tmp_path, sent):
    _campaign_dir(tmp_path, "camp-a")
    _campaign_dir(tmp_path, "camp-b")

    with client.websocket_connect("/ws/game?campaign=camp-a") as ws_a:
        with client.websocket_connect("/ws/game?campaign=camp-b") as ws_b:
            ws_a.send_text("a says hi")
            ws_b.send_text("b says hi")

    assert ("camp-a", "a says hi") in sent
    assert ("camp-b", "b says hi") in sent
    # No interference: session registry keeps them as distinct GameSession instances
    assert game_session_module._sessions["camp-a"] is not game_session_module._sessions["camp-b"]
