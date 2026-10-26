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


@pytest.mark.parametrize("good", [
    "<h1>Глава</h1>", "<h2>Сцена</h2>", "<h3>Подсцена</h3>", "<p class=\"lead\">Вступление</p>", "<div class=\"quest\"><b>ЗАДАНИЕ</b> найти багаж</div>",
    "<ul><li>а</li></ul>", "<ol><li>б</li></ol>", "<p>a<br>b<br/>c</p>", "<blockquote><em>x</em> <strong>y</strong> <span>z</span> <i>w</i></blockquote>",
    "<p>Тролль &amp; гном, 2 &gt; 1, &lt;3</p>", "Просто текст без тегов", "<p>javascript: это просто слово в тексте</p>",
])
def test_allowed_markup_passes_unchanged(good):
    assert content.validate_turn(turn(blocks=[good]))["blocks"] == [good]


@pytest.mark.parametrize("bad,named", [
    ("<img src=x>", "<img>"), ("<svg><circle r=1></circle></svg>", "<svg>"), ("<a href='#'>x</a>", "<a>"), ("<math><mi>x</mi></math>", "<math>"),
    ("<video src=x></video>", "<video>"), ("<input autofocus>", "<input>"), ("<details open>x</details>", "<details>"),
    ("<p style=\"color:red\">x</p>", "style"), ("<p id=\"x\">x</p>", "id"), ("<p data-x=\"1\">x</p>", "data-x"), ("<p class>x</p>", "class"),
    ("<p class=\"Lead\">x</p>", "class"), ("<p class=\"&#106;avascript:x\">x</p>", "javascript"), ("<a href=\"&#106;avascript:alert(1)\">x</a>", "<a>"),
    ("<p/onclick=alert(1)>x</p>", "onclick"), ("<p>a</p><!-- <script>alert(1)</script> -->", "comment"), ("<!-- note -->", "comment"),
    ("<!DOCTYPE html>", "DOCTYPE"), ("<?xml x?>", "xml"), ("<![CDATA[x]]>", "CDATA"),
])
def test_anything_outside_the_allowlist_is_refused_with_its_name(bad, named):
    with pytest.raises(ValueError, match=named):
        content.validate_turn(turn(blocks=["<p>ок</p>", bad]))


@pytest.mark.parametrize("bad", [
    "<p>hi</p><img src=x onerror=alert(1)",        # the page joins blocks: the next block would close this tag
    "<p class=\"lead", "<p>a < b</p>", "</p foo=\"<img src=x onerror=alert(1)>\">", "<scr<script>ipt>alert(1)</script>", "<p\x00>x</p>",
])
def test_a_tag_the_parser_did_not_fully_understand_is_refused(bad):
    with pytest.raises(ValueError):
        content.validate_turn(turn(blocks=[bad, "<p>следующий абзац</p>"]))


def test_the_error_says_which_block_is_wrong():
    with pytest.raises(ValueError, match="block 2: <img>"):
        content.validate_turn(turn(blocks=["<p>a</p>", "<p>b</p>", "<img src=x>"]))


@pytest.mark.parametrize("dot", ["330,150", '" onmouseover="alert(1)', [1, 2, 3], [1], [float("nan"), 5], [float("inf"), 5], [-1, 5], [5000, 5],
                                 [5, 2000], [True, 5], ["1", "2"], {"x": 1}])
def test_a_caption_dot_must_be_two_numbers_inside_the_art(dot):
    with pytest.raises(ValueError):
        content.validate_captions([{"zone": "tl", "title": "МАКСИМ", "dot": dot}])


def test_a_caption_without_a_dot_or_with_a_tuple_dot_is_fine():
    assert content.validate_captions([{"zone": "tr", "title": "Т", "kind": "note"}]) == [{"zone": "tr", "title": "Т", "kind": "note"}]
    assert content.validate_captions([{"zone": "tl", "title": "Т", "dot": (1672, 0.5)}])[0]["dot"] == [1672, 0.5]


@pytest.mark.parametrize("bar", [{"label": "HP", "value": "nan", "max": 20}, {"label": "HP", "value": 3, "max": "inf"},
                                 {"label": "HP", "value": 1e400, "max": 20}, {"label": "HP", "value": 3, "max": 0},
                                 {"label": "HP", "value": 3, "max": -5}])
def test_bars_need_finite_numbers_and_a_positive_max(bar):
    """NaN or Infinity in turn.json makes /api/state invalid JSON and freezes every open page."""
    with pytest.raises(ValueError, match="finite"):
        content.validate_panels([{"title": "HP", "bars": [bar]}])


def test_good_bars_still_pass():
    assert content.validate_panels([{"title": "HP", "bars": [{"label": "a", "value": "7", "max": 10}]}])[0]["bars"] == [
        {"label": "a", "value": 7.0, "max": 10.0}]
