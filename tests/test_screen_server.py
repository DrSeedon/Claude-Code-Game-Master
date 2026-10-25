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


def _events(tmp_path, **kw):
    from lib.screen import eventlog
    return eventlog.read(tmp_path, **kw)


def test_every_api_call_is_logged_with_status_and_time(running):
    port, token, tmp_path = running

    call(port, "POST", "/api/action", json.dumps({"who": "Катя", "source": "button", "text": "ход"}), {"X-Screen-Token": token})
    call(port, "GET", "/api/state")           # forbidden: no token

    http = _events(tmp_path, kinds={"http"})
    assert [(e["path"], e["status"]) for e in http] == [("/api/action", 200), ("/api/state", 403)]
    assert all("ms" in e for e in http)


def test_player_actions_and_voice_words_are_logged_in_full(running):
    port, token, tmp_path = running
    call(port, "POST", "/api/action", json.dumps({"who": "Оба", "source": "voice", "text": "Показать товар"}), {"X-Screen-Token": token})

    action = _events(tmp_path, kinds={"action"})[0]

    assert action["who"] == "Оба" and action["source"] == "voice" and action["text"] == "Показать товар" and action["id"] == 1


def test_voice_details_are_logged(tmp_path):
    details = {"text": "привет мир", "words": [{"word": "привет", "confidence": 0.99, "start": 0.1, "end": 0.5}], "seconds": 2.4, "request_id": "dg-1", "fallback": False}
    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict, transcriber=lambda audio, ctype: details)
    server.serve_in_thread(httpd)
    try:
        status, body = call(httpd.server_port, "POST", "/api/voice", b"x" * 100, {"X-Screen-Token": "T", "Content-Type": "audio/webm"})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 200 and json.loads(body)["text"] == "привет мир"
    stt = _events(tmp_path, kinds={"stt"})[0]
    assert stt["text"] == "привет мир" and stt["words"][0]["confidence"] == 0.99 and stt["seconds"] == 2.4 and stt["bytes"] == 100


def test_an_unhandled_exception_is_logged_and_answered(tmp_path):
    def boom():
        raise RuntimeError("views exploded")

    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=boom)
    server.serve_in_thread(httpd)
    try:
        status, body = call(httpd.server_port, "GET", "/api/state", headers={"X-Screen-Token": "T"})
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 500
    error = _events(tmp_path, kinds={"error"})[0]
    assert "views exploded" in error["message"] and "Traceback" in error["traceback"]


def test_the_page_can_report_its_own_events_and_errors(running):
    port, token, tmp_path = running
    batch = {"events": [{"kind": "ui.click", "target": "speak"}, {"kind": "ui.error", "message": "boom", "stack": "at x"}, {"kind": "not-ui", "x": 1}]}

    status, _ = call(port, "POST", "/api/log", json.dumps(batch), {"X-Screen-Token": token})

    assert status == 200
    kinds = [e["kind"] for e in _events(tmp_path) if e["kind"].startswith("ui.")]
    assert kinds == ["ui.click", "ui.error"]


def test_page_log_endpoint_needs_the_token_and_limits_size(running):
    port, token, tmp_path = running

    assert call(port, "POST", "/api/log", json.dumps({"events": [{"kind": "ui.click"}]}))[0] == 403
    huge = {"events": [{"kind": "ui.x", "blob": "я" * 1500}] * 100}
    call(port, "POST", "/api/log", json.dumps(huge, ensure_ascii=False).encode(), {"X-Screen-Token": token})
    assert call(port, "POST", "/api/log", b"x" * (300 * 1024), {"X-Screen-Token": token})[0] == 413
    assert len([e for e in _events(tmp_path) if e["kind"] == "ui.x"]) <= 50
    assert all(len(json.dumps(e)) < 6000 for e in _events(tmp_path) if e["kind"] == "ui.x")


@pytest.fixture
def sounding(tmp_path):
    from lib.screen import audio

    class Api:
        def __init__(self):
            self.calls = 0

        def sound(self, text, seconds=None, loop=False, **_):
            self.calls += 1
            return b"SFX"

    class Spk(FakeSpeaker):
        dir = tmp_path

        def spent(self, before, estimate):
            return estimate

    class NoFreesound:
        def search(self, query, kind):
            return None

    lib = audio.Library(tmp_path)
    entry = lib.add(b"LUTE", "mp3", "music", "Tavern lute", ["tavern"], source="opengameart", attribution="«Tavern lute» CC0")
    (tmp_path / "turn.json").write_text(json.dumps({"id": 9, "blocks": ["<p>x</p>"],
                                                    "audio": {"music": {"cue": "lute", "tags": ["tavern"], "seconds": 90, "volume": 0.3},
                                                              "sfx": [{"cue": "thunder", "tags": [], "seconds": 2, "volume": 0.9, "block": 0}]}}))
    api, speaker = Api(), Spk()
    director = audio.Director(tmp_path, api, speaker, freesound=NoFreesound())
    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict, speaker=speaker, director=director)
    server.serve_in_thread(httpd)
    yield httpd.server_port, api, entry
    httpd.shutdown()
    httpd.server_close()


def test_free_sounds_come_from_the_library_without_generating(sounding):
    port, api, entry = sounding

    status, body = call(port, "GET", "/api/audio", headers={"X-Screen-Token": "T"})

    data = json.loads(body)["audio"]
    assert status == 200 and api.calls == 0
    assert data["music"]["url"] == "/library/" + entry["file"] and data["music"]["credit"] == "«Tavern lute» CC0"
    assert data["sfx"] == [] and data["missing"] == ["thunder"]


def test_plan_adds_the_sounds_the_library_lacks(sounding):
    port, _, _ = sounding

    plan = json.loads(call(port, "GET", "/api/speech/plan", headers={"X-Screen-Token": "T"})[1])["plan"]

    assert plan["speech_credits"] == 40 and plan["sound_credits"] == 20 and plan["credits"] == 60 and plan["sounds_found"] == 1


def test_render_generates_missing_sounds_and_returns_them(sounding):
    port, api, _ = sounding

    data = json.loads(call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})[1])

    assert api.calls == 1 and data["audio"]["sfx"][0]["block"] == 0 and data["audio"]["music"]["title"] == "Tavern lute"


def test_library_files_need_the_token_and_a_clean_name(sounding):
    port, _, entry = sounding

    assert call(port, "GET", f"/library/{entry['file']}")[0] == 403
    status, body = call(port, "GET", f"/library/{entry['file']}?token=T")
    assert status == 200 and body == b"LUTE"
    assert call(port, "GET", "/library/..%2Findex.json?token=T")[0] == 404
