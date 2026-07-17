import json

import backend.game_state as game_state


def _campaign(tmp_path, name, player_name):
    campaign = tmp_path / name
    campaign.mkdir()
    (campaign / "world.json").write_text(
        json.dumps(
            {
                "meta": {"version": 2, "schema": "graph"},
                "nodes": {
                    "player:active": {
                        "type": "player",
                        "name": player_name,
                        "data": {
                            "hp": {"current": 10, "max": 12},
                            "xp": 3,
                            "money": 7,
                        },
                    }
                },
                "edges": [],
            }
        )
    )
    return campaign


def test_character_cache_is_isolated_by_campaign(tmp_path):
    game_state.invalidate_cache()
    first = _campaign(tmp_path, "first", "First")
    second = _campaign(tmp_path, "second", "Second")

    assert game_state.get_character_status(first)["name"] == "First"
    assert game_state.get_character_status(second)["name"] == "Second"
def test_character_status_prefers_embedded_inventory_and_player_location(tmp_path):
    game_state.invalidate_cache()
    campaign = _campaign(tmp_path, "canonical", "Canonical")
    world_file = campaign / "world.json"
    world = json.loads(world_file.read_text())
    player = world["nodes"]["player:active"]
    player["data"]["current_location"] = "location:base"
    player["inventory"] = {
        "stackable": {"Ammo": {"qty": 12, "weight": 0.1}},
        "unique": ["Dog tags"],
    }
    world["nodes"]["location:base"] = {
        "type": "location",
        "name": "Forward Base",
        "data": {},
    }
    world["nodes"]["item:stale"] = {
        "type": "item",
        "name": "Stale item",
        "data": {"quantity": 99},
    }
    world["edges"].append(
        {"from": "player:active", "to": "item:stale", "type": "owns"}
    )
    world_file.write_text(json.dumps(world))

    status = game_state.get_character_status(campaign)

    assert status["location"] == "Forward Base"
    assert status["inventory"] == [
        {"name": "Ammo", "quantity": 12},
        {"name": "Dog tags", "quantity": 1},
    ]


def test_character_status_falls_back_to_overview_location(tmp_path):
    game_state.invalidate_cache()
    campaign = _campaign(tmp_path, "fallback", "Fallback")
    (campaign / "campaign-overview.json").write_text(
        json.dumps({"player_position": {"current_location": "Old Camp"}})
    )

    assert game_state.get_character_status(campaign)["location"] == "Old Camp"
