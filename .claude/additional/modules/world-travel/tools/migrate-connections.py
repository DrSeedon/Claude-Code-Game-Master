#!/usr/bin/env python3
"""Import legacy world-travel locations.json into WorldGraph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = next(path for path in Path(__file__).parents if (path / ".git").exists())
MODULE_LIB = PROJECT_ROOT / ".claude" / "additional" / "modules" / "world-travel" / "lib"
sys.path.insert(0, str(MODULE_LIB))
sys.path.insert(0, str(PROJECT_ROOT))

from lib.campaign_context import resolve_campaign_dir, scoped_campaign_name
from world_travel_store import WorldTravelStore


def campaign_dir(name: str | None) -> Path:
    world_state = PROJECT_ROOT / "world-state"
    selected = name or scoped_campaign_name(world_state)
    if not selected:
        raise RuntimeError("No active campaign")
    return resolve_campaign_dir(
        world_state / "campaigns", selected, must_exist=True
    )


def import_legacy(target: Path, apply: bool = False) -> int:
    """Validate and optionally import one legacy campaign file."""
    legacy_file = target / "locations.json"
    if not legacy_file.exists():
        print(f"No legacy locations.json found in {target}")
        return 0

    locations = json.loads(legacy_file.read_text(encoding="utf-8"))
    if not isinstance(locations, dict):
        raise RuntimeError("Legacy locations.json must contain an object")

    connection_count = sum(
        len(location.get("connections", []))
        for location in locations.values()
        if isinstance(location, dict)
    )
    print(
        f"Legacy import: {len(locations)} locations, "
        f"{connection_count} stored connections"
    )
    character_file = target / "character.json"
    speed_kmh = None
    if character_file.exists():
        character = json.loads(character_file.read_text(encoding="utf-8"))
        if isinstance(character, dict):
            speed_kmh = character.get("speed_kmh")
            if speed_kmh is not None:
                print(f"Legacy player travel speed: {speed_kmh} km/h")
    if not apply:
        print("Dry run only; pass --apply to write WorldGraph")
        return 0

    store = WorldTravelStore(target)
    store.save_locations(locations)
    if speed_kmh is not None:
        player_id = store.graph._player_id()
        if player_id:
            store.graph.update_node(player_id, {"data": {"speed_kmh": speed_kmh}})
        else:
            print("Player speed was not imported because WorldGraph has no player node")
    print("Imported legacy world-travel state into world.json")
    print("The source locations.json was preserved for manual verification")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy world-travel flat state into WorldGraph"
    )
    campaign_group = parser.add_mutually_exclusive_group()
    campaign_group.add_argument("--campaign")
    campaign_group.add_argument("--campaign-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    target = args.campaign_dir or campaign_dir(args.campaign)
    return import_legacy(target, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
