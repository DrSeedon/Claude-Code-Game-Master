import json

import pytest

from lib.screen import speech


def block(html):
    return html


def test_script_splits_narration_and_dialogue():
    blocks = [
        "<h1>Двор</h1>",
        "<p>Аграфена Тихоновна смотрит на воз.</p>",
        "<p>Максим ставит ящики на стол.</p>",
        "<p><b>Аграфена Тихоновна:</b> «Ящик на стол. Без разговоров.»</p>",
        "<p>Дверь захлопывается.</p>",
    ]

    script = speech.script_from_blocks(blocks)

    assert [(s["speaker"], s["text"]) for s in script] == [
        ("narrator", "Аграфена Тихоновна смотрит на воз. Максим ставит ящики на стол."),
        ("Аграфена Тихоновна", "Ящик на стол. Без разговоров."),
        ("narrator", "Дверь захлопывается."),
    ]
    assert script[0]["blocks"] == [1, 2] and script[1]["blocks"] == [3] and script[2]["blocks"] == [4]


def test_script_skips_dice_headings_lists_and_ui_blocks():
    blocks = ["<h1>Т</h1>", "<p><b>🎲 Торговля против 13:</b> 15 + 3 = 18, успех.</p>", "<ul><li>цель</li></ul>",
              "<div class=\"quest\">Задание</div>", "<p>Текст.</p>"]

    assert [s["text"] for s in speech.script_from_blocks(blocks)] == ["Текст."]


def test_long_narration_is_chunked_on_sentence_boundaries():
    sentence = "Это достаточно длинное предложение для проверки. "
    blocks = [f"<p>{sentence * 4}</p>" for _ in range(8)]

    script = speech.script_from_blocks(blocks, max_chars=600)

    assert all(len(s["text"]) <= 600 for s in script) and len(script) > 1
    assert "".join(s["text"] for s in script).replace(" ", "") == ("".join(sentence * 4 for _ in range(8))).replace(" ", "").strip()


def test_tags_and_entities_are_stripped():
    script = speech.script_from_blocks(["<p>Он сказал <b>тихо</b> &amp; ушёл.</p>"])

    assert script[0]["text"] == "Он сказал тихо & ушёл."


CONFIG = {"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR"}, "default": {"voice_id": "DEF"}}
CHARACTERS = {"аграфена тихоновна": {"voice_id": "VIC", "effects": {"pan": 0.3}}, "максим астраханцев": {"voice_id": "NIK"}}


def test_voice_resolution_order():
    narrator = speech.resolve_voice("narrator", CONFIG, CHARACTERS)
    agrafena = speech.resolve_voice("Аграфена Тихоновна", CONFIG, CHARACTERS)
    maxim = speech.resolve_voice("Максим", CONFIG, CHARACTERS)
    stranger = speech.resolve_voice("Лакей", CONFIG, CHARACTERS)

    assert (narrator["voice_id"], agrafena["voice_id"], maxim["voice_id"], stranger["voice_id"]) == ("NARR", "VIC", "NIK", "DEF")
    assert agrafena["effects"] == {"pan": 0.3}


def test_missing_narrator_voice_fails_loudly():
    with pytest.raises(speech.SpeechUnavailable):
        speech.resolve_voice("narrator", {"model": "x"}, {})


@pytest.mark.parametrize("effects", [{"pan": 2}, {"distance": -0.1}, {"environment_id": "moon_base"}, {"unknown": 1}])
def test_bad_effects_are_rejected(effects):
    with pytest.raises(ValueError):
        speech.validate_effects(effects)


def test_good_effects_pass():
    assert speech.validate_effects({"environment_id": "hall", "distance": 0.3, "pan": -0.5}) == {"environment_id": "hall", "distance": 0.3, "pan": -0.5}


def test_credit_estimate_uses_model_multiplier():
    segments = [{"speaker": "narrator", "text": "а" * 100}]

    assert speech.estimate_credits(segments, {"model": "eleven_flash_v2_5"}) == 20
    assert speech.estimate_credits(segments, {"model": "eleven_v4"}) == 45
    assert speech.estimate_credits(segments, {"model": "eleven_multilingual_v2"}) == 100


class FakeApi:
    def __init__(self):
        self.calls = []

    def tts(self, voice_id, body, output_format):
        self.calls.append((voice_id, body, output_format))
        return b"MP3:" + body["text"].encode()

    def subscription(self):
        return {"character_count": 100, "character_limit": 10000}


