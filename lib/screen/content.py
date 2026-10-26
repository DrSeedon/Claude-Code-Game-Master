"""Validation of what the DM pushes to the screen: refuse anything that could run code in the page."""

import math
import re
from html.parser import HTMLParser

from . import audio, speech

MAX_OPTIONS = 6
MAX_LINE = 2000
ZONES = {"tl", "tr", "bottom"}
STAGE = (1672, 941)        # caption dots are in the page's art coordinates (16:9, 1672 wide)
ALLOWED_TAGS = {"h1", "h2", "h3", "p", "b", "i", "em", "strong", "ul", "ol", "li", "div", "br", "span", "blockquote"}
_CLASS = re.compile(r"[a-z0-9 _-]{1,60}")
_NAME = re.compile(r"[a-z][a-z0-9]*")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_TAG = re.compile(r"<[^>]+>")


class _Allowlist(HTMLParser):
    """Fails on the first tag, attribute or construct outside the allowlist; counts the tags it understood."""

    def __init__(self, where):
        super().__init__(convert_charrefs=True)
        self.where, self.tags = where, 0

    def _tag(self, tag, attrs):
        allowed = ", ".join(sorted(ALLOWED_TAGS))
        if not _NAME.fullmatch(tag) or tag not in ALLOWED_TAGS:
            raise ValueError(f"{self.where}: <{tag}> is not allowed; use only {allowed}")
        for name, value in attrs:
            if name != "class" or value is None or not _CLASS.fullmatch(value):
                raise ValueError(f"{self.where}: attribute {name}={value!r} on <{tag}> is not allowed; "
                                 "only class=\"...\" with lowercase letters, digits, spaces, _ and -")
        self.tags += 1

    def handle_starttag(self, tag, attrs):
        self._tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._tag(tag, attrs)

    def handle_endtag(self, tag):
        self._tag(tag, [])

    def handle_comment(self, data):
        raise ValueError(f"{self.where}: HTML comments are not allowed")

    def handle_decl(self, decl):
        raise ValueError(f"{self.where}: <!{decl[:30]}> is not allowed")

    def unknown_decl(self, data):
        raise ValueError(f"{self.where}: <![{data[:30]}> is not allowed")

    def handle_pi(self, data):
        raise ValueError(f"{self.where}: <?{data[:30]}> is not allowed")


def _check_html(text, where):
    """Allowlist: the tags in ALLOWED_TAGS, no attribute but a plain class. The page joins the blocks, so every '<'
    must open a tag the parser fully understood: an unclosed tag or a raw '<' could swallow the next block."""
    if _CONTROL.search(text):
        raise ValueError(f"{where}: control characters are not allowed")
    parser = _Allowlist(where)
    parser.feed(text)
    parser.close()
    if text.count("<") != parser.tags:
        raise ValueError(f"{where}: a '<' that does not open a complete allowed tag (an unclosed tag, or a raw '<' in text: write &lt;)")
    return text


def _check_plain(text, where):
    if _TAG.search(text):
        raise ValueError(f"{where}: plain text only")
    return text


def _validate_panel(panel):
    if not isinstance(panel, dict) or not panel.get("title"):
        raise ValueError("panel needs a title")
    out = {"title": _check_plain(str(panel["title"]), "panel title")}
    if "chips" in panel:
        out["chips"] = [_check_plain(str(c), "chip") for c in panel["chips"]]
    if "bars" in panel:
        bars = []
        for bar in panel["bars"]:
            if not {"label", "value"} <= set(bar):
                raise ValueError("bar needs label and value")
            value, high = float(bar["value"]), float(bar.get("max", 20))
            if not (math.isfinite(value) and math.isfinite(high)) or high <= 0:   # NaN would break the page's JSON
                raise ValueError(f"bar {bar['label']!r}: value and max must be finite numbers, max above 0")
            bars.append({"label": _check_plain(str(bar["label"]), "bar label"), "value": value, "max": high})
        out["bars"] = bars
    if "steps" in panel:
        out["steps"] = [{"label": _check_plain(str(s["label"]), "step"), "current": bool(s.get("current"))}
                        for s in panel["steps"]]
    return out


def validate_panels(panels):
    return [_validate_panel(p) for p in panels]


