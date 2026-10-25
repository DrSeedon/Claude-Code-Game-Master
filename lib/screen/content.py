"""Validation of what the DM pushes to the screen: refuse anything that could run code in the page."""

import re

MAX_OPTIONS = 6
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


def validate_turn(data):
    blocks = data.get("blocks")
    if not blocks or not isinstance(blocks, list):
        raise ValueError("turn needs at least one block")
    options = data.get("options", [])
    if len(options) > MAX_OPTIONS:
        raise ValueError(f"at most {MAX_OPTIONS} options")
    return {"blocks": [_check_html(str(b), "block") for b in blocks],
            "question": _check_plain(str(data.get("question", "")), "question"),
            "options": [_check_plain(str(o), "option") for o in options],
            "panels": [_validate_panel(p) for p in data.get("panels", [])]}


def validate_captions(cards):
    out = []
    for card in cards:
        if card.get("zone") not in ZONES or not card.get("title"):
            raise ValueError("caption needs a zone (tl, tr, bottom) and a title")
        _check_plain(str(card["title"]) + str(card.get("text", "")), "caption")
        out.append(card)
    return out
