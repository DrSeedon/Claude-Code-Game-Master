import json
import importlib.util
from pathlib import Path


SAVE_CHARACTER_PATH = (
    Path(__file__).parents[1]
    / "features"
    / "character-creation"
    / "save_character.py"
)
SPEC = importlib.util.spec_from_file_location("save_character", SAVE_CHARACTER_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
save_character = MODULE.save_character


def test_save_character_writes_player_node(tmp_path, monkeypatch):
    world_state = tmp_path / "world-state"
    campaign = world_state / "campaigns" / "test"
    campaign.mkdir(parents=True)
    (world_state / "active-campaign.txt").write_text("test", encoding="utf-8")
    (campaign / "campaign-overview.json").write_text("{}", encoding="utf-8")
    (campaign / "world.json").write_text(
        json.dumps({
            "meta": {"version": 2, "schema": "graph", "revision": 0},
            "nodes": {},
            "edges": [],
        }),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = save_character({
        "name": "Ada",
        "race": "Human",
        "class": "Wizard",
        "level": 1,
        "stats": {
            "strength": 8,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 16,
            "wisdom": 10,
            "charisma": 10,
        },
    })

    assert result["success"] is True
    world = json.loads((campaign / "world.json").read_text(encoding="utf-8"))
    player = world["nodes"]["player:active"]
    assert player["name"] == "Ada"
    assert player["data"]["stats"]["int"] == 16
    assert "race" not in player
    assert not (campaign / "character.json").exists()
