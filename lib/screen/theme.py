"""Derive an act's interface theme (colors and shape) from its key-art image."""

import colorsys
from pathlib import Path

from PIL import Image

STYLES = {
    "classic": {"radius": "14px", "font": "'Cormorant Garamond','PT Serif',Georgia,'Noto Serif',serif",
                "heading_spacing": ".14em"},
    "severe": {"radius": "3px", "font": "'PT Serif',Georgia,'Noto Serif',serif", "heading_spacing": ".22em"},
    "soft": {"radius": "22px", "font": "'Segoe UI','Noto Sans',system-ui,sans-serif", "heading_spacing": ".06em"},
}

PANEL_LIGHTNESS = 0.10
MIN_TEXT_CONTRAST = 7.0
MIN_ACCENT_CONTRAST = 4.5


def extract_palette(path, n=6):
    """Dominant colors of an image, most frequent first."""
    image = Image.open(path).convert("RGB")
    image.thumbnail((96, 96))
    quantized = image.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    flat = quantized.getpalette()
    return [tuple(flat[i * 3:i * 3 + 3]) for _, i in sorted(quantized.getcolors(), reverse=True)]


def _to_hex(rgb):
    return "#%02x%02x%02x" % tuple(round(c) for c in rgb)


def _from_hex(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    """WCAG contrast ratio between two hex colors."""
    la, lb = _luminance(_from_hex(a)), _luminance(_from_hex(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _hls(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def _rgb(h, l, s):
    return tuple(c * 255 for c in colorsys.hls_to_rgb(h % 1.0, min(max(l, 0), 1), min(max(s, 0), 1)))


def _lighten_until(rgb, against, minimum):
    h, l, s = _hls(rgb)
    while l < 0.97 and contrast_ratio(_to_hex(_rgb(h, l, s)), against) < minimum:
        l += 0.02
    return _rgb(h, l, s)


def _vividness(rgb):
    _, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return s * v if v >= 0.45 else 0


def build_theme(palette, style="classic"):
    """Return CSS-ready colors and shape values; every text color keeps a readable contrast on the panel."""
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; choose from {sorted(STYLES)}")
    base_hue, _, base_sat = _hls(palette[0])
    panel_rgb = _rgb(base_hue, PANEL_LIGHTNESS, min(base_sat, 0.3))
    panel = _to_hex(panel_rgb)

    ranked = sorted(palette, key=_vividness, reverse=True)
    if _vividness(ranked[0]) > 0:
        accent_src = ranked[0]
    else:
        accent_src = _rgb(base_hue, 0.7, 0.5)
    accent_hue = _hls(accent_src)[0]
    second = next((c for c in ranked[1:] if _vividness(c) > 0 and abs(_hls(c)[0] - accent_hue) > 0.06), None)
    accent2_src = second if second else _rgb(accent_hue + 0.08, 0.7, 0.5)

    accent = _to_hex(_lighten_until(accent_src, panel, MIN_ACCENT_CONTRAST))
    accent2 = _to_hex(_lighten_until(accent2_src, panel, MIN_ACCENT_CONTRAST))
    text = _to_hex(_lighten_until(_rgb(accent_hue, 0.9, 0.25), panel, MIN_TEXT_CONTRAST))
    muted_src = tuple(t * 0.7 + p * 0.3 for t, p in zip(_from_hex(text), panel_rgb))
    muted = _to_hex(_lighten_until(muted_src, panel, MIN_ACCENT_CONTRAST))
    bg = _to_hex(_rgb(base_hue, 0.05, min(base_sat, 0.3)))

    look = STYLES[style]
    return {"bg": bg, "panel": panel, "text": text, "muted": muted, "accent": accent, "accent2": accent2,
            "line": ",".join(str(round(c)) for c in _from_hex(accent)),
            "panel_rgb": ",".join(str(round(c)) for c in panel_rgb),
            "radius": look["radius"], "font": look["font"], "heading_spacing": look["heading_spacing"],
            "style": style}


def theme_css(theme):
    """A :root block with the theme as CSS variables (line/panel colors are 'r,g,b' for rgba use)."""
    return (":root{--bg:%(bg)s;--panel:%(panel)s;--panel-rgb:%(panel_rgb)s;--text:%(text)s;--muted:%(muted)s;"
            "--accent:%(accent)s;--accent2:%(accent2)s;--line:%(line)s;--radius:%(radius)s;"
            "--font:%(font)s;--spacing:%(heading_spacing)s}" % theme)
