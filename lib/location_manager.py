#!/usr/bin/env python3
"""
Location management module for DM tools
Handles location creation, connections, and descriptions
"""

import sys
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from connection_utils import get_connections as cu_get_connections, get_connection_between, add_canonical_connection


class LocationManager(EntityManager):
    """Manage location operations. Inherits from EntityManager for common functionality."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)
        self.locations_file = "locations.json"

    def add_location(self, name: str, position: str) -> bool:
        """
        Add a new location (simple CRUD).
        For coordinate-based creation, use coordinate-navigation module.
        """
        valid, error = self.validators.validate_name(name)
        if not valid:
            print(f"[ERROR] {error}")
            return False

        if self._entity_exists(self.locations_file, name):
            print(f"[ERROR] Location '{name}' already exists")
            return False

        location_data = {
            'position': position,
            'connections': [],
            'description': '',
            'discovered': self.get_timestamp()
        }

        if self._add_entity(self.locations_file, name, location_data):
            print(f"[SUCCESS] Added location: {name} ({position})")
            return True
        return False

    def connect_locations(self, from_loc: str, to_loc: str, path: str,
                         terrain: str = None, distance: float = None) -> bool:
        """
        Connect two locations canonically
        """
        for loc in [from_loc, to_loc]:
            valid, error = self.validators.validate_name(loc)
            if not valid:
                print(f"[ERROR] {error}")
                return False

        locations = self._load_entities(self.locations_file)

        if from_loc not in locations:
            print(f"[ERROR] Location '{from_loc}' not found")
            return False
        if to_loc not in locations:
            print(f"[ERROR] Location '{to_loc}' not found")
            return False

        if get_connection_between(from_loc, to_loc, locations) is not None:
            print(f"[ERROR] Connection already exists between '{from_loc}' and '{to_loc}'")
            return False

        kwargs = {'path': path}
        if terrain:
            kwargs['terrain'] = terrain
        if distance:
            kwargs['distance_meters'] = int(distance)

        add_canonical_connection(from_loc, to_loc, locations, **kwargs)

        if self._save_entities(self.locations_file, locations):
            print(f"[SUCCESS] Connected {from_loc} <-> {to_loc} via {path}")
            return True
        return False

    def set_description(self, name: str, description: str) -> bool:
        """
        Set or update location description
        """
        # Validate name
        valid, error = self.validators.validate_name(name)
        if not valid:
            print(f"[ERROR] {error}")
            return False

        # Check if location exists
        if not self._entity_exists(self.locations_file, name):
            print(f"[ERROR] Location '{name}' not found")
            return False

        # Update description
        if self._update_entity(self.locations_file, name, {'description': description}):
            print(f"[SUCCESS] Updated description for {name}")
            return True
        return False

    def get_location(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get location data
        """
        valid, error = self.validators.validate_name(name)
        if not valid:
            print(f"[ERROR] {error}")
            return None

        location = self._get_entity(self.locations_file, name)
        if not location:
            print(f"[ERROR] Location '{name}' not found")
            return None

        return location

    def list_locations(self) -> List[str]:
        """
        List all location names
        """
        locations = self._load_entities(self.locations_file)
        return list(locations.keys())

    def get_connections(self, name: str) -> List[Dict[str, str]]:
        """
        Get connections for a location
        """
        locations = self._load_entities(self.locations_file)
        return cu_get_connections(name, locations)


    def create_batch(self, locations_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create multiple locations in batch

        Args:
            locations_data: List of location dictionaries with name, description, position, etc.

        Returns:
            List of results for each location with success/error status
        """
        results = []
        locations = self._load_entities(self.locations_file)

        for loc_data in locations_data:
            result = {'name': loc_data.get('name', 'Unknown')}

            # Validate required fields
            if not loc_data.get('name'):
                result['success'] = False
                result['error'] = 'Missing location name'
                results.append(result)
                continue

            name = loc_data['name']

            # Check for duplicates
            if name in locations:
                result['success'] = False
                result['error'] = f'Location {name} already exists'
                results.append(result)
                continue

            # Create location entry
            location_entry = {
                'position': loc_data.get('position', 'unknown'),
                'description': loc_data.get('description', ''),
                'connections': [],
                'discovered': self.get_timestamp()
            }

            # Add source if provided
            if loc_data.get('source'):
                location_entry['source'] = loc_data['source']

            # Process connections if provided
            if loc_data.get('connections'):
                for conn_name in loc_data['connections']:
                    if conn_name in locations:
                        add_canonical_connection(name, conn_name, locations, path='connected')

            # Add notes if provided
            if loc_data.get('notes'):
                location_entry['notes'] = loc_data['notes']

            # Add to locations dictionary (pending save)
            locations[name] = location_entry
            result['_pending'] = True
            results.append(result)

        # Save all locations at once, then mark success/failure
        pending = [r for r in results if r.get('_pending')]
        if pending:
            saved = self._save_entities(self.locations_file, locations)
            for result in pending:
                del result['_pending']
                if saved:
                    result['success'] = True
                else:
                    result['success'] = False
                    result['error'] = 'Failed to save to file'

        return results


def main():
    """CLI interface for location management"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Location management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Add location
    add_parser = subparsers.add_parser('add', help='Add new location')
    add_parser.add_argument('name', help='Location name')
    add_parser.add_argument('position', help='Relative position')

    # Connect locations
    connect_parser = subparsers.add_parser('connect', help='Connect two locations')
    connect_parser.add_argument('from_loc', help='From location')
    connect_parser.add_argument('to_loc', help='To location')
    connect_parser.add_argument('path', nargs='?', default='connected', help='Path description')
    connect_parser.add_argument('--terrain', help='Terrain type')
    connect_parser.add_argument('--distance', type=float, help='Distance in meters')

    # Describe location
    describe_parser = subparsers.add_parser('describe', help='Set location description')
    describe_parser.add_argument('name', help='Location name')
    describe_parser.add_argument('description', help='Description text')

    # Get location
    get_parser = subparsers.add_parser('get', help='Get location info')
    get_parser.add_argument('name', help='Location name')

    # List locations
    subparsers.add_parser('list', help='List all locations')

    # Get connections
    connections_parser = subparsers.add_parser('connections', help='Get location connections')
    connections_parser.add_argument('name', help='Location name')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = LocationManager()

    if args.action == 'add':
        if not manager.add_location(args.name, args.position):
            sys.exit(1)

    elif args.action == 'connect':
        if not manager.connect_locations(args.from_loc, args.to_loc, args.path,
                                         terrain=args.terrain, distance=args.distance):
            sys.exit(1)

    elif args.action == 'describe':
        if not manager.set_description(args.name, args.description):
            sys.exit(1)

    elif args.action == 'get':
        location = manager.get_location(args.name)
        if location:
            print(json.dumps({args.name: location}, indent=2, ensure_ascii=False))
        else:
            sys.exit(1)

    elif args.action == 'list':
        locations = manager.list_locations()
        if locations:
            for loc in locations:
                print(f"  - {loc}")
        else:
            print("No locations found")

    elif args.action == 'connections':
        connections = manager.get_connections(args.name)
        if connections:
            print(json.dumps(connections, indent=2, ensure_ascii=False))
        else:
            print("No connections found")



if __name__ == "__main__":
    main()
