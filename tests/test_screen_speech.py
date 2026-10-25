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

    assert speech.estimate_credits(segments, {"model": "eleven_flash_v2_5"}) == 50
    assert speech.estimate_credits(segments, {"model": "eleven_v4"}) == 100


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
    api.subscription = lambda: {"character_count": 9990, "character_limit": 10000}

    with pytest.raises(speech.SpeechError) as error:
        spk.render(TURN)

    assert "кредит" in str(error.value).lower() or "credit" in str(error.value).lower()
    assert api.calls == []


def test_quota_reads_the_subscription(speaker):
    spk, _, _ = speaker

    assert spk.quota() == {"used": 100, "limit": 10000, "left": 9900}