def _validate_line(line, blocks):
    if not isinstance(line, dict) or not str(line.get("who", "")).strip() or not str(line.get("text", "")).strip():
        raise ValueError("speech line needs 'who' (narrator or a name) and 'text'")
    text = _check_plain(" ".join(str(line["text"]).split()), "speech text")
    if len(text) > MAX_LINE:
        raise ValueError(f"speech line is longer than {MAX_LINE} characters: split it")
    out = {"who": _check_plain(str(line["who"]).strip(), "speech who"), "text": text}
    indices = line.get("blocks", [])
    if not isinstance(indices, list) or not all(isinstance(i, int) and 0 <= i < blocks for i in indices):
        raise ValueError("speech blocks must be indices of shown blocks")
    if indices:
        out["blocks"] = indices
    if line.get("effects"):
        out["effects"] = speech.validate_effects(line["effects"])
    if line.get("cast") is not None:
        if line["cast"] not in speech.CASTS:
            raise ValueError(f"speech cast must be one of {speech.CASTS}")
        out["cast"] = line["cast"]
    return out


_WORD = re.compile(r"\w+")


def _words(text):
    return [w.lower().replace("ё", "е") for w in _WORD.findall(text)]


def check_verbatim(lines, shown):
    """The voice script reads exactly what is shown: every readable block, word for word; only performance tags are added."""
    expected = {}
    for seg in speech.script_from_blocks(shown, max_chars=10 ** 6):
        if len(seg["blocks"]) == 1 or seg["speaker"] != "narrator":
            expected[seg["blocks"][0]] = seg["text"]
        else:
            for index in seg["blocks"]:
                expected[index] = speech._plain(shown[index])
    covered = set()
    for number, line in enumerate(lines):
        if not line.get("blocks"):
            raise ValueError(f"speech line {number}: give the 'blocks' it reads")
        want = _words(" ".join(expected.get(i, "") for i in line["blocks"]))
        said = _words(speech.spoken_text(line["text"]))
        if said != want:
            raise ValueError(f"speech line {number} must read blocks {line['blocks']} word for word (only [tags] may be added): "
                             f"shown «{' '.join(want)[:120]}», spoken «{' '.join(said)[:120]}»")
        covered.update(line["blocks"])
    missing = sorted(set(expected) - covered)
    if missing:
        raise ValueError(f"speech skips readable blocks {missing}: voice every shown paragraph")


def validate_audio(data, blocks, shown=None):
    """The turn's sound: a voice script, scene acoustics, sound effects, ambience and music (all optional)."""
    if not isinstance(data, dict):
        raise ValueError("audio must be an object")
    unknown = set(data) - {"speech", "scene", "sfx", "ambience", "music"}
    if unknown:
        raise ValueError(f"unknown audio fields: {sorted(unknown)}")
    out = {}
    if data.get("speech"):
        out["speech"] = [_validate_line(line, blocks) for line in data["speech"]]
        if shown is not None:
            check_verbatim(out["speech"], shown)
    if data.get("scene"):
        out["scene"] = speech.validate_effects(data["scene"])
    if data.get("sfx"):
        if len(data["sfx"]) > audio.MAX_SFX:
            raise ValueError(f"at most {audio.MAX_SFX} sound effects a turn")
        out["sfx"] = [audio.validate_cue(c, "sfx", f"sfx {i}", blocks) for i, c in enumerate(data["sfx"])]
    for kind in ("ambience", "music"):
        if kind in data:
            out[kind] = audio.validate_cue(data[kind], kind, kind) if data[kind] else None
    return out


def validate_turn(data):
    blocks = data.get("blocks")
    if not blocks or not isinstance(blocks, list):
        raise ValueError("turn needs at least one block")
    options = data.get("options", [])
    if len(options) > MAX_OPTIONS:
        raise ValueError(f"at most {MAX_OPTIONS} options")
    turn = {"blocks": [_check_html(str(b), f"block {i}") for i, b in enumerate(blocks)],
            "question": _check_plain(str(data.get("question", "")), "question"),
            "options": [_check_plain(str(o), "option") for o in options],
            "panels": validate_panels(data.get("panels", []))}
    if data.get("audio"):
        turn["audio"] = validate_audio(data["audio"], len(blocks), turn["blocks"])
    return turn


def validate_captions(cards):
    out = []
    for card in cards:
        if card.get("zone") not in ZONES or not card.get("title"):
            raise ValueError("caption needs a zone (tl, tr, bottom) and a title")
        _check_plain(str(card["title"]) + str(card.get("text", "")), "caption")
        if card.get("dot") is not None:
            dot = card["dot"]
            if not (isinstance(dot, (list, tuple)) and len(dot) == 2
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= high
                            for v, high in zip(dot, STAGE))):
                raise ValueError(f"caption dot must be [x, y] with 0 <= x <= {STAGE[0]} and 0 <= y <= {STAGE[1]}")
            card = {**card, "dot": list(dot)}
        out.append(card)
    return out
