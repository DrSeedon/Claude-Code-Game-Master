import pytest

from lib.narrator_style import render_narrator_style


def test_embedded_custom_style_keeps_voice_rules_and_limits(tmp_path):
    text = render_narrator_style(tmp_path, {
        "name": "Anime Adventure", "description": "Earned growth.",
        "voice": "Witty narrator.", "rules_raw": "Let drama land.",
        "forbidden": ["Forced player actions", "Automatic victory"],
    })
    for expected in ("Anime Adventure", "Earned growth.", "Witty narrator.",
                     "Let drama land.", "- Forced player actions", "- Automatic victory"):
        assert expected in text


def test_builtin_style_reads_its_file(tmp_path):
    directory = tmp_path / ".claude/additional/narrator-styles"
    directory.mkdir(parents=True)
    (directory / "epic-heroic.md").write_text("# Epic\nExisting rules.")
    assert render_narrator_style(tmp_path, "epic-heroic") == "# Epic\nExisting rules."


@pytest.mark.parametrize("style", [None, "", {}])
def test_absent_style_is_empty(tmp_path, style):
    assert render_narrator_style(tmp_path, style) == ""


def test_missing_builtin_is_empty(tmp_path):
    assert render_narrator_style(tmp_path, "unknown") == ""


def test_style_id_cannot_read_outside_style_directory(tmp_path):
    with pytest.raises(ValueError, match="Invalid narrator style"):
        render_narrator_style(tmp_path, "../../private")