@pytest.fixture
def speaker(tmp_path):
    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR", "effects": {"environment_id": "hall"}},
                                                      "default": {"voice_id": "DEF"}}))
    api = FakeApi()
    return speech.Speaker(tmp_path, api=api, characters=lambda: {"аграфена тихоновна": {"voice_id": "VIC"}}), api, tmp_path


TURN = {"id": 4, "blocks": ["<p>Дверь закрывается.</p>", "<p><b>Аграфена Тихоновна:</b> «Всё.»</p>"]}


def test_render_synthesizes_once_and_reuses_the_cache(speaker):
    spk, api, tmp_path = speaker

    first = spk.render(TURN)
    second = spk.render(TURN)

    assert len(api.calls) == 2 and [s["speaker"] for s in first] == ["narrator", "Аграфена Тихоновна"]
    assert first == second
    assert all((tmp_path / "audio" / s["file"]).read_bytes().startswith(b"MP3:") for s in first)


def test_request_body_carries_model_voice_settings_and_effects(speaker):
    spk, api, _ = speaker

    spk.render(TURN)

    voice_id, body, fmt = api.calls[0]
    assert voice_id == "NARR" and body["model_id"] == "eleven_flash_v2_5" and body["language_code"] == "ru"
    assert body["audio_effects"] == {"environment_id": "hall"} and fmt == "mp3_44100_128"
    assert api.calls[1][0] == "VIC" and "audio_effects" not in api.calls[1][1]


def test_changing_the_voice_makes_new_audio(speaker):
    spk, api, tmp_path = speaker
    spk.render(TURN)
    cfg = json.loads((tmp_path / "speech.json").read_text())
    cfg["narrator"]["voice_id"] = "OTHER"
    (tmp_path / "speech.json").write_text(json.dumps(cfg))

    spk.render(TURN)

    assert len(api.calls) == 3 and api.calls[2][0] == "OTHER"


def test_plan_reports_cost_and_cached_state(speaker):
    spk, _, _ = speaker

    before = spk.plan(TURN)
    spk.render(TURN)
    after = spk.plan(TURN)

    assert before["credits"] > 0 and before["cached"] == 0
    assert after["credits"] == 0 and after["cached"] == 2


def test_render_refuses_when_credits_are_not_enough(speaker):
    spk, api, _ = speaker
    api.subscription = lambda: {"character_count": 9998, "character_limit": 10000}

    with pytest.raises(speech.SpeechError) as error:
        spk.render(TURN)

    assert "кредит" in str(error.value).lower() or "credit" in str(error.value).lower()
    assert api.calls == []


def test_quota_reads_the_subscription(speaker):
    spk, _, _ = speaker

    assert spk.quota() == {"used": 100, "limit": 10000, "left": 9900, "account": 100}


def test_spending_is_logged_and_wins_over_a_stale_account_counter(speaker):
    spk, api, tmp_path = speaker      # the account counter says 100 used
    spk.render(TURN)

    ledger = [json.loads(line) for line in (tmp_path / "audio" / "usage.jsonl").read_text().splitlines()]
    assert sum(entry["credits"] for entry in ledger) == 5    # 'Дверь закрывается.' (18) + 'Всё.' (4) at 0.2, rounded up

    api.subscription = lambda: {"character_count": 0, "character_limit": 10000}
    assert spk.quota()["used"] == 5 and spk.quota()["left"] == 9995


def test_old_spending_does_not_count(speaker):
    spk, api, tmp_path = speaker
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "audio" / "usage.jsonl").write_text(json.dumps({"ts": "2025-01-01T00:00:00Z", "credits": 5000}) + "\n")
    api.subscription = lambda: {"character_count": 0, "character_limit": 10000}

    assert spk.quota()["used"] == 0


def test_speed_goes_to_voice_settings_but_not_for_v4(tmp_path):
    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR", "speed": 1.12},
                                                      "default": {"voice_id": "DEF", "model": "eleven_v4", "speed": 1.1}}))
    api = FakeApi()
    spk = speech.Speaker(tmp_path, api=api, characters=lambda: {})

    spk.render({"id": 1, "blocks": ["<p>Диктор.</p>", "<p><b>Некто:</b> «Реплика.»</p>"]})

    assert api.calls[0][1]["voice_settings"]["speed"] == 1.12
    assert "speed" not in api.calls[1][1]["voice_settings"]


