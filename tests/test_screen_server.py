import http.client
import json
import re

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
    httpd, api, entry = make_sounding(tmp_path)
    yield httpd.server_port, api, entry
    _stop(httpd)


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


# ---- online hardening ----

def _serve(tmp_path, **kw):
    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict, **kw)
    server.serve_in_thread(httpd)
    return httpd


def _stop(httpd):
    httpd.shutdown()
    httpd.server_close()


class SlowApi:
    """ElevenLabs stand-in: every synthesis takes a moment; the account counter never moves (the estimate is logged)."""

    def __init__(self, delay=0.0):
        self.calls, self.delay = [], delay

    def tts(self, voice_id, body, output_format):
        import time
        time.sleep(self.delay)
        self.calls.append(body["text"])
        return b"MP3:" + body["text"].encode()

    def subscription(self):
        return {"character_count": 100, "character_limit": 100000}


def _voiced(tmp_path, api, text="Дверь закрывается."):
    from lib.screen import speech

    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR"}}))
    (tmp_path / "turn.json").write_text(json.dumps({"id": 1, "blocks": [f"<p>{text}</p>"], "question": "", "options": []}))
    return speech.Speaker(tmp_path, api, lambda: {})


def test_two_presses_on_the_same_turn_synthesize_it_once(tmp_path):
    import threading

    api = SlowApi(delay=0.4)
    httpd = _serve(tmp_path, speaker=_voiced(tmp_path, api))
    results = []
    try:
        threads = [threading.Thread(target=lambda: results.append(call(httpd.server_port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})))
                   for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    finally:
        _stop(httpd)

    assert [status for status, _ in results] == [200, 200] and len(api.calls) == 1


def test_a_turn_over_the_per_turn_credit_cap_is_refused_before_spending(tmp_path, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_TURN_CREDITS", "10")
    api = SlowApi()
    httpd = _serve(tmp_path, speaker=_voiced(tmp_path, api, "Очень длинная фраза рассказчика. " * 3))
    try:
        status, body = call(httpd.server_port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})
    finally:
        _stop(httpd)

    assert status == 402 and json.loads(body)["limit"] == "turn_credits" and api.calls == []


def test_the_daily_credit_budget_counts_what_was_really_spent(tmp_path, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_DAILY_CREDITS", "100")
    api = SlowApi()
    speaker = _voiced(tmp_path, api, "а" * 200)            # flash: 0.2 credits a character -> 40
    httpd = _serve(tmp_path, speaker=speaker)
    port = httpd.server_port
    try:
        assert call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})[0] == 200
        assert server.spent_today(tmp_path, "credits") == 40
        plan = json.loads(call(port, "GET", "/api/speech/plan", headers={"X-Screen-Token": "T"})[1])
        assert plan["budget"] == {"daily": 100, "turn": None, "spent_today": 40}

        (tmp_path / "turn.json").write_text(json.dumps({"id": 2, "blocks": ["<p>" + "б" * 400 + "</p>"]}))     # 80 more: over the day
        status, body = call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})
        assert status == 402 and json.loads(body)["limit"] == "daily_credits" and len(api.calls) == 1

        (tmp_path / "turn.json").write_text(json.dumps({"id": 3, "blocks": ["<p>" + "а" * 200 + "</p>"]}))     # cached: free
        assert call(port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})[0] == 200
    finally:
        _stop(httpd)
    assert len(api.calls) == 1 and server.spent_today(tmp_path, "credits") == 40


def test_spend_ledger_is_kept_per_local_day_and_trimmed(tmp_path):
    (tmp_path / "spend.json").write_text(json.dumps({f"2026-01-{d:02d}": {"credits": d} for d in range(1, 21)}))

    server.add_spend(tmp_path, "credits", 7)
    server.add_spend(tmp_path, "credits", 5)
    server.add_spend(tmp_path, "voice_bytes", 1000)

    data = json.loads((tmp_path / "spend.json").read_text())
    assert len(data) == server.SPEND_DAYS and server.spent_today(tmp_path, "credits") == 12 and server.spent_today(tmp_path, "voice_bytes") == 1000


class CountingSpeaker(FakeSpeaker):
    def __init__(self):
        super().__init__()
        self.quotas = 0

    def quota(self):
        self.quotas += 1
        return super().quota()


