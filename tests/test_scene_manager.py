import json

import pytest

from lib.scene_manager import SceneManager, SceneTransitionError


def make_world_state(tmp_path):
    world_state = tmp_path / "world-state"
    campaign = world_state / "campaigns" / "scene-test"
    campaign.mkdir(parents=True)
    (world_state / "active-campaign.txt").write_text("scene-test")

    overview = {
        "campaign_name": "Scene Test",
        "current_date": "Day 1",
        "precise_time": "08:00",
        "time_of_day": "08:00",
        "player_position": {"current_location": "Entrance"},
    }
    (campaign / "campaign-overview.json").write_text(json.dumps(overview))

    world = {
        "meta": {"version": 2, "schema": "graph"},
        "nodes": {
            "player:active": {
                "type": "player",
                "name": "Hero",
                "data": {"current_location": "Entrance"},
            },
            "location:entrance": {
                "type": "location",
                "name": "Entrance",
                "data": {"description": "Starting area"},
            },
            "npc:marine": {
                "type": "npc",
                "name": "Marine",
                "data": {"party_member": True},
            },
            "npc:engineer": {
                "type": "npc",
                "name": "Engineer",
                "data": {},
            },
            "quest:repair": {
                "type": "quest",
                "name": "Repair",
                "data": {"status": "active", "objectives": []},
            },
            "consequence:contact": {
                "type": "consequence",
                "name": "Contact",
                "data": {
                    "description": "Something approaches",
                    "trigger": "After entry",
                    "status": "pending",
                    "hours_remaining": 0.25,
                },
            },
        },
        "edges": [],
    }
    (campaign / "world.json").write_text(json.dumps(world))
    return str(world_state), campaign


def test_transition_applies_complete_scene_beat(tmp_path):
    world_state, campaign = make_world_state(tmp_path)
    manager = SceneManager(world_state)

    result = manager.transition(
        "Control Room",
        description="A dark industrial control room.",
        path="sealed corridor",
        elapsed=0.25,
        with_npcs=["Engineer"],
        resolve_consequences=[("consequence:contact", "Sensor contact detected")],
        add_objectives=[("Repair", "Inspect the hidden level")],
    )

    overview = json.loads((campaign / "campaign-overview.json").read_text())
    world = json.loads((campaign / "world.json").read_text())

    assert overview["player_position"]["current_location"] == "Control Room"
    assert overview["precise_time"] == "08:15"
    assert world["nodes"]["player:active"]["data"]["current_location"] == "Control Room"
    assert world["nodes"]["location:control-room"]["data"]["description"] == "A dark industrial control room."

    connected = {
        (edge["from"], edge["to"], edge.get("data", {}).get("path_type"))
        for edge in world["edges"]
        if edge["type"] == "connected"
    }
    assert ("location:entrance", "location:control-room", "sealed corridor") in connected
    assert ("location:control-room", "location:entrance", "sealed corridor") in connected

    locations = {
        edge["from"]: edge["to"]
        for edge in world["edges"]
        if edge["type"] == "at"
    }
    assert locations["npc:marine"] == "location:control-room"
    assert locations["npc:engineer"] == "location:control-room"

    consequence = world["nodes"]["consequence:contact"]["data"]
    assert consequence["status"] == "resolved"
    assert consequence["resolution"] == "Sensor contact detected"
    assert world["nodes"]["quest:repair"]["data"]["objectives"] == [
        {"text": "Inspect the hidden level", "done": False}
    ]

    assert result["created_location"] is True
    assert result["moved_npcs"] == ["Engineer", "Marine"]
    assert result["triggered_consequences"] == ["consequence:contact"]


def test_transition_validates_references_before_writing(tmp_path):
    world_state, campaign = make_world_state(tmp_path)
    before_world = (campaign / "world.json").read_text()
    before_overview = (campaign / "campaign-overview.json").read_text()

    manager = SceneManager(world_state)
    with pytest.raises(SceneTransitionError, match="Unknown quest"):
        manager.transition(
            "Control Room",
            add_objectives=[("Missing Quest", "Impossible objective")],
        )

    assert (campaign / "world.json").read_text() == before_world
    assert (campaign / "campaign-overview.json").read_text() == before_overview


def test_transition_delegates_travel_time_to_world_travel(tmp_path):
    world_state, campaign = make_world_state(tmp_path)
    overview = json.loads((campaign / "campaign-overview.json").read_text())
    overview["modules"] = {"world-travel": True}
    (campaign / "campaign-overview.json").write_text(json.dumps(overview))

    world = json.loads((campaign / "world.json").read_text())
    world["nodes"]["player:active"]["data"]["speed_kmh"] = 4
    world["nodes"]["location:outpost"] = {
        "type": "location",
        "name": "Outpost",
        "data": {"coordinates": {"x": 1000, "y": 0}},
    }
    for source, target, bearing in (
        ("location:entrance", "location:outpost", 90),
        ("location:outpost", "location:entrance", 270),
    ):
        world["edges"].append({
            "from": source,
            "to": target,
            "type": "connected",
            "data": {
                "path": "road",
                "path_type": "road",
                "distance_meters": 1000,
                "bearing": bearing,
                "terrain": "open",
            },
        })
    (campaign / "world.json").write_text(json.dumps(world))

    result = SceneManager(world_state).transition("Outpost", elapsed=0.1)

    assert result["travel_elapsed_hours"] == pytest.approx(0.25)
    assert result["scene_elapsed_hours"] == pytest.approx(0.1)
    assert result["elapsed_hours"] == pytest.approx(0.35)
    assert result["current_time"] == "08:21"
    assert result["triggered_consequences"] == ["consequence:contact"]
