#!/usr/bin/env python3
"""Idempotent migration from legacy campaign JSON files into WorldGraph."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .campaign_schema import CAMPAIGN_SCHEMA_VERSION
    from .json_ops import JsonOperations
    from .world_graph import WorldGraph
except ImportError:
    from campaign_schema import CAMPAIGN_SCHEMA_VERSION
    from json_ops import JsonOperations
    from world_graph import WorldGraph


LEGACY_FILES = (
    "character.json",
    "npcs.json",
    "locations.json",
    "facts.json",
    "consequences.json",
    "plots.json",
)


class LegacyCampaignMigrator:
    def __init__(self, campaign_dir: str | Path):
        self.campaign_dir = Path(campaign_dir)
        self.graph = WorldGraph(self.campaign_dir)
        self.report = {
            "campaign": self.campaign_dir.name,
            "files_found": [],
            "nodes_added": 0,
            "edges_added": 0,
            "nodes_skipped": 0,
            "nodes_updated": 0,
        }

    def _read(self, filename: str, default: Any) -> Any:
        path = self.campaign_dir / filename
        if not path.exists():
            return default
        self.report["files_found"].append(filename)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if filename in LEGACY_FILES and not isinstance(data, dict):
            raise ValueError(f"{filename} must contain a JSON object")
        return data

    def _node_id(self, world: dict, node_type: str, name: str) -> str:
        for node_id, node in world["nodes"].items():
            if node.get("type") == node_type and node.get("name") == name:
                return node_id
        base = f"{node_type}:{self.graph._slug(name)}"
        candidate = base
        suffix = 2
        while candidate in world["nodes"]:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _add_node(
        self,
        world: dict,
        node_id: str,
        node_type: str,
        name: str,
        data: dict,
    ) -> str:
        if node_id in world["nodes"]:
            existing_data = world["nodes"][node_id].setdefault("data", {})
            changed = False
            for key, value in data.items():
                if key not in existing_data:
                    existing_data[key] = copy.deepcopy(value)
                    changed = True
            if changed:
                self.report["nodes_updated"] += 1
            self.report["nodes_skipped"] += 1
            return node_id
        world["nodes"][node_id] = {
            "type": node_type,
            "name": name,
            "data": copy.deepcopy(data),
        }
        self.report["nodes_added"] += 1
        return node_id

    def _add_edge(
        self,
        world: dict,
        source: str,
        target: str,
        edge_type: str,
        data: dict | None = None,
    ) -> None:
        if source not in world["nodes"] or target not in world["nodes"]:
            return
        if any(
            edge.get("from") == source
            and edge.get("to") == target
            and edge.get("type") == edge_type
            for edge in world["edges"]
        ):
            return
        edge = {"from": source, "to": target, "type": edge_type}
        if data:
            edge["data"] = copy.deepcopy(data)
        world["edges"].append(edge)
        self.report["edges_added"] += 1

    def _migrate_player(self, world: dict) -> None:
        character = self._read("character.json", {})
        if not isinstance(character, dict) or not character:
            return
        name = str(character.get("name") or character.get("id") or "Hero")
        data = {key: value for key, value in character.items() if key != "name"}
        self._add_node(world, "player:active", "player", name, data)

    def _migrate_locations(self, world: dict) -> dict[str, str]:
        locations = self._read("locations.json", {})
        if not isinstance(locations, dict):
            return {}
        ids = {}
        for name, raw in locations.items():
            data = copy.deepcopy(raw) if isinstance(raw, dict) else {"description": str(raw)}
            data.pop("connections", None)
            node_id = self._node_id(world, "location", name)
            ids[name] = self._add_node(world, node_id, "location", name, data)

        for name, raw in locations.items():
            if not isinstance(raw, dict):
                continue
            for connection in raw.get("connections", []):
                if isinstance(connection, str):
                    target_name, edge_data = connection, {"path": "traveled"}
                elif isinstance(connection, dict):
                    target_name = connection.get("to")
                    edge_data = {
                        key: value
                        for key, value in connection.items()
                        if key != "to"
                    }
                else:
                    continue
                if target_name not in ids:
                    continue
                edge_data.setdefault(
                    "path_type", edge_data.get("path", "traveled")
                )
                self._add_edge(
                    world, ids[name], ids[target_name], "connected", edge_data
                )
                reverse = copy.deepcopy(edge_data)
                if reverse.get("bearing") is not None:
                    reverse["bearing"] = (reverse["bearing"] + 180) % 360
                self._add_edge(
                    world, ids[target_name], ids[name], "connected", reverse
                )
        return ids

    def _migrate_npcs(self, world: dict, locations: dict[str, str]) -> dict[str, str]:
        npcs = self._read("npcs.json", {})
        if not isinstance(npcs, dict):
            return {}
        ids = {}
        for name, raw in npcs.items():
            data = copy.deepcopy(raw) if isinstance(raw, dict) else {"description": str(raw)}
            node_id = self._node_id(world, "npc", name)
            ids[name] = self._add_node(world, node_id, "npc", name, data)
            tags = data.get("tags", {})
            for location_name in tags.get("locations", []) if isinstance(tags, dict) else []:
                location_id = locations.get(location_name)
                if location_id:
                    self._add_edge(world, ids[name], location_id, "at")
        return ids

    def _migrate_facts(self, world: dict) -> None:
        facts = self._read("facts.json", {})
        if not isinstance(facts, dict):
            return
        for category, entries in facts.items():
            if not isinstance(entries, list):
                entries = [entries]
            for entry in entries:
                if isinstance(entry, dict):
                    text = str(entry.get("fact") or entry.get("text") or entry)
                    data = copy.deepcopy(entry)
                    data.pop("fact", None)
                    data.pop("text", None)
                else:
                    text, data = str(entry), {}
                digest = hashlib.sha1(
                    f"{category}\0{text}".encode("utf-8")
                ).hexdigest()[:12]
                node_id = f"fact:legacy-{digest}"
                data.update({"category": category, "text": text})
                self._add_node(
                    world,
                    node_id,
                    "fact",
                    f"[{category}] {text[:40]}",
                    data,
                )

    def _migrate_consequences(self, world: dict) -> None:
        consequences = self._read("consequences.json", {})
        if not isinstance(consequences, dict):
            return
        for status, entries in consequences.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    entry = {"consequence": str(entry)}
                description = str(
                    entry.get("consequence")
                    or entry.get("description")
                    or "Legacy consequence"
                )
                legacy_id = str(entry.get("id") or "")
                suffix = (
                    legacy_id.lower()
                    if legacy_id.isalnum()
                    else hashlib.sha1(description.encode("utf-8")).hexdigest()[:12]
                )
                node_id = f"consequence:legacy-{suffix}"
                data = copy.deepcopy(entry)
                data.pop("id", None)
                data.pop("consequence", None)
                data["description"] = description
                data["status"] = "pending" if status == "active" else status
                self._add_node(
                    world, node_id, "consequence", description[:40], data
                )

    def _migrate_plots(
        self,
        world: dict,
        npcs: dict[str, str],
        locations: dict[str, str],
    ) -> None:
        plots = self._read("plots.json", {})
        if not isinstance(plots, dict):
            return
        for name, raw in plots.items():
            data = copy.deepcopy(raw) if isinstance(raw, dict) else {"description": str(raw)}
            data["quest_type"] = data.pop("type", data.get("quest_type", "side"))
            objectives = []
            for objective in data.get("objectives", []):
                if isinstance(objective, dict):
                    objectives.append({
                        "text": objective.get("text", ""),
                        "done": bool(
                            objective.get("done", objective.get("completed", False))
                        ),
                    })
                else:
                    objectives.append({"text": str(objective), "done": False})
            data["objectives"] = objectives
            quest_npcs = data.pop("npcs", [])
            quest_locations = data.pop("locations", [])
            node_id = self._node_id(world, "quest", name)
            node_id = self._add_node(world, node_id, "quest", name, data)
            for npc_name in quest_npcs:
                if npc_name in npcs:
                    self._add_edge(world, node_id, npcs[npc_name], "involves")
            for location_name in quest_locations:
                if location_name in locations:
                    self._add_edge(
                        world, node_id, locations[location_name], "involves"
                    )

    def migrate(self, dry_run: bool = False) -> dict[str, Any]:
        def apply(world: dict) -> None:
            self._migrate_player(world)
            locations = self._migrate_locations(world)
            npcs = self._migrate_npcs(world, locations)
            if "player:active" in world["nodes"]:
                for npc_id in npcs.values():
                    self._add_edge(
                        world,
                        "player:active",
                        npc_id,
                        "known_by",
                        {"source": "legacy-migration"},
                    )
            self._migrate_facts(world)
            self._migrate_consequences(world)
            self._migrate_plots(world, npcs, locations)

        if dry_run:
            world = copy.deepcopy(self.graph.repository.load())
            apply(world)
        else:
            with self.graph.transaction() as world:
                apply(world)
            overview_ops = JsonOperations(str(self.campaign_dir))
            with overview_ops.transaction("campaign-overview.json") as overview:
                overview["schema_version"] = CAMPAIGN_SCHEMA_VERSION
                overview.setdefault("name", self.campaign_dir.name)
                overview.setdefault(
                    "campaign_name",
                    overview.get("name", self.campaign_dir.name),
                )
                if isinstance(overview.get("modules"), list):
                    overview["modules"] = {
                        module_id: True for module_id in overview["modules"]
                    }
        return copy.deepcopy(self.report)

    def remove_legacy_files(self) -> list[str]:
        """Delete migrated sources only when their data can be parsed."""
        removed = []
        for filename in LEGACY_FILES:
            path = self.campaign_dir / filename
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError(f"{filename} must contain a JSON object")
            path.unlink()
            removed.append(filename)
        return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy campaign JSON")
    parser.add_argument("campaign_dir")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-legacy", action="store_true")
    args = parser.parse_args()

    migrator = LegacyCampaignMigrator(args.campaign_dir)
    report = migrator.migrate(dry_run=args.dry_run)
    if args.remove_legacy:
        if args.dry_run:
            parser.error("--remove-legacy cannot be combined with --dry-run")
        report["files_removed"] = migrator.remove_legacy_files()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