def test_the_plan_asks_the_account_quota_at_most_once_a_minute(tmp_path):
    (tmp_path / "turn.json").write_text(json.dumps({"id": 1, "blocks": ["<p>x</p>"]}))
    speaker = CountingSpeaker()
    httpd = _serve(tmp_path, speaker=speaker)
    try:
        for _ in range(3):
            assert json.loads(call(httpd.server_port, "GET", "/api/speech/plan", headers={"X-Screen-Token": "T"})[1])["quota"]["left"] == 9900
    finally:
        _stop(httpd)

    assert speaker.quotas == 1


def make_sounding(tmp_path):
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
    return _serve(tmp_path, speaker=speaker, director=audio.Director(tmp_path, api, speaker, freesound=NoFreesound())), api, entry


def test_sound_generation_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_SOUND_GENERATION", "0")
    httpd, api, entry = make_sounding(tmp_path)
    try:
        plan = json.loads(call(httpd.server_port, "GET", "/api/speech/plan", headers={"X-Screen-Token": "T"})[1])["plan"]
        data = json.loads(call(httpd.server_port, "POST", "/api/speech/render", b"{}", {"X-Screen-Token": "T"})[1])
    finally:
        _stop(httpd)

    assert api.calls == 0 and plan["sound_credits"] == 0 and plan["credits"] == 40
    assert data["audio"]["music"]["file"] == entry["file"] and data["audio"]["missing"] == ["thunder"]


def test_the_event_stream_asks_nginx_not_to_buffer(running):
    port, token, _ = running
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", f"/api/events?token={token}")
    response = conn.getresponse()
    header = response.getheader("X-Accel-Buffering")
    conn.close()

    assert header == "no"


