"""Validation of what the DM pushes to the screen: refuse anything that could run code in the page."""

import re

from . import audio, speech

MAX_OPTIONS = 6
MAX_LINE = 2000
ZONES = {"tl", "tr", "bottom"}
_DANGEROUS = re.compile(r"<\s*(script|style|iframe|object|embed|link|meta|form|base)\b|\son\w+\s*=|javascript:|data:text/html",
                        re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def _check_html(text, where):
    if _DANGEROUS.search(text):
        raise ValueError(f"{where}: scripts, styles, frames and event handlers are not allowed")
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
            bars.append({"label": _check_plain(str(bar["label"]), "bar label"), "value": float(bar["value"]),
                         "max": float(bar.get("max", 20))})
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
    turn = {"blocks": [_check_html(str(b), "block") for b in blocks],
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
        out.append(card)
    return out
