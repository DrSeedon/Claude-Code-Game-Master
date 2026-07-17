from pathlib import Path
import importlib.util
import json
import sys

MODULE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MODULE_ROOT / "lib"))

from world_travel_store import WorldTravelStore


def test_location_projection_round_trip_uses_world_graph(tmp_path):
    store = WorldTravelStore(tmp_path)
    locations = {
        "Alpha": {
            "coordinates": {"x": 0, "y": 0},
            "connections": [{
                "to": "Beta",
                "distance_meters": 1000,
                "bearing": 90,
                "terrain": "road",
            }],
        },
        "Beta": {
            "coordinates": {"x": 1000, "y": 0},
            "connections": [],
        },
    }

    assert store.save_locations(locations)

    world = store.graph.repository.load()
    assert not (tmp_path / "locations.json").exists()
    assert world["nodes"]["location:alpha"]["data"]["coordinates"] == {"x": 0, "y": 0}
    assert len([edge for edge in world["edges"] if edge["type"] == "connected"]) == 2
    assert store.load_locations() == locations


def test_legacy_import_writes_world_graph_and_preserves_source(tmp_path):
    legacy = {
        "Camp": {
            "coordinates": {"x": 0, "y": 0},
            "connections": [{
                "to": "Mine",
                "distance_meters": 500,
                "bearing": 90,
                "terrain": "road",
            }],
        },
        "Mine": {
            "coordinates": {"x": 500, "y": 0},
            "connections": [],
        },
    }
    legacy_path = tmp_path / "locations.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    (tmp_path / "character.json").write_text(
        json.dumps({"name": "Ranger", "speed_kmh": 12}), encoding="utf-8"
    )
    WorldTravelStore(tmp_path).graph.add_node(
        "player:active", "player", "Ranger", {"speed_kmh": 4}
    )

    script = MODULE_ROOT / "tools" / "migrate-connections.py"
    spec = importlib.util.spec_from_file_location("world_travel_migration", script)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.import_legacy(tmp_path, apply=True) == 0
    assert legacy_path.exists()
    assert WorldTravelStore(tmp_path).load_locations() == legacy
    assert WorldTravelStore(tmp_path).get_player_data()["speed_kmh"] == 12
