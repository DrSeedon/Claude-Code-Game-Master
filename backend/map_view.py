"""Read-only web projection for world-travel map data."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORLD_TRAVEL_LIB = (
    PROJECT_ROOT / ".claude" / "additional" / "modules" / "world-travel" / "lib"
)


def _load_world_travel_module(name: str) -> ModuleType:
    path = WORLD_TRAVEL_LIB / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_dm_world_travel_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load world-travel module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_store_module = _load_world_travel_module("world_travel_store")
_connections_module = _load_world_travel_module("connection_utils")
_layout_module = _load_world_travel_module("force_layout")

WorldTravelStore = _store_module.WorldTravelStore
get_unique_edges = _connections_module.get_unique_edges
compute_layout = _layout_module.compute_layout


def _empty_snapshot(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "current": {
            "location": None,
            "context": "global",
            "compound": None,
            "global_location": None,
            "vehicle_id": None,
            "coordinates": None,
        },
        "nodes": [],
        "connections": [],
        "hierarchy": [],
        "breadcrumb": ["World"],
        "layouts": {},
    }


def _world_travel_enabled(overview: dict[str, Any]) -> bool:
    modules = overview.get("modules")
    if isinstance(modules, list):
        return "world-travel" in modules
    if isinstance(modules, dict):
        return bool(modules.get("world-travel", False))
    return False


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _coordinate(data: dict[str, Any]) -> dict[str, float] | None:
    coordinates = data.get("coordinates")
    if not isinstance(coordinates, dict):
        return None
    x = coordinates.get("x")
    y = coordinates.get("y")
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return None
    if not isinstance(y, (int, float)) or isinstance(y, bool):
        return None
    return {"x": x, "y": y}


def _ancestor_chain(
    location: str | None,
    locations: dict[str, dict[str, Any]],
) -> list[str]:
    chain: list[str] = []
    seen: set[str] = set()
    current = location
    while current and current in locations and current not in seen:
        seen.add(current)
        chain.append(current)
        parent = locations[current].get("parent")
        current = parent if isinstance(parent, str) and parent else None
    chain.reverse()
    return chain


def _children_index(
    locations: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    children: dict[str, set[str]] = {name: set() for name in locations}
    for name, data in locations.items():
        declared = data.get("children")
        if isinstance(declared, list):
            children[name].update(
                child for child in declared if isinstance(child, str) and child in locations
            )
        parent = data.get("parent")
        if isinstance(parent, str) and parent in locations:
            children[parent].add(name)
    return {name: sorted(names) for name, names in children.items()}


def _hierarchy(
    locations: dict[str, dict[str, Any]],
    children: dict[str, list[str]],
) -> list[dict[str, Any]]:
    def build(name: str, ancestors: set[str]) -> dict[str, Any]:
        if name in ancestors:
            return {"name": name, "type": locations[name].get("type", "world"), "children": []}
        next_ancestors = ancestors | {name}
        return {
            "name": name,
            "type": locations[name].get("type", "world"),
            "children": [
                build(child, next_ancestors)
                for child in children.get(name, [])
                if child not in next_ancestors
            ],
        }

    roots = sorted(
        name
        for name, data in locations.items()
        if not isinstance(data.get("parent"), str) or data.get("parent") not in locations
    )
    return [build(root, set()) for root in roots]


def _connection_projection(
    locations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_source, raw_target, raw_data in get_unique_edges(locations):
        source, target = sorted((raw_source, raw_target))
        data = dict(raw_data or {})
        bearing = data.get("bearing")
        if raw_source != source and isinstance(bearing, (int, float)):
            bearing = (bearing + 180) % 360
        result.append(
            {
                "source": source,
                "target": target,
                "distance_meters": data.get("distance_meters"),
                "terrain": data.get("terrain"),
                "path": data.get("path"),
                "bearing": bearing,
            }
        )
    return sorted(result, key=lambda edge: (edge["source"], edge["target"]))


def _interior_layouts(
    locations: dict[str, dict[str, Any]],
    children: dict[str, list[str]],
    connections: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    layouts: dict[str, dict[str, dict[str, float]]] = {}
    # The legacy layout cache omits entry points from its key. Clear it so two
    # campaigns with the same room graph cannot reuse a differently-oriented map.
    _layout_module._cache.clear()
    edge_pairs = {
        tuple(sorted((edge["source"], edge["target"])))
        for edge in connections
    }
    for compound in sorted(locations):
        compound_children = children.get(compound, [])
        if not compound_children:
            continue
        if locations[compound].get("type") != "compound":
            continue
        child_set = set(compound_children)
        interior_edges = sorted(
            pair
            for pair in edge_pairs
            if pair[0] in child_set and pair[1] in child_set
        )
        entry_points = sorted(
            entry
            for entry in locations[compound].get("entry_points", [])
            if entry in child_set
        )
        raw_layout = compute_layout(
            sorted(compound_children),
            interior_edges,
            entry_points=entry_points,
            width=800,
            height=600,
        )
        layouts[compound] = {
            name: {
                "x": round(float(raw_layout[name]["x"]), 3),
                "y": round(float(raw_layout[name]["y"]), 3),
            }
            for name in sorted(raw_layout)
        }
    return layouts


def get_map_snapshot(campaign_dir: str | Path) -> dict[str, Any]:
    """Return a JSON-safe, read-only map view for one campaign."""
    campaign_path = Path(campaign_dir)
    overview_path = campaign_path / "campaign-overview.json"
    try:
        overview = json.loads(overview_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        overview = {}
    if not isinstance(overview, dict) or not _world_travel_enabled(overview):
        return _empty_snapshot(enabled=False)

    snapshot = _empty_snapshot(enabled=True)
    store = WorldTravelStore(campaign_path)
    locations = store.load_locations()
    if not locations:
        return snapshot

    children = _children_index(locations)
    player_data = store.get_player_data()
    player_position = overview.get("player_position")
    if not isinstance(player_position, dict):
        player_position = {}
    current_location = (
        player_position.get("current_location")
        or overview.get("current_location")
        or player_data.get("current_location")
    )
    if current_location not in locations:
        current_location = None

    chain = _ancestor_chain(current_location, locations)
    current_data = locations.get(current_location, {})
    parent = current_data.get("parent")
    compound = parent if isinstance(parent, str) and parent in locations else None
    global_location = chain[0] if chain else current_location
    map_context = player_position.get("map_context")
    if map_context not in {"global", "local", "interior"}:
        map_context = "interior" if compound else "global"
    context = "interior" if map_context in {"local", "interior"} else "global"
    vehicle = current_data.get("_vehicle")
    vehicle_id = player_position.get("vehicle_id")
    if not vehicle_id and isinstance(vehicle, dict):
        vehicle_id = vehicle.get("vehicle_id")

    snapshot["current"] = {
        "location": current_location,
        "context": context,
        "compound": compound,
        "global_location": global_location,
        "vehicle_id": vehicle_id,
        "coordinates": _coordinate(locations.get(global_location, {})),
    }
    snapshot["breadcrumb"] = ["World", *chain]
    snapshot["hierarchy"] = _hierarchy(locations, children)

    nodes = []
    for name in sorted(locations):
        data = locations[name]
        parent = data.get("parent")
        parent = parent if isinstance(parent, str) and parent in locations else None
        location_type = data.get("type", "world")
        entry_points = set(locations.get(parent, {}).get("entry_points", []))
        discovered = bool(data.get("discovered", data.get("known", True)))
        hidden = bool(data.get("hidden", False))
        global_eligible = parent is None and location_type != "interior"
        interior_eligible = parent is not None
        nodes.append(
            {
                "id": name,
                "name": name,
                "type": location_type,
                "coordinates": _coordinate(data),
                "parent": parent,
                "children": children.get(name, []),
                "entry": {
                    "is_entry_point": name in entry_points,
                    "config": _json_safe(data.get("entry_config") or {}),
                },
                "vehicle": _json_safe(data.get("_vehicle")) if data.get("_vehicle") else None,
                "visibility": {
                    "discovered": discovered,
                    "hidden": hidden,
                    "global": global_eligible and discovered and not hidden,
                    "interior": interior_eligible and discovered and not hidden,
                },
            }
        )

    snapshot["nodes"] = nodes
    snapshot["connections"] = _connection_projection(locations)
    snapshot["layouts"] = _interior_layouts(
        locations,
        children,
        snapshot["connections"],
    )
    return _json_safe(snapshot)