def test_speed_does_not_change_old_cache_names_when_unset():
    voice = {"voice_id": "V", "model": "m", "stability": 0.5, "similarity_boost": 0.75, "effects": {}}
    config = {"output_format": "f", "language": "ru"}

    before = speech._cache_key(voice, "текст", config)

    assert speech._cache_key({**voice, "speed": None}, "текст", config) == before
    assert speech._cache_key({**voice, "speed": 1.1}, "текст", config) != before


def test_extra_voices_in_the_config_are_used_by_name(tmp_path):
    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR"},
                                                      "voices": {"Голос 1 · Daniel": {"voice_id": "DAN"}}}))
    api = FakeApi()
    spk = speech.Speaker(tmp_path, api=api, characters=lambda: {})

    spk.render({"id": 1, "blocks": ["<p><b>Голос 1 · Daniel:</b> «Проба.»</p>"]})

    assert api.calls[0][0] == "DAN"


@pytest.mark.parametrize("speed", [0.5, 1.5, "fast"])
def test_bad_speed_is_rejected(speed):
    from lib.screen import voices

    with pytest.raises(ValueError):
        voices.make_profile({"voice_id": "V" * 20, "name": "V"}, speed=speed)


class RichApi(FakeApi):
    def tts(self, voice_id, body, output_format):
        self.calls.append((voice_id, body, output_format))
        return b"MP3:" + body["text"].encode(), {"request-id": "req-9", "x-character-count": "11", "history-item-id": "h-1"}


def test_every_synthesis_and_cache_hit_is_logged_with_price_and_ids(tmp_path):
    from lib.screen import eventlog

    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR", "name": "Nikolay", "speed": 1.1},
                                                      "default": {"voice_id": "DEF"}}))
    spk = speech.Speaker(tmp_path, api=RichApi(), characters=lambda: {})
    turn = {"id": 5, "blocks": ["<p>Дверь закрывается.</p>"]}

    spk.render(turn)
    spk.render(turn)

    tts = eventlog.read(tmp_path, kinds={"tts"})
    fresh, cached = tts[0], tts[1]
    assert fresh["cached"] is False and fresh["credits"] == 4 and fresh["chars"] == 18 and fresh["model"] == "eleven_flash_v2_5"
    assert fresh["voice_id"] == "NARR" and fresh["voice"] == "Nikolay" and fresh["speed"] == 1.1 and fresh["request_id"] == "req-9"
    assert fresh["api_chars"] == "11" and fresh["ms"] >= 0 and fresh["turn"] == 5 and fresh["text"] == "Дверь закрывается."
    assert cached["cached"] is True and cached["credits"] == 0
    render = eventlog.read(tmp_path, kinds={"speech_render"})
    assert render[0]["segments"] == 1 and render[0]["credits"] == 4 and render[0]["quota_before"]["used"] == 100


def test_a_failed_synthesis_is_logged_with_its_status(tmp_path):
    from lib.screen import eventlog

    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_flash_v2_5", "narrator": {"voice_id": "NARR"}}))

    class Broken(FakeApi):
        def tts(self, voice_id, body, output_format):
            raise speech.SpeechError("ElevenLabs: Free users cannot use library voices via the API.", 402)

    with pytest.raises(speech.SpeechError):
        speech.Speaker(tmp_path, api=Broken(), characters=lambda: {}).render({"id": 1, "blocks": ["<p>Текст.</p>"]})

    failed = eventlog.read(tmp_path, kinds={"tts"})[0]
    assert failed["ok"] is False and failed["status"] == 402 and "library voices" in failed["error"]


SCRIPTED = {"id": 5, "blocks": ["<p>Таверна гудит.</p>", "<p><b>Зоя:</b> «Можно я его потрогаю?»</p>"],
            "audio": {"scene": {"environment_id": "big_room", "background_noise_id": "cafe"},
                      "speech": [{"who": "narrator", "text": "Таверна гудит, [pause] как улей.", "blocks": [0]},
                                 {"who": "Зоя", "text": "[whispers] Можно я его потрогаю?", "blocks": [1], "effects": {"distance": 0.2}},
                                 {"who": "Трактирщица", "text": "Не трогать!", "cast": "female"}]}}


@pytest.fixture
def cast_speaker(tmp_path):
    (tmp_path / "speech.json").write_text(json.dumps({"model": "eleven_v4", "narrator": {"voice_id": "NARR"}, "default": {"voice_id": "MALE"},
                                                      "cast": {"female": {"voice_id": "FEM"}}}))
    api = FakeApi()
    return speech.Speaker(tmp_path, api=api, characters=lambda: {"зоя": {"voice_id": "ZOYA", "effects": {"pan": -0.3}}}), api, tmp_path


