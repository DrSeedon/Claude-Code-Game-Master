#!/usr/bin/env python3
"""Apply one complete narrative scene transition through a single command."""

from __future__ import annotations

import argparse
import importlib
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from session_manager import SessionManager
from time_manager import TimeManager
from world_graph import WorldGraph


class SceneTransitionError(ValueError):
    """Raised before a transition when a referenced entity is invalid."""


class SceneManager:
    def __init__(self, world_state_dir: str = "world-state"):
        self.world_state_dir = world_state_dir
        campaign_dir = CampaignManager(world_state_dir).get_active_campaign_dir()
        if campaign_dir is None:
            raise SceneTransitionError("No active campaign")
        self.campaign_dir = campaign_dir
        self.graph = WorldGraph(campaign_dir)
        self.session = SessionManager(world_state_dir)

    def _world_travel_enabled(self) -> bool:
        overview = self.session.json_ops.load_json("campaign-overview.json")
        modules = overview.get("modules", {})
        if isinstance(modules, list):
            return "world-travel" in modules
        return isinstance(modules, dict) and bool(modules.get("world-travel"))

    def _world_travel_adapter(self):
        module_lib = (
            Path(__file__).parents[1]
            / ".claude"
            / "additional"
            / "modules"
            / "world-travel"
            / "lib"
        )
        if not module_lib.exists():
            raise SceneTransitionError("world-travel is enabled but not installed")
        module_path = str(module_lib)
        if module_path not in sys.path:
            sys.path.insert(0, module_path)
        return importlib.import_module("movement_adapter").WorldTravelMovementAdapter(
            self.campaign_dir
        )

    def _resolve_required(self, value: str, node_type: str, label: str) -> str:
        node_id = self.graph._resolve_id(value, node_type)
        node = self.graph.get_node(node_id) if node_id else None
        if not node or node.get("type") != node_type:
            raise SceneTransitionError(f"Unknown {label}: {value}")
        return node_id

    def _find_location(self, name: str) -> str | None:
        folded = name.casefold()
        for node in self.graph.list_nodes("location"):
            if node.get("name", "").casefold() == folded:
                return node["id"]
        return None

    def _validate_pairs(
        self,
        values: Iterable[tuple[str, str]],
        node_type: str,
        label: str,
    ) -> list[tuple[str, str]]:
        return [
            (self._resolve_required(entity, node_type, label), text)
            for entity, text in values
        ]

    def transition(
        self,
        location: str,
        *,
        description: str = "",
        from_location: str | None = None,
        path: str = "traveled",
        elapsed: float = 0,
        speed_multiplier: float = 1.0,
        move_party: bool = True,
        with_npcs: Iterable[str] = (),
        resolve_consequences: Iterable[tuple[str, str]] = (),
        add_objectives: Iterable[tuple[str, str]] = (),
    ) -> dict:
        if elapsed < 0:
            raise SceneTransitionError("Elapsed time cannot be negative")
        if speed_multiplier <= 0:
            raise SceneTransitionError("Speed multiplier must be positive")

        old_location = from_location or self.session._get_current_location()
        moved_npc_ids: set[str] = set()
        triggered: set[str] = set()

        source_id = None
        if old_location:
            source_id = self._resolve_required(
                old_location, "location", "source location"
            )
        extra_npc_ids = [
            self._resolve_required(name, "npc", "NPC") for name in with_npcs
        ]
        consequence_updates = self._validate_pairs(
            resolve_consequences, "consequence", "consequence"
        )
        objective_updates = self._validate_pairs(
            add_objectives, "quest", "quest"
        )

        destination_id = self._find_location(location)
        created_location = destination_id is None
        with self.graph.transaction():
            if destination_id is None:
                destination_id = self.graph.location_create(location, description)
            elif description:
                node = self.graph.get_node(destination_id)
                if not node.get("data", {}).get("description"):
                    if not self.graph.update_node(
                        destination_id, {"data": {"description": description}}
                    ):
                        raise SceneTransitionError(
                            f"Failed to describe location: {location}"
                        )

            if source_id and source_id != destination_id:
                if not self.graph.location_connect(source_id, destination_id, path):
                    raise SceneTransitionError(f"Failed to connect location: {location}")

        travel_elapsed = 0.0
        current_location = location
        world_travel = self._world_travel_enabled()
        if world_travel:
            movement = self._world_travel_adapter().move(
                location,
                speed_multiplier=speed_multiplier,
                move_party=move_party,
            )
            if not movement.get("success"):
                raise SceneTransitionError(
                    f"world-travel move failed: {movement.get('error', 'unknown error')}"
                )
            current_location = movement.get("location", location)
            travel_elapsed = float(movement.get("elapsed_hours", 0))
            moved_npc_ids.update(movement.get("moved_party_members", []))
            triggered.update(movement.get("triggered_consequences", []))

        destination_id = self._resolve_required(
            current_location, "location", "destination location"
        )
        with self.graph.transaction():
            npc_ids = set(extra_npc_ids)
            if not world_travel:
                player_id = self.graph._player_id()
                if player_id and not self.graph.update_node(
                    player_id, {"data": {"current_location": current_location}}
                ):
                    raise SceneTransitionError("Failed to move player")

            if move_party and not world_travel:
                npc_ids.update(
                    node["id"]
                    for node in self.graph.list_nodes("npc")
                    if node.get("data", {}).get("party_member")
                    or node.get("data", {}).get("is_party_member")
                )

            for npc_id in sorted(npc_ids):
                if not self.graph.npc_locate(npc_id, destination_id):
                    raise SceneTransitionError(f"Failed to move NPC: {npc_id}")
                moved_npc_ids.add(npc_id)

            if elapsed:
                with redirect_stdout(io.StringIO()):
                    tick_result = self.graph.tick(elapsed)
                triggered.update(
                    item["id"] for item in tick_result.get("consequences", [])
                )

            for consequence_id, resolution in consequence_updates:
                if not self.graph.consequence_resolve(consequence_id, resolution):
                    raise SceneTransitionError(
                        f"Failed to resolve consequence: {consequence_id}"
                    )

            for quest_id, objective in objective_updates:
                if not self.graph.quest_objective_add(quest_id, objective):
                    raise SceneTransitionError(f"Failed to update quest: {quest_id}")

        self.session._update_position_metadata(
            old_location or "Unknown", current_location
        )
        if elapsed:
            with redirect_stdout(io.StringIO()):
                TimeManager(self.world_state_dir).advance(elapsed)

        current_time = TimeManager(self.world_state_dir).get_time()
        moved_npcs = [
            self.graph.get_node(npc_id).get("name", npc_id)
            for npc_id in moved_npc_ids
            if self.graph.get_node(npc_id)
        ]
        return {
            "previous_location": old_location,
            "current_location": current_location,
            "created_location": created_location,
            "moved_npcs": sorted(moved_npcs),
            "elapsed_hours": travel_elapsed + elapsed,
            "travel_elapsed_hours": travel_elapsed,
            "scene_elapsed_hours": elapsed,
            "current_time": current_time["precise_time"],
            "triggered_consequences": sorted(triggered),
            "resolved_consequences": [item[0] for item in consequence_updates],
            "objectives_added": len(objective_updates),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply a complete scene transition in one command"
    )
    parser.add_argument("location", help="Destination location")
    parser.add_argument("--description", default="", help="Description for a new location")
    parser.add_argument("--from", dest="from_location", help="Connection source override")
    parser.add_argument("--path", default="traveled", help="Connection description")
    parser.add_argument("--elapsed", type=float, default=0, help="Elapsed game hours")
    parser.add_argument(
        "--speed-multiplier",
        type=float,
        default=1.0,
        help="Travel speed multiplier used by world-travel",
    )
    parser.add_argument(
        "--player-only",
        action="store_true",
        help="Do not move party-member NPCs",
    )
    parser.add_argument(
        "--with",
        dest="with_npcs",
        action="append",
        default=[],
        metavar="NPC",
        help="Move an additional non-party NPC; repeat as needed",
    )
    parser.add_argument(
        "--resolve",
        action="append",
        nargs=2,
        default=[],
        metavar=("CONSEQUENCE", "RESOLUTION"),
        help="Resolve a consequence; repeat as needed",
    )
    parser.add_argument(
        "--objective",
        action="append",
        nargs=2,
        default=[],
        metavar=("QUEST", "TEXT"),
        help="Add a quest objective; repeat as needed",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = SceneManager().transition(
            args.location,
            description=args.description,
            from_location=args.from_location,
            path=args.path,
            elapsed=args.elapsed,
            speed_multiplier=args.speed_multiplier,
            move_party=not args.player_only,
            with_npcs=args.with_npcs,
            resolve_consequences=args.resolve,
            add_objectives=args.objective,
        )
    except SceneTransitionError as exc:
        print(f"Error: {exc}")
        return 1

    created = "created" if result["created_location"] else "existing"
    print(
        f"SCENE: {result['previous_location']} -> {result['current_location']} "
        f"({created}, +{result['elapsed_hours']:g}h, {result['current_time']})"
    )
    print(f"  Party NPCs moved: {len(result['moved_npcs'])}")
    if result["triggered_consequences"]:
        print("  Triggered: " + ", ".join(result["triggered_consequences"]))
    if result["resolved_consequences"]:
        print(f"  Consequences resolved: {len(result['resolved_consequences'])}")
    if result["objectives_added"]:
        print(f"  Quest objectives added: {result['objectives_added']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
