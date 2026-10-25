import pytest

from lib.screen import content


def turn(**extra):
    base = {"blocks": ["<p>Текст</p>"], "question": "Что делаете?", "options": ["Один", "Два"]}
    base.update(extra)
    return base


def test_valid_turn_passes_and_keeps_fields():
    result = content.validate_turn(turn(panels=[{"title": "ОБОЗ", "chips": ["12 бутылок"]}]))

    assert result["options"] == ["Один", "Два"]
    assert result["panels"][0]["title"] == "ОБОЗ"


@pytest.mark.parametrize("bad", [
    "<script>alert(1)</script>", "<p onclick='x()'>a</p>", "<a href='javascript:x()'>a</a>",
    "<iframe src='http://x'></iframe>", "<img src=x onerror=x()>", "<style>body{}</style>",
])
def test_dangerous_html_is_rejected(bad):
    with pytest.raises(ValueError):
        content.validate_turn(turn(blocks=[bad]))


def test_requires_blocks():
    with pytest.raises(ValueError):
        content.validate_turn(turn(blocks=[]))


def test_options_are_limited():
    with pytest.raises(ValueError):
        content.validate_turn(turn(options=[str(i) for i in range(9)]))


def test_options_must_be_plain_text():
    with pytest.raises(ValueError):
        content.validate_turn(turn(options=["<b>Один</b>"]))


def test_panels_shape_is_checked():
    with pytest.raises(ValueError):
        content.validate_turn(turn(panels=[{"title": "X", "bars": [{"label": "a"}]}]))


def test_captions_need_zone_and_title():
    good = {"zone": "tl", "title": "МАКСИМ", "text": "26 лет", "dot": [330, 150]}
    assert content.validate_captions([good]) == [good]
    with pytest.raises(ValueError):
        content.validate_captions([{"zone": "middle", "title": "X"}])
    with pytest.raises(ValueError):
        content.validate_captions([{"zone": "tl"}])


def _audio_turn(audio):
    return {"blocks": ["<p>Дождь идёт.</p>", "<p><b>Зоя:</b> «Ну!»</p>"], "audio": audio}


def test_audio_is_kept_and_normalised():
    turn = content.validate_turn(_audio_turn({
        "scene": {"environment_id": "big_room"},
        "speech": [{"who": "narrator", "text": "  Дождь   идёт. ", "blocks": [0]}, {"who": "Зоя", "text": "[laughs] Ну!", "cast": "female", "blocks": [1]}],
        "sfx": [{"cue": "mug slammed on a table", "tags": ["Tavern"], "block": 1}],
        "music": {"cue": "cheerful lute jig", "tags": ["tavern"]},
        "ambience": None}))

    audio = turn["audio"]
    assert audio["speech"][0] == {"who": "narrator", "text": "Дождь идёт.", "blocks": [0]}
    assert audio["speech"][1]["cast"] == "female" and audio["sfx"][0]["tags"] == ["tavern"] and audio["sfx"][0]["block"] == 1
    assert audio["sfx"][0]["seconds"] == 3 and audio["music"]["seconds"] == 90 and audio["ambience"] is None


@pytest.mark.parametrize("audio", [
    {"speech": [{"who": "narrator", "text": "<b>x</b>"}]},
    {"speech": [{"who": "", "text": "x"}]},
    {"speech": [{"who": "narrator", "text": "x", "blocks": [5]}]},
    {"speech": [{"who": "Зоя", "text": "x", "cast": "robot"}]},
    {"speech": [{"who": "Зоя", "text": "x", "effects": {"environment_id": "moon"}}]},
    {"scene": {"pan": 3}},
    {"sfx": [{"tags": ["x"]}]},
    {"sfx": [{"cue": "boom", "seconds": 60}]},
    {"sfx": [{"cue": "boom", "block": 9}]},
    {"sfx": [{"cue": "boom"}] * 7},
    {"music": {"cue": "x", "volume": 2}},
    {"voices": []},
])
def test_bad_audio_is_rejected(audio):
    with pytest.raises(ValueError):
        content.validate_turn(_audio_turn(audio))


def test_a_turn_without_audio_has_no_audio_field():
    assert "audio" not in content.validate_turn({"blocks": ["<p>a</p>"]})


def _scripted(*lines):
    return {"blocks": ["<h1>Глава</h1>", "<p>Дождь идёт отовсюду.</p>", "<p>Включая пол.</p>", "<p><b>Зоя:</b> «Можно я его потрогаю?»</p>",
                       "<p>🎲 Восприятие: 12</p>"], "audio": {"speech": list(lines)}}


def test_the_voice_script_may_add_tags_and_join_paragraphs_but_not_change_words():
    turn = content.validate_turn(_scripted({"who": "narrator", "text": "Дождь идёт отовсюду... [pause] Включая пол!", "blocks": [1, 2]},
                                           {"who": "Зоя", "text": "[whispers] Можно я его потрогаю?", "blocks": [3]}))

    assert len(turn["audio"]["speech"]) == 2


@pytest.mark.parametrize("lines", [
    [{"who": "narrator", "text": "Дождь идёт.", "blocks": [1, 2]}, {"who": "Зоя", "text": "Можно я его потрогаю?", "blocks": [3]}],
    [{"who": "narrator", "text": "Дождь идёт отовсюду. Включая пол.", "blocks": [1, 2]}],
    [{"who": "narrator", "text": "Дождь идёт отовсюду. Включая пол.", "blocks": [1, 2]}, {"who": "Зоя", "text": "Зоя: Можно я его потрогаю?", "blocks": [3]}],
    [{"who": "narrator", "text": "Дождь идёт отовсюду. Включая пол."}, {"who": "Зоя", "text": "Можно я его потрогаю?", "blocks": [3]}],
])
def test_a_rewritten_shortened_or_incomplete_voice_script_is_refused(lines):
    with pytest.raises(ValueError):
        content.validate_turn(_scripted(*lines))
