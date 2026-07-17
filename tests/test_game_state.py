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
