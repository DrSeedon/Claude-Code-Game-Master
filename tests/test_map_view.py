import json

from backend.map_view import get_map_snapshot


def _write_campaign(tmp_path, *, modules, nodes=None, edges=None, position=None):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    (campaign / "campaign-overview.json").write_text(
        json.dumps(
            {
                "campaign_name": "Map Test",
                "modules": modules,
                "player_position": position or {},
            }
        ),
        encoding="utf-8",
    )
    (campaign / "world.json").write_text(
        json.dumps(
            {
                "meta": {"version": 2, "schema": "graph"},
                "nodes": nodes or {},
                "edges": edges or [],
            }
        ),
        encoding="utf-8",
    )
    return campaign


def _location(name, **data):
    return {
        "type": "location",
        "name": name,
        "data": data,
    }


def test_disabled_module_returns_clean_empty_snapshot(tmp_path):
    campaign = _write_campaign(tmp_path, modules={"world-travel": False})

    snapshot = get_map_snapshot(campaign)

    assert snapshot["enabled"] is False
    assert snapshot["nodes"] == []
    assert snapshot["connections"] == []
    assert snapshot["breadcrumb"] == ["World"]


def test_projects_world_graph_map_and_current_context(tmp_path):
    campaign = _write_campaign(
        tmp_path,
        modules=["world-travel"],
        position={
            "current_location": "Airlock",
            "map_context": "local",
            "vehicle_id": "ship-01",
        },
        nodes={
            "player:active": {
                "type": "player",
                "name": "Pilot",
                "data": {"current_location": "Airlock"},
            },
            "location:colony": _location(
                "Colony",
                type="world",
                coordinates={"x": 0, "y": 0},
            ),
            "location:ship": _location(
                "Ship",
                type="compound",
                coordinates={"x": 1000, "y": 500},
                children=["Bridge", "Airlock"],
                entry_points=["Airlock"],
                _vehicle={
                    "vehicle_id": "ship-01",
                    "is_vehicle_anchor": True,
                    "vehicle_type": "corvette",
                },
            ),
            "location:bridge": _location(
                "Bridge",
                type="interior",
                parent="Ship",
                _vehicle={"vehicle_id": "ship-01", "is_vehicle_anchor": False},
            ),
            "location:airlock": _location(
                "Airlock",
                type="interior",
                parent="Ship",
                entry_config={
                    "name": "Dock",
                    "on_enter": {"description": "Secret ambush"},
                },
                _vehicle={"vehicle_id": "ship-01", "is_vehicle_anchor": False},
            ),
        },
        edges=[
            {
                "from": "location:colony",
                "to": "location:ship",
                "type": "connected",
                "data": {
                    "distance_meters": 1200,
                    "bearing": 63,
                    "terrain": "open",
                    "path": "service road",
                },
            },
            {
                "from": "location:ship",
                "to": "location:colony",
                "type": "connected",
                "data": {
                    "distance_meters": 1200,
                    "bearing": 243,
                    "terrain": "open",
                    "path": "service road",
                },
            },
            {
                "from": "location:airlock",
                "to": "location:bridge",
                "type": "connected",
                "data": {"distance_meters": 15, "path": "main corridor"},
            },
            {
                "from": "location:bridge",
                "to": "location:airlock",
                "type": "connected",
                "data": {"distance_meters": 15, "path": "main corridor"},
            },
        ],
    )

    snapshot = get_map_snapshot(campaign)

    assert snapshot["enabled"] is True
    assert snapshot["current"] == {
        "location": "Airlock",
        "context": "interior",
        "compound": "Ship",
        "global_location": "Ship",
        "vehicle_id": "ship-01",
        "coordinates": {"x": 1000, "y": 500},
    }
    assert snapshot["breadcrumb"] == ["World", "Ship", "Airlock"]
    assert [(edge["source"], edge["target"]) for edge in snapshot["connections"]] == [
        ("Airlock", "Bridge"),
        ("Colony", "Ship"),
    ]
    road = snapshot["connections"][1]
    assert road == {
        "source": "Colony",
        "target": "Ship",
        "distance_meters": 1200,
        "terrain": "open",
        "path": "service road",
        "bearing": 63,
    }

    nodes = {node["name"]: node for node in snapshot["nodes"]}
    assert nodes["Airlock"]["entry"] == {
        "is_entry_point": True,
        "config": {"name": "Dock"},
    }
    assert nodes["Airlock"]["visibility"]["global"] is False
    assert nodes["Airlock"]["visibility"]["interior"] is True
    assert nodes["Ship"]["vehicle"]["vehicle_id"] == "ship-01"
    assert "Secret ambush" not in json.dumps(snapshot)
    assert snapshot["hierarchy"][1]["name"] == "Ship"
    assert [child["name"] for child in snapshot["hierarchy"][1]["children"]] == [
        "Airlock",
        "Bridge",
    ]
    json.dumps(snapshot)


def test_interior_layout_is_deterministic_and_honors_inferred_children(tmp_path):
    nodes = {
        "location:base": _location(
            "Base",
            type="compound",
            entry_points=["Door"],
        ),
        "location:door": _location("Door", type="interior", parent="Base"),
        "location:hall": _location("Hall", type="interior", parent="Base"),
        "location:lab": _location(
            "Lab",
            type="interior",
            parent="Base",
            hidden=True,
        ),
    }
    edges = [
        {
            "from": "location:door",
            "to": "location:hall",
            "type": "connected",
            "data": {},
        },
        {
            "from": "location:hall",
            "to": "location:door",
            "type": "connected",
            "data": {},
        },
        {
            "from": "location:hall",
            "to": "location:lab",
            "type": "connected",
            "data": {},
        },
        {
            "from": "location:lab",
            "to": "location:hall",
            "type": "connected",
            "data": {},
        },
    ]
    campaign = _write_campaign(
        tmp_path,
        modules={"world-travel": True},
        nodes=nodes,
        edges=edges,
        position={"current_location": "Hall"},
    )

    first = get_map_snapshot(campaign)
    second = get_map_snapshot(campaign)

    assert first["layouts"] == second["layouts"]
    assert set(first["layouts"]["Base"]) == {"Door", "Hall"}
    positions = first["layouts"]["Base"].values()
    assert len({(position["x"], position["y"]) for position in positions}) == 2
    assert all(40 <= position["x"] <= 760 for position in positions)
    assert all(40 <= position["y"] <= 560 for position in positions)
    projected = {node["name"]: node for node in first["nodes"]}
    assert projected["Base"]["children"] == ["Door", "Hall"]
    assert "Lab" not in json.dumps(first)
