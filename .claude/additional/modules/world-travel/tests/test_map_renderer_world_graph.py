"""Map rendering reads the WorldGraph projection, not legacy flat files."""

import sys
from pathlib import Path


PROJECT_ROOT = next(path for path in Path(__file__).parents if (path / "pyproject.toml").exists())
MODULE_LIB = PROJECT_ROOT / ".claude/additional/modules/world-travel/lib"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(MODULE_LIB))

from map_renderer import MapRenderer
from world_travel_store import WorldTravelStore


def _campaign(tmp_path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    store = WorldTravelStore(campaign_dir)
    store.save_locations({
        "Harbor": {
            "coordinates": {"x": 0, "y": 0},
            "connections": [{
                "to": "Hill",
                "distance_meters": 1000,
                "bearing": 45,
                "terrain": "open",
            }],
        },
        "Hill": {
            "coordinates": {"x": 1000, "y": 1000},
            "connections": [],
        },
    })
    store.save_overview({
        "player_position": {"current_location": "Harbor"},
    })
    return campaign_dir


def test_render_map_uses_world_graph_without_locations_file(tmp_path):
    campaign_dir = _campaign(tmp_path)

    output = MapRenderer(str(campaign_dir)).render_map(
        width=50,
        height=20,
        show_compass=False,
        use_colors=False,
    )

    assert "Harbor" in output
    assert "Hill" in output
    assert "@" in output
    assert not (campaign_dir / "locations.json").exists()


def test_render_minimap_uses_overview_and_world_graph(tmp_path):
    campaign_dir = _campaign(tmp_path)

    output = MapRenderer(str(campaign_dir)).render_minimap(radius=3)

    assert "You (Harbor)" in output
    assert "@" in output
    assert "●" in output
