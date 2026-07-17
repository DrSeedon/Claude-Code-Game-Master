#!/usr/bin/env python3
"""Convert legacy vehicle metadata on WorldGraph locations to hierarchy fields."""

import sys
from pathlib import Path


def _find_project_root() -> Path:
    for p in Path(__file__).parents:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("pyproject.toml not found")


PROJECT_ROOT = _find_project_root()
MODULE_LIB = PROJECT_ROOT / ".claude" / "additional" / "modules" / "world-travel" / "lib"
sys.path.insert(0, str(MODULE_LIB))

from world_travel_store import WorldTravelStore


def migrate_campaign(campaign_dir: Path, dry_run: bool = False) -> dict:
    store = WorldTravelStore(campaign_dir)
    locations = store.load_locations()
    if not locations:
        return {"skipped": True, "reason": "no WorldGraph locations"}

    changed = 0
    type_set = 0

    anchors: dict = {}
    for name, data in locations.items():
        v = data.get("_vehicle", {})
        if v.get("is_vehicle_anchor"):
            anchors[v.get("vehicle_id")] = name

    for name, data in locations.items():
        v = data.get("_vehicle", {})

        if not v:
            if "type" not in data:
                data["type"] = "world"
                type_set += 1
            continue

        if v.get("is_vehicle_anchor"):
            vehicle_id = v.get("vehicle_id", "")
            dock_room = v.get("dock_room", "")

            rooms = [
                n for n, d in locations.items()
                if d.get("_vehicle", {}).get("vehicle_id") == vehicle_id
                and not d.get("_vehicle", {}).get("is_vehicle_anchor")
            ]

            entry_points = [dock_room] if dock_room and dock_room in locations else []
            if not entry_points and rooms:
                entry_points = [rooms[0]]

            data["type"] = "compound"
            data["mobile"] = True
            data["children"] = rooms
            data["entry_points"] = entry_points
            changed += 1

        elif v.get("map_context") == "local":
            vehicle_id = v.get("vehicle_id", "")
            anchor_name = anchors.get(vehicle_id)

            data["type"] = "interior"
            if anchor_name:
                data["parent"] = anchor_name
                dock_room = locations.get(anchor_name, {}).get("_vehicle", {}).get("dock_room", "")
                if name == dock_room:
                    data["is_entry_point"] = True
                    data["entry_config"] = {"name": "Dock"}

            changed += 1

        else:
            if "type" not in data:
                data["type"] = "world"
                type_set += 1

    for name, data in locations.items():
        if data.get("type") == "compound":
            for child in data.get("children", []):
                if child in locations and "parent" not in locations[child]:
                    locations[child]["parent"] = name

    if changed == 0 and type_set == 0:
        return {"skipped": True, "reason": "nothing to migrate"}

    if not dry_run:
        store.save_locations(locations)

    return {
        "migrated": changed,
        "type_set": type_set,
        "dry_run": dry_run,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate _vehicle fields to hierarchy")
    parser.add_argument("--campaign", help="Campaign name (default: active campaign)")
    parser.add_argument("--all", action="store_true", help="Migrate all campaigns")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    campaigns_dir = PROJECT_ROOT / "world-state" / "campaigns"

    if args.all:
        targets = [d for d in campaigns_dir.iterdir() if d.is_dir()]
    elif args.campaign:
        from lib.campaign_context import resolve_campaign_dir

        try:
            targets = [
                resolve_campaign_dir(
                    campaigns_dir, args.campaign, must_exist=True
                )
            ]
        except (ValueError, FileNotFoundError) as exc:
            print(f"[ERROR] {exc}")
            sys.exit(1)
    else:
        from lib.campaign_context import scoped_campaign_name

        name = scoped_campaign_name(PROJECT_ROOT / "world-state")
        if not name:
            print("[ERROR] No active campaign and --campaign not specified")
            sys.exit(1)
        from lib.campaign_context import resolve_campaign_dir

        targets = [resolve_campaign_dir(campaigns_dir, name, must_exist=True)]

    for campaign_dir in targets:
        if not campaign_dir.exists():
            print(f"[ERROR] Campaign dir not found: {campaign_dir}")
            continue

        result = migrate_campaign(campaign_dir, dry_run=args.dry_run)

        if result.get("skipped"):
            print(f"{campaign_dir.name}: skipped — {result['reason']}")
        else:
            label = "[DRY-RUN] " if args.dry_run else ""
            print(
                f"{label}{campaign_dir.name}: "
                f"migrated={result['migrated']}, type_set={result['type_set']}"
            )


if __name__ == "__main__":
    main()
