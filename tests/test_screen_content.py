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
