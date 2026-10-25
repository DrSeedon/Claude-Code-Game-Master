"""Choosing and storing voices: the campaign narrator, a default, and a voice profile on every character."""

import base64
import json
from pathlib import Path

from lib.world_graph import WorldGraph

from . import speech


def find_voice(api, query):
    """A voice by id or by a unique part of its name."""
    found = api.voices()
    for voice in found:
        if voice["voice_id"] == query:
            return voice
    matches = [v for v in found if query.lower() in v["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"no voice matches {query!r}")
    raise ValueError(f"{query!r} matches several voices: " + ", ".join(v["name"].split(" - ")[0] for v in matches))


def _is_russian(voice):
    langs = {voice.get("labels", {}).get("language")} | {x.get("language") for x in voice.get("verified_languages") or []}
    return "ru" in langs


def describe_all(api):
    return [{"name": v["name"], "voice_id": v["voice_id"], "category": v.get("category"), "gender": v.get("labels", {}).get("gender"),
             "accent": v.get("labels", {}).get("accent"), "ru": _is_russian(v)} for v in api.voices()]


def make_profile(voice, model=None, stability=None, similarity_boost=None, effects=None, speed=None):
    profile = {"voice_id": voice["voice_id"], "name": voice["name"].split(" - ")[0]}
    if speed is not None and not (isinstance(speed, (int, float)) and speech.SPEED_RANGE[0] <= speed <= speech.SPEED_RANGE[1]):
        raise ValueError(f"speed must be between {speech.SPEED_RANGE[0]} and {speech.SPEED_RANGE[1]}")
    for key, value in (("model", model), ("stability", stability), ("similarity_boost", similarity_boost), ("speed", speed)):
        if value is not None:
            profile[key] = value
    if effects:
        profile["effects"] = speech.validate_effects(effects)
    return profile


def _write_config(screen_dir, mutate):
    path = Path(screen_dir) / speech.CONFIG_FILE
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    mutate(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")


def set_narrator(screen_dir, profile):
    _write_config(screen_dir, lambda c: c.__setitem__("narrator", profile))


def set_default(screen_dir, profile):
    _write_config(screen_dir, lambda c: c.__setitem__("default", profile))


def set_model(screen_dir, model):
    _write_config(screen_dir, lambda c: c.__setitem__("model", model))


def set_character_voice(campaign_dir, name, profile):
    """Store the profile in the character's own card (player or NPC), found by full or first name."""
    graph = WorldGraph(str(campaign_dir))
    people = graph.list_nodes("player") + graph.list_nodes("npc")
    key = name.lower()
    matches = ([n for n in people if n["name"].lower() == key] or [n for n in people if n["name"].lower().split()[0] == key]
               or [n for n in people if key in [a.lower() for a in (graph.get_node(n["id"])["data"].get("aliases") or [])]])
    if len(matches) != 1:
        known = ", ".join(sorted(n["name"] for n in people)[:12])
        raise ValueError(f"no single character named {name!r} (known: {known})")
    graph.update_node(matches[0]["id"], {"data": {"voice": profile}})
    return matches[0]["id"]


def set_audition(screen_dir, profiles):
    """Temporary named voices for the audition paragraphs (replaced by the next audition)."""
    _write_config(screen_dir, lambda c: c.__setitem__("voices", profiles))


def design_voice(api, screen_dir, description, text=None, seed=None, model_id=None):
    """Ask for voice previews from a description; each preview is saved as an mp3 in <screen>/voices/ to listen to."""
    if text is not None and not 100 <= len(text) <= 1000:
        raise ValueError("the sample text must be 100 to 1000 characters (or leave it out to let the service write one)")
    result = api.design(description, text=text, model_id=model_id, seed=seed)
    folder = Path(screen_dir) / "voices"
    folder.mkdir(parents=True, exist_ok=True)
    previews = []
    for preview in result["previews"]:
        path = folder / f"preview-{preview['generated_voice_id']}.mp3"
        path.write_bytes(base64.b64decode(preview["audio_base_64"]))
        previews.append({"id": preview["generated_voice_id"], "file": str(path.relative_to(screen_dir)), "seconds": preview.get("duration_secs")})
    return previews


def keep_voice(api, name, description, generated_voice_id, model=None):
    """Turn a chosen preview into a permanent voice of the account and return its profile."""
    created = api.create_voice(name, description, generated_voice_id)
    return make_profile({"voice_id": created["voice_id"], "name": created.get("name", name)}, model=model)
