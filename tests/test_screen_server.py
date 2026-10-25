import http.client
import json

import pytest

from lib.screen import inbox, server


@pytest.fixture
def running(tmp_path):
    (tmp_path / "art.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "act.json").write_text(json.dumps({"id": 1, "title": "Том первый", "captions": [],
                                                    "theme": {"bg": "#000000"}, "theme_css": ":root{--bg:#000}"}))
    (tmp_path / "turn.json").write_text(json.dumps({"id": 3, "blocks": ["<p>x</p>"], "question": "?", "options": ["a"]}))
    httpd, token = server.make_server(
        tmp_path, port=0, token="T0KEN", views_provider=lambda: {"character": {"name": "Максим"}},
        transcriber=lambda audio, ctype: "привет, мир")
    server.serve_in_thread(httpd)
    yield httpd.server_port, token, tmp_path
    httpd.shutdown()
    httpd.server_close()


def call(port, method, path, body=None, headers=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = dict(headers or {})
    if host:
        h["Host"] = host
    conn.request(method, path, body=body, headers=h)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_page_contains_token_and_theme(running):
    port, token, _ = running

    status, body = call(port, "GET", "/")

    assert status == 200
    text = body.decode()
    assert token in text and "--bg:#000" in text and "Том первый" in text


def test_state_requires_token(running):
    port, token, _ = running

    assert call(port, "GET", "/api/state")[0] == 403
    status, body = call(port, "GET", "/api/state", headers={"X-Screen-Token": token})
    state = json.loads(body)
    assert status == 200
    assert state["turn"]["id"] == 3 and state["act"]["id"] == 1 and state["views"]["character"]["name"] == "Максим"


def test_foreign_host_header_is_rejected(running):
    port, token, _ = running

    status, _ = call(port, "GET", "/api/state", headers={"X-Screen-Token": token}, host="evil.example")

    assert status == 403


def test_action_lands_in_inbox(running):
    port, token, tmp_path = running
    payload = json.dumps({"who": "Катя", "source": "button", "text": "1. Показать товар"})

    status, body = call(port, "POST", "/api/action", payload, {"X-Screen-Token": token, "Content-Type": "application/json"})

    assert status == 200 and json.loads(body)["id"] == 1
    assert inbox.read_events(tmp_path)[0]["text"] == "1. Показать товар"


def test_action_without_token_is_rejected_and_not_stored(running):
    port, _, tmp_path = running
    payload = json.dumps({"who": "Катя", "source": "button", "text": "x"})

    status, _ = call(port, "POST", "/api/action", payload, {"Content-Type": "application/json"})

    assert status == 403 and inbox.read_events(tmp_path) == []


def test_empty_action_is_a_client_error(running):
    port, token, _ = running

    status, _ = call(port, "POST", "/api/action", json.dumps({"who": "Оба", "source": "text", "text": " "}),
                     {"X-Screen-Token": token})

    assert status == 400


def test_voice_returns_transcript(running):
    port, token, _ = running

    status, body = call(port, "POST", "/api/voice", b"fake-audio", {"X-Screen-Token": token, "Content-Type": "audio/webm"})

    assert status == 200 and json.loads(body)["text"] == "привет, мир"


def test_voice_without_key_is_service_unavailable(tmp_path):
    from lib.screen import voice

    def no_key(audio, ctype):
        raise voice.VoiceUnavailable("DEEPGRAM_API_KEY is not set")

    httpd, token = server.make_server(tmp_path, port=0, token="T", views_provider=dict, transcriber=no_key)
    server.serve_in_thread(httpd)
    try:
        status, body = call(httpd.server_port, "POST", "/api/voice", b"x", {"X-Screen-Token": "T"})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 503 and "DEEPGRAM_API_KEY" in json.loads(body)["error"]


def test_art_is_served(running):
    port, _, _ = running

    status, body = call(port, "GET", "/art.png")

    assert status == 200 and body.startswith(b"\x89PNG")


def _read_event(response):
    while True:
        line = response.fp.readline().decode()
        if line.startswith("data:"):
            return json.loads(line[5:])
        if not line:
            raise AssertionError("stream closed")


def test_event_stream_pushes_changes_without_reload(running):
    import time

    port, token, tmp_path = running
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", f"/api/events?token={token}")
    response = conn.getresponse()

    assert response.status == 200 and "text/event-stream" in response.getheader("Content-Type")
    assert _read_event(response)["turn"]["id"] == 3

    time.sleep(0.05)
    (tmp_path / "turn.json").write_text(json.dumps({"id": 4, "blocks": ["<p>y</p>"], "question": "?", "options": []}))
    inbox.append_event(tmp_path, "Катя", "button", "ход")
    pushed = _read_event(response)
    conn.close()

    assert pushed["turn"]["id"] == 4 and pushed["inbox_last"] == 1


def test_event_stream_requires_token(running):
    port, _, _ = running

    assert call(port, "GET", "/api/events?token=wrong")[0] == 403


def test_state_includes_activity_tail(running):
    from lib.screen import activity

    port, token, tmp_path = running
    activity.append_activity(tmp_path, "roll", "🎲 Торговля: 17")

    _, body = call(port, "GET", "/api/state", headers={"X-Screen-Token": token})

    assert json.loads(body)["activity"][-1]["text"] == "🎲 Торговля: 17"


def test_state_carries_a_build_stamp_so_open_windows_can_refresh(running):
    port, token, _ = running

    _, body = call(port, "GET", "/api/state", headers={"X-Screen-Token": token})

    assert isinstance(json.loads(body)["build"], int)


def test_client_count_follows_open_pages(running):
    import time

    port, token, _ = running
    assert json.loads(call(port, "GET", "/api/clients", headers={"X-Screen-Token": token})[1])["clients"] == 0
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", f"/api/events?token={token}")
    stream = conn.getresponse()
    stream.fp.readline()
    time.sleep(0.2)

    assert json.loads(call(port, "GET", "/api/clients", headers={"X-Screen-Token": token})[1])["clients"] == 1

    stream.close()
    conn.close()
    for _ in range(20):
        time.sleep(0.2)
        if json.loads(call(port, "GET", "/api/clients", headers={"X-Screen-Token": token})[1])["clients"] == 0:
            break
    assert json.loads(call(port, "GET", "/api/clients", headers={"X-Screen-Token": token})[1])["clients"] == 0


def test_state_carries_the_live_clock(tmp_path):
    (tmp_path / "act.json").write_text(json.dumps({"id": 1, "title": "t", "theme_css": ""}))
    httpd, token = server.make_server(tmp_path, port=0, token="T", views_provider=dict,
                                      clock_provider=lambda: {"text": "Monday — 20:15", "location": "Courtyard"})
    server.serve_in_thread(httpd)
    try:
        _, body = call(httpd.server_port, "GET", "/api/state", headers={"X-Screen-Token": "T"})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert json.loads(body)["clock"] == {"text": "Monday — 20:15", "location": "Courtyard"}


def test_signature_changes_when_the_game_time_changes(tmp_path):
    (tmp_path / "act.json").write_text("{}")
    overview = tmp_path.parent / "campaign-overview.json"
    overview.write_text('{"precise_time": "20:00"}')
    before = server._signature(tmp_path)

    overview.write_text('{"precise_time": "20:15", "x": "longer"}')

    assert server._signature(tmp_path) != before


class FakeSpeaker:
    def __init__(self):
        self.rendered = []

    def plan(self, turn):
        return {"segments": 2, "cached": 0, "credits": 40}

    def quota(self):
        return {"used": 100, "limit": 10000, "left": 9900}

    def render(self, turn):
        self.rendered.append(turn["id"])
        return [{"speaker": "narrator", "text": "Текст", "blocks": [0], "file": "a" * 64 + ".mp3"}]


@pytest.fixture
def talking(tmp_path):
    (tmp_path / "turn.json").write_text(json.dumps({"id": 7, "blocks": ["<p>x</p>"], "question": "?", "options": []}))
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / ("a" * 64 + ".mp3")).write_bytes(b"ID3fake-mp3")
    speaker = FakeSpeaker()
    httpd, token = server.make_server(tmp_path, port=0, token="T", views_provider=dict, speaker=speaker)
    server.serve_in_thread(httpd)
    yield httpd.server_port, speaker, tmp_path
    httpd.shutdown()
    httpd.server_close()


