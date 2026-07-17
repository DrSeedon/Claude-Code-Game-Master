"""WorldGraph-backed persistence adapter for the world-travel module."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = next(path for path in Path(__file__).parents if (path / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.json_ops import JsonOperations
from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
    scoped_campaign_name,
)
from lib.world_graph import WorldGraph


def active_campaign_dir() -> Path | None:
    world_state = PROJECT_ROOT / "world-state"
    try:
        name = scoped_campaign_name(world_state)
        if not name:
            return None
        return resolve_campaign_dir(
            world_state / "campaigns", name, must_exist=True
        )
    except (InvalidCampaignName, FileNotFoundError):
        return None


class WorldTravelStore:
    """Expose the legacy location-dict API as a projection of WorldGraph."""

    def __init__(self, campaign_dir: str | Path):
        self.campaign_dir = Path(campaign_dir)
        self.graph = WorldGraph(self.campaign_dir)
        self.json_ops = JsonOperations(str(self.campaign_dir))

    def load_locations(self) -> dict[str, dict[str, Any]]:
        with self.graph.transaction() as snapshot:
            world = copy.deepcopy(snapshot)
        location_nodes = {
            node_id: node
            for node_id, node in world["nodes"].items()
            if node.get("type") == "location"
        }
        result = {
            node["name"]: {
                **copy.deepcopy(node.get("data", {})),
                "connections": [],
            }
            for node in location_nodes.values()
        }

        edge_by_pair: dict[tuple[str, str], tuple[str, str, dict]] = {}
        for edge in world["edges"]:
            if edge.get("type") != "connected":
                continue
            source = location_nodes.get(edge.get("from"))
            target = location_nodes.get(edge.get("to"))
            if not source or not target:
                continue
            source_name = source["name"]
            target_name = target["name"]
            pair = tuple(sorted((source_name, target_name)))
            current = edge_by_pair.get(pair)
            if current is None or source_name == pair[0]:
                edge_by_pair[pair] = (
                    source_name,
                    target_name,
                    copy.deepcopy(edge.get("data") or {}),
                )

        for (first, second), (source_name, _target_name, edge_data) in edge_by_pair.items():
            if source_name != first and edge_data.get("bearing") is not None:
                edge_data["bearing"] = (edge_data["bearing"] + 180) % 360
            edge_data["to"] = second
            result[first]["connections"].append(edge_data)

        return result

    def save_locations(self, locations: dict[str, dict[str, Any]]) -> bool:
        with self.graph.transaction() as world:
            name_to_id = {
                node["name"]: node_id
                for node_id, node in world["nodes"].items()
                if node.get("type") == "location"
            }

            for name, location in locations.items():
                node_id = name_to_id.get(name)
                if node_id is None:
                    node_id = f"location:{self.graph._slug(name)}"
                    suffix = 2
                    while node_id in world["nodes"]:
                        node_id = f"location:{self.graph._slug(name)}-{suffix}"
                        suffix += 1
                    world["nodes"][node_id] = {
                        "type": "location",
                        "name": name,
                        "data": {},
                    }
                    name_to_id[name] = node_id

                data = copy.deepcopy(location)
                data.pop("connections", None)
                world["nodes"][node_id].setdefault("data", {}).update(data)

            managed_ids = {name_to_id[name] for name in locations}
            world["edges"] = [
                edge
                for edge in world["edges"]
                if edge.get("type") != "connected"
                or edge.get("from") not in managed_ids
            ]

            seen_pairs: set[tuple[str, str]] = set()
            for source_name, location in locations.items():
                for connection in location.get("connections", []):
                    target_name = connection.get("to")
                    if target_name not in name_to_id or target_name == source_name:
                        continue
                    pair = tuple(sorted((source_name, target_name)))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)

                    first, second = pair
                    data = copy.deepcopy(connection)
                    data.pop("to", None)
                    if source_name != first and data.get("bearing") is not None:
                        data["bearing"] = (data["bearing"] + 180) % 360
                    reverse_data = copy.deepcopy(data)
                    if reverse_data.get("bearing") is not None:
                        reverse_data["bearing"] = (reverse_data["bearing"] + 180) % 360

                    world["edges"].append({
                        "from": name_to_id[first],
                        "to": name_to_id[second],
                        "type": "connected",
                        "data": data,
                    })
                    world["edges"].append({
                        "from": name_to_id[second],
                        "to": name_to_id[first],
                        "type": "connected",
                        "data": reverse_data,
                    })
        return True

    def load_overview(self) -> dict[str, Any]:
        return self.json_ops.load_json("campaign-overview.json") or {}

    def save_overview(self, overview: dict[str, Any]) -> bool:
        return self.json_ops.save_json("campaign-overview.json", overview)

    def update_player_position(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge position metadata without replacing unrelated overview fields."""
        with self.json_ops.transaction("campaign-overview.json") as overview:
            position = overview.setdefault("player_position", {})
            previous = copy.deepcopy(position)
            for key, value in updates.items():
                if value is None:
                    position.pop(key, None)
                else:
                    position[key] = value
            if "current_location" in updates and "current_location" in overview:
                overview["current_location"] = updates["current_location"]
        return previous

    def get_player_data(self) -> dict[str, Any]:
        player_id = self.graph._player_id()
        player = self.graph.get_node(player_id) if player_id else None
        return copy.deepcopy(player.get("data", {})) if player else {}