def _raw_post(port, length_header, body=b"", path="/api/log"):
    """Send a POST by hand and keep the socket open: a server that waits for more body times out here."""
    import socket

    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    try:
        sock.sendall(f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Screen-Token: T0KEN\r\n{length_header}\r\n".encode() + body)
        return int(sock.recv(4096).split(b" ", 2)[1])
    finally:
        sock.close()


@pytest.mark.parametrize("length_header", ["", "Content-Length: abc\r\n", "Content-Length: -1\r\n", "Content-Length: 1e3\r\n"])
def test_a_missing_or_bad_content_length_is_refused_without_waiting(running, length_header):
    port, _, _ = running

    assert _raw_post(port, length_header, b'{"events": []}') == 400


def test_a_good_content_length_still_works_by_hand(running):
    port, _, _ = running
    body = b'{"events": []}'

    assert _raw_post(port, f"Content-Length: {len(body)}\r\n", body) == 200


def test_too_many_waiting_actions_are_refused(running, monkeypatch):
    from lib.screen import cli

    monkeypatch.setenv("DM_SCREEN_MAX_PENDING", "2")
    _, _, tmp_path = running
    httpd = _serve(tmp_path)
    port = httpd.server_port
    send = lambda text: call(port, "POST", "/api/action", json.dumps({"who": "Ринсвинд", "source": "text", "text": text}), {"X-Screen-Token": "T"})
    try:
        assert [send("раз")[0], send("два")[0]] == [200, 200]
        status, body = send("три")
        assert status == 429 and json.loads(body)["limit"] == "pending" and len(inbox.read_events(tmp_path)) == 2
        cli.write_cursor(tmp_path, 2)          # the master took them
        assert send("три")[0] == 200
    finally:
        _stop(httpd)


def test_the_daily_microphone_limit_answers_429(tmp_path, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_DAILY_VOICE_MB", str(150 / 1024 / 1024))
    heard = []
    httpd = _serve(tmp_path, transcriber=lambda audio, ctype: heard.append(len(audio)) or "привет")
    try:
        first = call(httpd.server_port, "POST", "/api/voice", b"x" * 100, {"X-Screen-Token": "T"})
        second = call(httpd.server_port, "POST", "/api/voice", b"x" * 100, {"X-Screen-Token": "T"})
    finally:
        _stop(httpd)

    assert first[0] == 200 and second[0] == 429 and json.loads(second[1])["limit"] == "voice_mb" and heard == [100]


def _get(port, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, dict(response.getheaders()), data


@pytest.mark.parametrize("header,status,body,content_range", [
    ("bytes=0-1", 206, b"ID", "bytes 0-1/11"),
    ("bytes=3-", 206, b"fake-mp3", "bytes 3-10/11"),
    ("bytes=-3", 206, b"mp3", "bytes 8-10/11"),
    ("bytes=5-500", 206, b"ke-mp3", "bytes 5-10/11"),
    ("bytes=50-", 416, None, "bytes */11"),
    ("bytes=5-3", 200, b"ID3fake-mp3", None),
    ("bytes=0-1,4-5", 200, b"ID3fake-mp3", None),
])
def test_audio_answers_byte_ranges_for_safari(talking, header, status, body, content_range):
    port, _, _ = talking

    got, headers, data = _get(port, f"/audio/{'a' * 64}.mp3?token=T", {"Range": header})

    assert got == status and headers.get("Accept-Ranges") == "bytes" and headers.get("Content-Range") == content_range
    if body is not None:
        assert data == body and headers["Content-Length"] == str(len(body))


def test_library_sounds_answer_byte_ranges_too(tmp_path):
    httpd, _, entry = make_sounding(tmp_path)
    try:
        status, headers, data = _get(httpd.server_port, f"/library/{entry['file']}?token=T", {"Range": "bytes=1-2"})
    finally:
        _stop(httpd)

    assert status == 206 and data == b"UT" and headers["Content-Range"] == "bytes 1-2/4"


def _campaign_screen(tmp_path, name="pratchett-dungeon"):
    sdir = tmp_path / "world-state" / "campaigns" / name / "screen"
    sdir.mkdir(parents=True)
    return sdir


def test_state_carries_the_online_master_status_of_this_campaign(tmp_path):
    import os

    sdir = _campaign_screen(tmp_path)
    status_file = tmp_path / "world-state" / "online-play-status.json"
    assert "master" not in server.build_state(sdir, dict)
    before = server._signature(sdir)

    status_file.write_text(json.dumps({"pid": os.getpid(), "campaign": "pratchett-dungeon", "port": 18116, "state": "resting", "last_error": "hour limit"}))

    assert server.build_state(sdir, dict)["master"] == {"state": "resting", "last_error": "hour limit"}
    assert server._signature(sdir) != before          # open pages hear about it at once
    status_file.write_text(json.dumps({"pid": 99999999, "campaign": "pratchett-dungeon", "state": "thinking"}))
    assert server.build_state(sdir, dict)["master"]["state"] == "offline"
    status_file.write_text(json.dumps({"pid": os.getpid(), "campaign": "war-and-peace", "state": "thinking"}))
    assert "master" not in server.build_state(sdir, dict)


def _template_js(names):
    """The I18N table and the named functions of the page script, cut out for node."""
    text = server.TEMPLATE.read_text(encoding="utf-8")
    start = text.index("const I18N=")
    parts = [text[start:text.index("}};", start) + 3]]
    for name in names:
        at = text.index(f"function {name}(")
        depth, i = 0, text.index("{", at)
        while True:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
            if depth == 0:
                break
        parts.append(text[at:i])
    return "\n".join(parts)


def test_the_page_names_each_server_limit_and_the_master_state():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = _template_js(["limitText", "masterNote"]) + """
let L=I18N.ru;const t=k=>L[k];
const note=(m,w)=>{const n=masterNote(m,w);return n&&t(n.k)};
console.log(JSON.stringify([limitText(429,{limit:'pending'}),limitText(429,{limit:'voice_mb'}),limitText(402,{limit:'daily_credits'}),
  limitText(402,{limit:'turn_credits'}),limitText(402,{error:'x'}),limitText(500,{}),
  note({state:'thinking'},false),note({state:'resting'},false),note({state:'paused'},true),note(null,true),note({state:'idle'},false),
  masterNote({state:'error',last_error:'boom'},false).title]))"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

    assert out == ["Мастер ещё не разобрал прошлые действия: дождитесь ответа", "Микрофон на сегодня исчерпан: напишите действие текстом",
                   "Озвучка на сегодня исчерпана: читаем глазами", "Этот ход слишком длинный для озвучки", "Кончились кредиты озвучки", None,
                   "Мастер думает", "Мастер отдыхает (лимит)", "Пауза", "Мастер думает", None, "boom"]


def test_every_page_request_that_can_hit_a_limit_shows_it():
    text = server.TEMPLATE.read_text(encoding="utf-8")

    assert text.count("limitText(r.status,j)") == 3                     # actions, speech, microphone
    assert "masterNote(S.master,S.waiting)" in text and "S.master=st.master" in text
    keys = lambda lang: set(re.findall(r"(\w+):", text[text.index(f" {lang}:{{"):].split("}", 1)[0]))
    assert {"tooMany", "voiceLimit", "dailyLimit", "turnLimit", "noCredits", "mRest", "mPause", "mError", "mOff"} <= keys("ru") & keys("en")


def test_one_spend_file_is_shared_across_campaign_screens(tmp_path, monkeypatch):
    """The online table switches campaigns; the day's budget must not start again with the next screen."""
    alpha, beta = tmp_path / "alpha" / "screen", tmp_path / "beta" / "screen"
    monkeypatch.setenv("DM_SCREEN_SPEND_FILE", str(tmp_path / "usage" / "screen-spend.json"))

    server.add_spend(alpha, "credits", 15000)

    assert server.spent_today(beta, "credits") == 15000 and not (alpha / "spend.json").exists()
    monkeypatch.delenv("DM_SCREEN_SPEND_FILE")
    assert server.spent_today(beta, "credits") == 0          # the laptop default: one ledger per screen


def test_a_capped_spend_is_checked_and_added_in_one_step(tmp_path):
    import threading

    results = []
    threads = [threading.Thread(target=lambda: results.append(server.add_spend(tmp_path, "voice_bytes", 100, cap=250))) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert results.count(True) == 2 and server.spent_today(tmp_path, "voice_bytes") == 200


def test_parallel_actions_cannot_overshoot_the_pending_cap(tmp_path, monkeypatch):
    import threading

    monkeypatch.setenv("DM_SCREEN_MAX_PENDING", "1")
    httpd = _serve(tmp_path)
    statuses = []
    post = lambda: statuses.append(call(httpd.server_port, "POST", "/api/action", json.dumps({"who": "Ринсвинд", "text": "бежать"}),
                                        {"X-Screen-Token": "T"})[0])
    try:
        threads = [threading.Thread(target=post) for _ in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    finally:
        _stop(httpd)

    assert sorted(statuses) == [200] + [429] * 5 and len(inbox.read_events(tmp_path)) == 1


def test_a_credit_budget_turns_the_pages_auto_speech_off(tmp_path, monkeypatch):
    httpd = _serve(tmp_path)
    try:
        free = json.loads(call(httpd.server_port, "GET", "/api/state", headers={"X-Screen-Token": "T"})[1])
    finally:
        _stop(httpd)
    monkeypatch.setenv("DM_SCREEN_DAILY_CREDITS", "15000")
    httpd = _serve(tmp_path)
    try:
        capped = json.loads(call(httpd.server_port, "GET", "/api/state", headers={"X-Screen-Token": "T"})[1])
    finally:
        _stop(httpd)

    assert free["auto_speech"] is True and capped["auto_speech"] is False
    text = server.TEMPLATE.read_text(encoding="utf-8")
    assert "if(st.auto_speech===false){$('autoBtn').style.display='none';if(SP.auto)setAuto(false)}" in text


def test_nginx_rate_limits_are_not_shown_as_pending_actions_and_keep_auto_speech():
    import shutil
    import subprocess

    text = server.TEMPLATE.read_text(encoding="utf-8")
    assert "if(r.status===402&&SP.auto)setAuto(false)" in text and "lim&&SP.auto" not in text
    assert '"limit":"rate"' in (server.TEMPLATE.parents[2] / "ops" / "play" / "nginx-dnd-play-sslip").read_text(encoding="utf-8")
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = _template_js(["limitText"]) + """
let L=I18N.ru;const t=k=>L[k];
console.log(JSON.stringify([limitText(429,{error:'too many requests, wait a minute',limit:'rate'}),limitText(429,{error:'x'}),
  limitText(429,{limit:'pending'}),limitText(429,{limit:'voice_mb'})]))"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

    assert out == ["Слишком часто: подождите минуту", "Слишком часто: подождите минуту",
                   "Мастер ещё не разобрал прошлые действия: дождитесь ответа", "Микрофон на сегодня исчерпан: напишите действие текстом"]


def test_skill_values_from_the_world_are_escaped_in_the_side_panel():
    text = server.TEMPLATE.read_text(encoding="utf-8")

    assert "<b>+${esc(typeof v==='object'?v.total:v)}</b>" in text
