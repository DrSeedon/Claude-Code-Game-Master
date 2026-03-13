#!/usr/bin/env python3
"""
Canonical connection utilities for location graph management.
Each edge is stored ONCE in the alphabetically-first location.
All modules should use these helpers instead of raw connection access.
"""

from typing import Dict, List, Optional, Tuple, Any


def canonical_pair(a: str, b: str) -> Tuple[str, str]:
    """Return (first, second) in alphabetical order."""
    if a <= b:
        return (a, b)
    return (b, a)


def get_connections(loc_name: str, locations_data: Dict) -> List[Dict]:
    """
    Get ALL connections for a location — both forward (stored here)
    and reverse (stored in other locations pointing to us).

    Reverse connections get bearing flipped by +180.
    Deduplicates by target name — forward connection takes priority.
    """
    result = []
    seen_targets = set()

    if loc_name not in locations_data:
        return result

    loc = locations_data[loc_name]
    for conn in loc.get('connections', []):
        result.append(dict(conn))
        seen_targets.add(conn.get('to'))

    for other_name, other_data in locations_data.items():
        if other_name == loc_name or other_name in seen_targets:
            continue
        for conn in other_data.get('connections', []):
            if conn.get('to') == loc_name:
                reverse = dict(conn)
                reverse['to'] = other_name
                if 'bearing' in reverse and reverse['bearing'] is not None:
                    reverse['bearing'] = (reverse['bearing'] + 180) % 360
                result.append(reverse)
                seen_targets.add(other_name)

    return result


def get_connection_between(a: str, b: str, locations_data: Dict) -> Optional[Dict]:
    """
    Get connection data between two locations (regardless of storage direction).
    Returns the raw stored dict (with original bearing from owner to target).
    Returns None if no connection exists.
    """
    first, second = canonical_pair(a, b)

    if first in locations_data:
        for conn in locations_data[first].get('connections', []):
            if conn.get('to') == second:
                return conn

    if second in locations_data:
        for conn in locations_data[second].get('connections', []):
            if conn.get('to') == first:
                return conn

    return None


def _segment_intersects_circle(x1, y1, x2, y2, cx, cy, cr) -> bool:
    import math
    dx, dy = x2 - x1, y2 - y1
    fx, fy = x1 - cx, y1 - cy
    a = dx * dx + dy * dy
    if a < 1e-6:
        return False
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - cr * cr
    disc = b * b - 4 * a * c
    if disc < 0:
        return False
    disc_sq = math.sqrt(disc)
    t1 = (-b - disc_sq) / (2 * a)
    t2 = (-b + disc_sq) / (2 * a)
    return t1 < 1.0 and t2 > 0.0


def validate_connection(a: str, b: str, locations_data: Dict) -> List[str]:
    """
    Check if a direct connection A→B passes through any other location's radius.
    Returns list of location names that block the path. Empty = path is clear.
    """
    coords_a = locations_data.get(a, {}).get('coordinates')
    coords_b = locations_data.get(b, {}).get('coordinates')
    if not coords_a or not coords_b:
        return []

    blockers = []
    for name, data in locations_data.items():
        if name in (a, b):
            continue
        coords = data.get('coordinates')
        if not coords:
            continue
        if data.get('parent'):
            continue
        r = data.get('diameter_meters', 100) / 2
        if _segment_intersects_circle(
            coords_a['x'], coords_a['y'], coords_b['x'], coords_b['y'],
            coords['x'], coords['y'], r
        ):
            blockers.append(name)
    return blockers


def add_canonical_connection(a: str, b: str, locations_data: Dict, force: bool = False, **kwargs) -> bool:
    """
    Add connection between a and b, stored in alphabetically-first location.
    kwargs: path, distance_meters, bearing, terrain, etc.

    bearing should be from the owner (first) to the target (second).
    If a > b (caller provides bearing from a to b), we flip it.

    Blocks creation if the path passes through another location's radius.
    Use force=True to override.
    Returns True if connection was added, False if blocked.
    """
    first, second = canonical_pair(a, b)

    if first not in locations_data or second not in locations_data:
        return False

    if 'connections' not in locations_data[first]:
        locations_data[first]['connections'] = []

    for conn in locations_data[first]['connections']:
        if conn.get('to') == second:
            return False

    blockers = validate_connection(a, b, locations_data)
    if blockers and not force:
        import sys
        print(f"⚠️  WARNING: Direct path {a} → {b} passes through: {', '.join(blockers)}", file=sys.stderr)
        print(f"   Connection NOT created. Route through intermediate locations instead.", file=sys.stderr)
        print(f"   Use --force to override.", file=sys.stderr)
        return False

    conn_data = {'to': second}
    conn_data.update(kwargs)

    if a != first and 'bearing' in conn_data and conn_data['bearing'] is not None:
        conn_data['bearing'] = (conn_data['bearing'] + 180) % 360

    locations_data[first]['connections'].append(conn_data)
    return True


def remove_canonical_connection(a: str, b: str, locations_data: Dict) -> None:
    """Remove connection between a and b from wherever it's stored."""
    first, second = canonical_pair(a, b)

    if first in locations_data:
        conns = locations_data[first].get('connections', [])
        locations_data[first]['connections'] = [
            c for c in conns if c.get('to') != second
        ]

    if second in locations_data:
        conns = locations_data[second].get('connections', [])
        locations_data[second]['connections'] = [
            c for c in conns if c.get('to') != first
        ]


def get_unique_edges(locations_data: Dict) -> List[Tuple[str, str, Dict]]:
    """
    Get all unique edges for map rendering — no duplicates.
    Returns list of (loc_a, loc_b, connection_data) tuples.
    """
    seen = set()
    edges = []

    for loc_name, loc_data in locations_data.items():
        for conn in loc_data.get('connections', []):
            to_loc = conn.get('to')
            if not to_loc:
                continue
            edge_key = tuple(sorted([loc_name, to_loc]))
            if edge_key not in seen:
                seen.add(edge_key)
                edges.append((loc_name, to_loc, conn))

    return edges
