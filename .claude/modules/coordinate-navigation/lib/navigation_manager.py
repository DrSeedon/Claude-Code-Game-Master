#!/usr/bin/env python3
"""
Navigation Manager — standalone module for coordinate-based navigation.

Handles coordinate calculations, bearing-based location creation, route analysis,
blocked directions. CORE location_manager.py handles basic location CRUD.

This module imports CORE's JsonOperations, connection_utils. CORE has zero knowledge of this module.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.json_ops import JsonOperations
from lib.connection_utils import (
    get_connections as cu_get_connections,
    get_connection_between,
    add_canonical_connection,
    remove_canonical_connection
)

MODULE_DIR = Path(__file__).parent
sys.path.insert(0, str(MODULE_DIR))

from pathfinding import PathFinder
from path_manager import PathManager


class NavigationManager:
    """Coordinate-based navigation operations."""

    def __init__(self, campaign_dir: str):
        self.json_ops = JsonOperations(campaign_dir)
        self.pf = PathFinder()
        self.path_manager = PathManager(campaign_dir)

    def add_location_with_coordinates(
        self,
        name: str,
        position: str,
        from_location: str,
        bearing: float,
        distance: float,
        terrain: str = "open"
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Calculate coordinates and add connection for a new location.

        Returns: (success, location_data or None)
        """
        locations = self.json_ops.load_json("locations.json")

        if from_location not in locations:
            return False, None

        from_coords = locations[from_location].get('coordinates')
        if not from_coords:
            return False, None

        new_coords = self.pf.calculate_coordinates(from_coords, distance, bearing)

        location_data = {
            'position': position,
            'connections': [],
            'description': '',
            'coordinates': new_coords,
            'blocked_ranges': []
        }

        add_canonical_connection(
            from_location, name, locations,
            path=f"{distance}m на {bearing}°",
            distance_meters=int(distance),
            bearing=bearing,
            terrain=terrain
        )

        direction, abbr = self.pf.bearing_to_compass(bearing)

        return True, {
            'location_data': location_data,
            'coordinates': new_coords,
            'direction': direction,
            'direction_abbr': abbr,
            'updated_locations': locations
        }

    def block_direction(
        self,
        location: str,
        from_deg: float,
        to_deg: float,
        reason: str
    ) -> bool:
        """Add blocked direction range to a location."""
        locations = self.json_ops.load_json("locations.json")

        if location not in locations:
            print(f"[ERROR] Location '{location}' not found")
            return False

        if 'blocked_ranges' not in locations[location]:
            locations[location]['blocked_ranges'] = []

        for block in locations[location]['blocked_ranges']:
            if (from_deg <= block['to'] and to_deg >= block['from']):
                print(f"[WARNING] Range overlaps with existing block: {block['from']}° - {block['to']}°")

        locations[location]['blocked_ranges'].append({
            'from': from_deg,
            'to': to_deg,
            'reason': reason
        })

        if self.json_ops.save_json("locations.json", locations):
            print(f"[SUCCESS] Blocked {from_deg}° - {to_deg}° at {location}: {reason}")
            return True
        return False

    def unblock_direction(
        self,
        location: str,
        from_deg: float,
        to_deg: float
    ) -> bool:
        """Remove blocked direction range from a location."""
        locations = self.json_ops.load_json("locations.json")

        if location not in locations:
            print(f"[ERROR] Location '{location}' not found")
            return False

        if 'blocked_ranges' not in locations[location]:
            print(f"[ERROR] No blocked ranges at {location}")
            return False

        original_count = len(locations[location]['blocked_ranges'])
        locations[location]['blocked_ranges'] = [
            block for block in locations[location]['blocked_ranges']
            if not (block['from'] == from_deg and block['to'] == to_deg)
        ]

        new_count = len(locations[location]['blocked_ranges'])
        if new_count == original_count:
            print(f"[ERROR] No matching blocked range found: {from_deg}° - {to_deg}°")
            return False

        if self.json_ops.save_json("locations.json", locations):
            print(f"[SUCCESS] Unblocked {from_deg}° - {to_deg}° at {location}")
            return True
        return False

    def decide_route(self, from_loc: str, to_loc: str) -> bool:
        """Interactive route decision."""
        import json

        suggestion = self.path_manager.suggest_navigation(from_loc, to_loc)

        if suggestion.get("method") == "error":
            print(f"[ERROR] {suggestion.get('message')}")
            return False

        if suggestion.get("method") != "needs_decision":
            cached = self.path_manager.get_cached_decision(from_loc, to_loc)
            if cached:
                print(f"[INFO] Decision already cached: {cached['decision']}")
                print(json.dumps(cached, indent=2, ensure_ascii=False))
                return True

        print("=" * 60)
        print(f"ROUTE DECISION: {from_loc} → {to_loc}")
        print("=" * 60)

        options = suggestion.get("options", {})

        print("\nAVAILABLE OPTIONS:\n")

        option_keys = []

        if "direct" in options:
            opt = options["direct"]
            option_keys.append("direct")
            print(f"[1] DIRECT PATH")
            print(f"    Distance: {opt['distance']}m")
            print(f"    Direction: {opt['direction']}")
            print(f"    Bearing: {opt['bearing']}°")
            print()

        if "use_route" in options:
            opt = options["use_route"]
            option_keys.append("use_route")
            print(f"[2] USE EXISTING ROUTE")
            print(f"    Path: {' → '.join(opt['route'])}")
            print(f"    Distance: {opt['distance']}m")
            print(f"    Hops: {opt['hops']}")
            print()

        if "blocked_reason" in options:
            print(f"[!] DIRECT PATH BLOCKED: {options['blocked_reason']}\n")

        print(f"[3] BLOCK THIS ROUTE (permanently)")
        option_keys.append("blocked")
        print()

        print("=" * 60)
        print("Enter choice [1-3]: ", end='', flush=True)

        try:
            choice = input().strip()
            choice_num = int(choice)

            if choice_num < 1 or choice_num > len(option_keys) + 1:
                print(f"[ERROR] Invalid choice: {choice}")
                return False

            if choice_num == len(option_keys) + 1:
                print("Enter reason for blocking: ", end='', flush=True)
                reason = input().strip()
                self.path_manager.cache_decision(from_loc, to_loc, "blocked", reason=reason)
                print(f"[SUCCESS] Route blocked: {reason}")
                return True

            decision = option_keys[choice_num - 1]

            if decision == "direct":
                self.path_manager.cache_decision(from_loc, to_loc, "direct")
                print(f"[SUCCESS] Cached decision: use direct path")

            elif decision == "use_route":
                route = options["use_route"]["route"]
                self.path_manager.cache_decision(from_loc, to_loc, "use_route", route=route)
                print(f"[SUCCESS] Cached decision: use route through {len(route)-2} locations")

            return True

        except (ValueError, KeyboardInterrupt, EOFError):
            print("\n[ERROR] Invalid input or cancelled")
            return False

    def show_routes(self, from_loc: str, to_loc: str) -> bool:
        """Show all possible routes between two locations."""
        import json

        analysis = self.path_manager.analyze_route_options(from_loc, to_loc)

        if analysis.get("error"):
            print(f"[ERROR] {analysis['error']}")
            return False

        print("=" * 60)
        print(f"ROUTES: {from_loc} → {to_loc}")
        print("=" * 60)
        print()

        cached = self.path_manager.get_cached_decision(from_loc, to_loc)
        if cached:
            print(f"CACHED DECISION: {cached['decision']}")
            if cached.get('reason'):
                print(f"  Reason: {cached['reason']}")
            if cached.get('route'):
                print(f"  Route: {' → '.join(cached['route'])}")
            print()

        if analysis.get("direct_distance"):
            print(f"DIRECT PATH:")
            print(f"  Distance: {analysis['direct_distance']}m")
            print(f"  Bearing: {analysis['direct_bearing']}°")

            direction, abbr = self.pf.bearing_to_compass(analysis['direct_bearing'])
            print(f"  Direction: {direction} ({abbr})")

            if analysis.get("direct_blocked"):
                print(f"  ⚠ BLOCKED: {analysis['blocked_reason']}")
            print()

        existing_routes = analysis.get("existing_routes", [])
        if existing_routes:
            print(f"EXISTING ROUTES ({len(existing_routes)}):")
            for i, route in enumerate(existing_routes, 1):
                print(f"\n  Route {i}:")
                print(f"    Path: {' → '.join(route['path'])}")
                print(f"    Distance: {route['distance']}m")
                print(f"    Hops: {route['hops']}")
                if route.get('terrains'):
                    terrains_str = ' → '.join(route['terrains'])
                    print(f"    Terrain: {terrains_str}")
        else:
            print("NO EXISTING ROUTES FOUND")

        print()
        print("=" * 60)
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Navigation Manager')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    add_parser = subparsers.add_parser('add', help='Add location with coordinates')
    add_parser.add_argument('campaign_dir', help='Campaign directory path')
    add_parser.add_argument('name', help='Location name')
    add_parser.add_argument('position', help='Relative position description')
    add_parser.add_argument('--from', dest='from_location', required=True, help='Origin location')
    add_parser.add_argument('--bearing', type=float, required=True, help='Direction in degrees (0=North)')
    add_parser.add_argument('--distance', type=float, required=True, help='Distance in meters')
    add_parser.add_argument('--terrain', default='open', help='Terrain type')

    decide_parser = subparsers.add_parser('decide', help='Decide route between locations')
    decide_parser.add_argument('campaign_dir', help='Campaign directory path')
    decide_parser.add_argument('from_loc', help='From location')
    decide_parser.add_argument('to_loc', help='To location')

    routes_parser = subparsers.add_parser('routes', help='Show all possible routes')
    routes_parser.add_argument('campaign_dir', help='Campaign directory path')
    routes_parser.add_argument('from_loc', help='From location')
    routes_parser.add_argument('to_loc', help='To location')

    block_parser = subparsers.add_parser('block', help='Block direction range')
    block_parser.add_argument('campaign_dir', help='Campaign directory path')
    block_parser.add_argument('location', help='Location name')
    block_parser.add_argument('from_deg', type=float, help='From bearing (degrees)')
    block_parser.add_argument('to_deg', type=float, help='To bearing (degrees)')
    block_parser.add_argument('reason', help='Reason for blocking')

    unblock_parser = subparsers.add_parser('unblock', help='Unblock direction range')
    unblock_parser.add_argument('campaign_dir', help='Campaign directory path')
    unblock_parser.add_argument('location', help='Location name')
    unblock_parser.add_argument('from_deg', type=float, help='From bearing (degrees)')
    unblock_parser.add_argument('to_deg', type=float, help='To bearing (degrees)')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = NavigationManager(args.campaign_dir)

    if args.action == 'add':
        locations = manager.json_ops.load_json("locations.json") or {}
        if args.name in locations:
            print(f"[ERROR] Location '{args.name}' already exists")
            sys.exit(1)

        success, result = manager.add_location_with_coordinates(
            args.name, args.position,
            args.from_location, args.bearing, args.distance, args.terrain
        )
        if not success:
            print(f"[ERROR] Failed to add location '{args.name}' (check origin location and coordinates)")
            sys.exit(1)

        updated_locations = result['updated_locations']
        updated_locations[args.name] = result['location_data']
        manager.json_ops.save_json("locations.json", updated_locations)

        print(f"[INFO] Calculated coordinates: {result['coordinates']}")
        print(f"[INFO] Direction from {args.from_location}: {result['direction']} ({result['direction_abbr']})")
        print(f"[INFO] Auto-created connection")
        print(f"[SUCCESS] Added location: {args.name} ({args.position})")

    elif args.action == 'decide':
        if not manager.decide_route(args.from_loc, args.to_loc):
            sys.exit(1)

    elif args.action == 'routes':
        if not manager.show_routes(args.from_loc, args.to_loc):
            sys.exit(1)

    elif args.action == 'block':
        if not manager.block_direction(args.location, args.from_deg, args.to_deg, args.reason):
            sys.exit(1)

    elif args.action == 'unblock':
        if not manager.unblock_direction(args.location, args.from_deg, args.to_deg):
            sys.exit(1)