def test_render_returns_playable_segments_and_quota(talking):
    port, speaker, _ = talking

    status, body = call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})

    data = json.loads(body)
    assert status == 200 and speaker.rendered == [7]
    assert data["segments"][0]["url"] == "/audio/" + "a" * 64 + ".mp3" and data["quota"]["left"] == 9900


def test_plan_shows_cost_before_spending(talking):
    port, _, _ = talking

    status, body = call(port, "GET", "/api/speech/plan", headers={"X-Screen-Token": "T"})

    assert status == 200 and json.loads(body)["plan"]["credits"] == 40


def test_audio_file_is_served_with_token_only(talking):
    port, _, _ = talking
    name = "a" * 64 + ".mp3"

    assert call(port, "GET", f"/audio/{name}")[0] == 403
    status, body = call(port, "GET", f"/audio/{name}?token=T")
    assert status == 200 and body == b"ID3fake-mp3"


@pytest.mark.parametrize("name", ["../act.json", "..%2Fact.json", "x.mp3", "a" * 64 + ".wav", ("a" * 64) + ".mp3/../../x"])
def test_audio_path_traversal_is_refused(talking, name):
    port, _, _ = talking

    status, _ = call(port, "GET", f"/audio/{name}?token=T")

    assert status in (403, 404)


def test_speech_errors_become_http_errors(tmp_path):
    from lib.screen import speech

    (tmp_path / "turn.json").write_text(json.dumps({"id": 1, "blocks": ["<p>x</p>"], "question": "", "options": []}))

    class Broke(FakeSpeaker):
        def render(self, turn):
            raise speech.SpeechError("Not enough ElevenLabs credits: need 5, left 1", 402)

    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict, speaker=Broke())
    server.serve_in_thread(httpd)
    try:
        status, body = call(httpd.server_port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 402 and "credits" in json.loads(body)["error"]


def test_speech_is_off_without_a_speaker(running):
    port, token, _ = running

    status, _ = call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": token})
    _, state = call(port, "GET", "/api/state", headers={"X-Screen-Token": token})

    assert status == 503 and json.loads(state)["speech"] is False
