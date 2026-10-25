import pytest
from PIL import Image

from lib.screen import theme


def _stripes(tmp_path, colors, name="art.png"):
    img = Image.new("RGB", (120, 60))
    width = 120 // len(colors)
    for i, color in enumerate(colors):
        for x in range(i * width, (i + 1) * width):
            for y in range(60):
                img.putpixel((x, y), color)
    path = tmp_path / name
    img.save(path)
    return path


def test_extract_palette_orders_by_dominance(tmp_path):
    img = Image.new("RGB", (100, 100), (200, 30, 30))
    for x in range(70, 100):
        for y in range(100):
            img.putpixel((x, y), (20, 40, 200))
    path = tmp_path / "two.png"
    img.save(path)

    palette = theme.extract_palette(path, n=2)

    assert palette[0][0] > palette[0][2]  # red dominates
    assert palette[1][2] > palette[1][0]  # blue second


PALETTES = {
    "blue dusk": [(18, 24, 48), (230, 170, 90), (60, 70, 120), (250, 220, 160)],
    "desert": [(220, 190, 140), (240, 220, 180), (180, 120, 70), (250, 245, 230)],
    "grayscale": [(40, 40, 40), (120, 120, 120), (200, 200, 200), (250, 250, 250)],
    "neon": [(5, 5, 20), (255, 0, 200), (0, 255, 220), (20, 20, 60)],
    "white snow": [(255, 255, 255), (240, 245, 255), (220, 230, 250), (250, 250, 250)],
}


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_theme_is_readable_for_any_palette(name):
    t = theme.build_theme(PALETTES[name])

    assert theme.contrast_ratio(t["text"], t["panel"]) >= 7
    assert theme.contrast_ratio(t["muted"], t["panel"]) >= 4.5
    assert theme.contrast_ratio(t["accent"], t["panel"]) >= 4.5
    assert theme.contrast_ratio(t["accent2"], t["panel"]) >= 4.5


def test_theme_follows_the_palette():
    dusk = theme.build_theme(PALETTES["blue dusk"])
    desert = theme.build_theme(PALETTES["desert"])

    assert dusk["accent"] != desert["accent"]
    assert dusk["bg"] != desert["bg"]


def test_theme_is_deterministic():
    assert theme.build_theme(PALETTES["neon"]) == theme.build_theme(PALETTES["neon"])


def test_unknown_style_is_rejected():
    with pytest.raises(ValueError):
        theme.build_theme(PALETTES["neon"], style="glitter")


def test_styles_change_shape_not_colors():
    classic = theme.build_theme(PALETTES["desert"], style="classic")
    severe = theme.build_theme(PALETTES["desert"], style="severe")

    assert classic["accent"] == severe["accent"]
    assert classic["radius"] != severe["radius"]


def test_css_exposes_variables():
    css = theme.theme_css(theme.build_theme(PALETTES["blue dusk"]))

    for var in ("--bg:", "--panel:", "--text:", "--muted:", "--accent:", "--accent2:", "--line:", "--radius:", "--font:"):
        assert var in css


def test_palette_from_real_file_round_trip(tmp_path):
    path = _stripes(tmp_path, [(10, 20, 60), (240, 180, 80), (40, 40, 40)])

    t = theme.build_theme(theme.extract_palette(path))

    assert theme.contrast_ratio(t["text"], t["panel"]) >= 7