def test_the_voice_script_replaces_the_shown_blocks(cast_speaker):
    spk, api, _ = cast_speaker

    segments = spk.render(SCRIPTED)

    assert [s["speaker"] for s in segments] == ["narrator", "Зоя", "Трактирщица"]
    assert [call[1]["text"] for call in api.calls] == ["Таверна гудит, [pause] как улей.", "[whispers] Можно я его потрогаю?", "Не трогать!"]
    assert segments[1]["text"] == "Можно я его потрогаю?" and segments[0]["blocks"] == [0] and segments[2]["blocks"] == []


def test_scene_effects_reach_characters_but_not_the_narrator(cast_speaker):
    spk, api, _ = cast_speaker

    spk.render(SCRIPTED)

    bodies = {call[0]: call[1] for call in api.calls}
    assert "audio_effects" not in bodies["NARR"]
    assert bodies["ZOYA"]["audio_effects"] == {"environment_id": "big_room", "background_noise_id": "cafe", "pan": -0.3, "distance": 0.2}
    assert bodies["FEM"]["audio_effects"] == {"environment_id": "big_room", "background_noise_id": "cafe"}


def test_a_line_cast_picks_the_campaign_voice_for_an_unknown_character(cast_speaker):
    spk, api, _ = cast_speaker
    turn = {"id": 1, "blocks": ["<p>x</p>"], "audio": {"speech": [{"who": "Прохожий", "text": "Эй!"}, {"who": "Торговка", "text": "Ой!", "cast": "female"}]}}

    spk.render(turn)

    assert [call[0] for call in api.calls] == ["MALE", "FEM"]


def test_a_turn_without_a_voice_script_still_reads_its_blocks(cast_speaker):
    spk, api, _ = cast_speaker

    spk.render({"id": 2, "blocks": ["<p>Тишина.</p>"], "audio": {"scene": {"environment_id": "hall"}}})

    assert [(call[0], call[1]["text"]) for call in api.calls] == [("NARR", "Тишина.")]


def test_spending_records_the_account_counter_move_not_the_estimate(speaker):
    spk, api, tmp_path = speaker
    counts = iter([100, 104, 104])
    api.subscription = lambda: {"character_count": next(counts), "character_limit": 10000}

    spk.render(TURN)

    ledger = [json.loads(line) for line in (tmp_path / "audio" / "usage.jsonl").read_text().splitlines()]
    assert ledger[0]["credits"] == 4 and "estimated" not in ledger[0] and len(ledger) == 1


def test_a_lagging_account_counter_falls_back_to_the_marked_estimate(speaker):
    spk, _, tmp_path = speaker      # the fake counter never moves

    spk.render(TURN)

    ledger = [json.loads(line) for line in (tmp_path / "audio" / "usage.jsonl").read_text().splitlines()]
    assert ledger == [{"ts": ledger[0]["ts"], "credits": 5, "estimated": True}]


def test_a_failed_line_still_records_what_was_made(speaker):
    spk, api, tmp_path = speaker
    real = api.tts

    def flaky(voice_id, body, fmt):
        if voice_id == "VIC":
            raise speech.SpeechError("boom", 500)
        return real(voice_id, body, fmt)
    api.tts = flaky

    with pytest.raises(speech.SpeechError):
        spk.render(TURN)

    ledger = [json.loads(line) for line in (tmp_path / "audio" / "usage.jsonl").read_text().splitlines()]
    assert sum(entry["credits"] for entry in ledger) == 4    # only 'Дверь закрывается.' (18 at 0.2, rounded up)


def test_spoken_text_drops_performance_tags():
    assert speech.spoken_text("[sighs] Ну вот. [laughs] Опять.") == "Ну вот. Опять."


def test_an_old_estimate_stops_counting_once_the_account_had_time_to_catch_up(speaker):
    spk, api, tmp_path = speaker
    (tmp_path / "audio").mkdir(exist_ok=True)
    fresh = speech.datetime.now(speech.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [{"ts": "2026-01-01T00:00:00Z", "credits": 9000, "estimated": True}, {"ts": fresh, "credits": 300, "estimated": True}]
    (tmp_path / "audio" / "usage.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    api.subscription = lambda: {"character_count": 0, "character_limit": 10000}

    assert spk.quota()["used"] == 300
