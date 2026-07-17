import json

import pytest

from lib.legacy_migration import LegacyCampaignMigrator


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_legacy_migration_is_complete_and_idempotent(tmp_path):
    write_json(tmp_path / "campaign-overview.json", {
        "name": "legacy",
        "modules": ["world-travel"],
    })
    write_json(tmp_path / "character.json", {
        "name": "Hero",
        "race": "Human",
        "class": "Fighter",
        "level": 2,
    })
    write_json(tmp_path / "locations.json", {
        "Camp": {
            "description": "Home",
            "connections": [{"to": "Mine", "path": "road", "distance_meters": 50}],
        },
        "Mine": {"description": "Dark", "connections": []},
    })
    write_json(tmp_path / "npcs.json", {
        "Guide": {
            "description": "Scout",
            "is_party_member": True,
            "tags": {"locations": ["Camp"], "quests": []},
        }
    })
    write_json(tmp_path / "facts.json", {
        "lore": [{"fact": "The mine is old", "timestamp": "now"}],
    })
    write_json(tmp_path / "consequences.json", {
        "active": [{"id": "abc123", "consequence": "Cave-in", "hours_remaining": 3}],
        "resolved": [],
    })
    write_json(tmp_path / "plots.json", {
        "Explore": {
            "type": "main",
            "status": "active",
            "npcs": ["Guide"],
            "locations": ["Mine"],
            "objectives": [{"text": "Enter mine", "completed": True}],
        }
    })

    first = LegacyCampaignMigrator(tmp_path).migrate()
    second = LegacyCampaignMigrator(tmp_path).migrate()
    world = json.loads((tmp_path / "world.json").read_text(encoding="utf-8"))

    assert first["nodes_added"] == 7
    assert second["nodes_added"] == 0
    assert world["nodes"]["player:active"]["data"]["class"] == "Fighter"
    assert world["nodes"]["quest:explore"]["data"]["objectives"] == [
        {"text": "Enter mine", "done": True}
    ]
    assert len([
        edge for edge in world["edges"] if edge["type"] == "connected"
    ]) == 2
    assert any(edge["type"] == "at" for edge in world["edges"])
    assert json.loads(
        (tmp_path / "campaign-overview.json").read_text(encoding="utf-8")
    )["modules"] == {"world-travel": True}


def test_migration_rejects_unsupported_legacy_root_shape(tmp_path):
    write_json(tmp_path / "campaign-overview.json", {})
    write_json(tmp_path / "npcs.json", ["not", "an", "object"])

    with pytest.raises(ValueError, match="npcs.json"):
        LegacyCampaignMigrator(tmp_path).migrate()

    assert (tmp_path / "npcs.json").exists()
