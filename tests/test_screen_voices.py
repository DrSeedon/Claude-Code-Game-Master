import json

import pytest

from lib.screen import speech, voices


class Api:
    def voices(self):
        return [
            {"voice_id": "N" * 20, "name": "Nikolay - Professional YouTube", "category": "professional", "labels": {"language": "ru", "gender": "male"}},
            {"voice_id": "V" * 20, "name": "Victoria", "category": "professional", "labels": {"language": "ru", "gender": "female"}},
            {"voice_id": "G" * 20, "name": "George - Warm", "category": "premade", "labels": {"gender": "male", "accent": "british"}},
            {"voice_id": "B" * 20, "name": "Brian - Deep", "category": "premade", "labels": {"gender": "male"}},
            {"voice_id": "D" * 20, "name": "Daniel - Steady", "category": "premade", "labels": {"gender": "male"}},
        ]


def test_find_voice_by_id_or_unique_part_of_name():
    assert voices.find_voice(Api(), "Victoria")["voice_id"] == "V" * 20
    assert voices.find_voice(Api(), "nikolay")["voice_id"] == "N" * 20
    assert voices.find_voice(Api(), "G" * 20)["name"].startswith("George")


def test_find_voice_ambiguous_or_missing_fails():
    with pytest.raises(ValueError):
        voices.find_voice(Api(), "e")      # several voices contain it
    with pytest.raises(ValueError):
        voices.find_voice(Api(), "Zeus")


def test_russian_voices_are_marked():
    listing = voices.describe_all(Api())

    assert [v["name"].split()[0] for v in listing if v["ru"]] == ["Nikolay", "Victoria"]


def test_profile_keeps_only_what_was_given():
    profile = voices.make_profile({"voice_id": "V" * 20, "name": "Victoria"}, model="eleven_v4", effects={"pan": 0.4}, stability=None)

    assert profile == {"voice_id": "V" * 20, "name": "Victoria", "model": "eleven_v4", "effects": {"pan": 0.4}}


def test_profile_rejects_bad_effects():
    with pytest.raises(ValueError):
        voices.make_profile({"voice_id": "V" * 20, "name": "V"}, effects={"pan": 5})


@pytest.fixture
def campaign(tmp_path):
    nodes = {"player:active": {"type": "player", "name": "Максим Астраханцев", "data": {}},
             "npc:agrafena-tikhonovna": {"type": "npc", "name": "Аграфена Тихоновна", "data": {"attitude": "neutral"}},
             "location:x": {"type": "location", "name": "Аграфена", "data": {}}}
    (tmp_path / "world.json").write_text(json.dumps({"nodes": nodes, "edges": []}))
    (tmp_path / "screen").mkdir()
    return tmp_path


def test_character_voice_is_written_to_the_character_card(campaign):
    profile = voices.make_profile({"voice_id": "V" * 20, "name": "Victoria"})

    voices.set_character_voice(campaign, "Аграфена", profile)

    node = json.loads((campaign / "world.json").read_text())["nodes"]["npc:agrafena-tikhonovna"]
    assert node["data"]["voice"] == profile and node["data"]["attitude"] == "neutral"
    assert speech.characters_from_world(campaign) == {"аграфена тихоновна": profile}


def test_first_name_finds_the_hero(campaign):
    voices.set_character_voice(campaign, "Максим", voices.make_profile({"voice_id": "N" * 20, "name": "Nikolay"}))

    assert "максим астраханцев" in speech.characters_from_world(campaign)


def test_unknown_character_is_an_error_not_a_new_node(campaign):
    with pytest.raises(ValueError):
        voices.set_character_voice(campaign, "Незнакомец", voices.make_profile({"voice_id": "N" * 20, "name": "N"}))

    assert "незнакомец" not in speech.characters_from_world(campaign)


def test_narrator_and_default_go_to_speech_json(campaign):
    sdir = campaign / "screen"

    voices.set_narrator(sdir, voices.make_profile({"voice_id": "N" * 20, "name": "Nikolay"}, effects={"environment_id": "hall"}))
    voices.set_default(sdir, voices.make_profile({"voice_id": "B" * 20, "name": "Brian"}))
    voices.set_model(sdir, "eleven_v4")

    config = speech.load_config(sdir)
    assert config["narrator"]["voice_id"] == "N" * 20 and config["default"]["voice_id"] == "B" * 20 and config["model"] == "eleven_v4"
    assert config["narrator"]["effects"] == {"environment_id": "hall"}


def test_aliases_find_the_character_and_are_spoken_for(campaign):
    path = campaign / "world.json"
    world = json.loads(path.read_text())
    world["nodes"]["player:active"]["data"]["aliases"] = ["Макс"]
    path.write_text(json.dumps(world))

    voices.set_character_voice(campaign, "Макс", voices.make_profile({"voice_id": "N" * 20, "name": "Nikolay"}))

    found = speech.characters_from_world(campaign)
    assert found["макс"] == found["максим астраханцев"]
