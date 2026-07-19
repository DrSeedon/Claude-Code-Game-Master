#!/usr/bin/env python3
"""Single movement entry point for world-travel middleware and scene orchestration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = next(path for path in MODULE_DIR.parents if (path / "pyproject.toml").exists())
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(MODULE_DIR))

from hierarchy_manager import HierarchyManager
from navigation_manager import NavigationManager
from vehicle_manager import VehicleManager
from world_travel_store import active_campaign_dir


class WorldTravelMovementAdapter:
    """Route a move through hierarchy, vehicle, or overland navigation logic."""

    def __init__(self, campaign_dir: str | Path):
        self.campaign_dir = Path(campaign_dir)
        self.hierarchy = HierarchyManager(str(self.campaign_dir))
        self.vehicle = VehicleManager(str(self.campaign_dir))
        self.navigation = NavigationManager(str(self.campaign_dir))

    def _sync_party(self, location: str, move_party: bool) -> dict[str, Any]:
        return self.navigation._move_party_to(location, move_party=move_party)

    def move(
        self,
        destination: str,
        *,
        speed_multiplier: float = 1.0,
        move_party: bool = True,
    ) -> dict[str, Any]:
        if speed_multiplier <= 0:
            return {"success": False, "error": "Speed multiplier must be positive"}

        if self.hierarchy.get_location_type(destination) == "compound":
            result = self.hierarchy.enter_compound(destination)
            if result.get("success"):
                sync = self._sync_party(result["location"], move_party)
                if not sync.get("success"):
                    return sync
                result.update({
                    "movement_kind": "compound",
                    "elapsed_hours": 0.0,
                    "moved_party_members": sync.get("moved_party_members", []),
                })
            return result

        vehicle_status = self.vehicle.get_status()
        player_position = vehicle_status.get("player_position", {})
        vehicle_id = player_position.get("vehicle_id")
        rooms = []
        if player_position.get("map_context") == "local" and vehicle_id:
            rooms = self.vehicle.get_status(vehicle_id).get("rooms", [])
        if destination in rooms:
            result = self.vehicle.move_internal(destination)
            if result.get("success"):
                sync = self._sync_party(destination, move_party)
                if not sync.get("success"):
                    return sync
                result.update({
                    "location": destination,
                    "movement_kind": "vehicle_internal",
                    "elapsed_hours": 0.0,
                    "moved_party_members": sync.get("moved_party_members", []),
                })
            return result

        result = self.navigation.move_with_navigation(
            destination,
            speed_multiplier=speed_multiplier,
            move_party=move_party,
        )
        if result.get("success"):
            result["movement_kind"] = "overland"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Move using world-travel routing")
    parser.add_argument("destination")
    parser.add_argument("--campaign-dir")
    parser.add_argument("--speed-multiplier", type=float, default=1.0)
    parser.add_argument("--player-only", action="store_true")
    args = parser.parse_args()

    campaign_dir = Path(args.campaign_dir) if args.campaign_dir else active_campaign_dir()
    if campaign_dir is None:
        print(json.dumps({"success": False, "error": "No active campaign"}))
        return 1

    result = WorldTravelMovementAdapter(campaign_dir).move(
        args.destination,
        speed_multiplier=args.speed_multiplier,
        move_party=not args.player_only,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
