"""Game state cache for fast character status queries.

Uses WorldGraph to read data from world.json and caches results
to minimize disk operations during frequent requests (e.g. sidebar updates).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Add lib/ to path for world_graph import
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from world_graph import WorldGraph
except ImportError:
    WorldGraph = None


# Global character state cache
_character_cache: Optional[Dict] = None
_cache_timestamp: Optional[datetime] = None
_cache_ttl = timedelta(seconds=5)  # Cache valid for 5 seconds


def get_character_status(campaign_dir: Optional[Path] = None, force_refresh: bool = False) -> Dict:
    """Get current character status from world.json.

    Args:
        campaign_dir: Path to campaign directory (optional)
        force_refresh: Force cache refresh (ignore TTL)

    Returns:
        Dict with keys:
            - hp (int): Current health
            - max_hp (int): Maximum health
            - xp (int): Experience
            - gold (int): Gold (in base units - copper)
            - inventory (List[Dict]): Item list [{name, quantity}]
            - name (str): Character name
            - location (str): Current location (if exists)

        Or Dict with error key if error occurred:
            - error (str): Error description
    """
    global _character_cache, _cache_timestamp

    # Check cache
    if not force_refresh and _character_cache is not None and _cache_timestamp is not None:
        if datetime.now() - _cache_timestamp < _cache_ttl:
            return _character_cache

    # WorldGraph not available
    if WorldGraph is None:
        return {
            "error": "WorldGraph module not available"
        }

    try:
        # Initialize WorldGraph
        if campaign_dir:
            graph = WorldGraph(campaign_dir=campaign_dir)
        else:
            # Try to find active campaign
            try:
                graph = WorldGraph()
            except SystemExit:
                # _find_campaign_dir() calls sys.exit(1) when no active campaign
                return {
                    "error": "No active campaign found"
                }
            except Exception as e:
                return {
                    "error": f"Failed to initialize WorldGraph: {str(e)}"
                }

        # Find player node (first node of type "player")
        players = graph.list_nodes(node_type="player")
        if not players:
            return {
                "error": "No player character found in world.json"
            }

        # Take first player
        player = players[0]
        player_id = player.get("id")
        player_name = player.get("name", "Unknown")
        player_data = player.get("data", {})

        # Extract base stats (hp/xp can be objects)
        hp_raw = player_data.get("hp", 0)
        if isinstance(hp_raw, dict):
            hp = hp_raw.get("current", 0)
            max_hp = hp_raw.get("max", 0)
        else:
            hp = hp_raw
            max_hp = player_data.get("max_hp", hp)

        xp_raw = player_data.get("xp", 0)
        xp = xp_raw.get("current", 0) if isinstance(xp_raw, dict) else xp_raw

        gold = player_data.get("money", player_data.get("gold", 0))

        # Get inventory via "owns" edges
        inventory = []
        owned_edges = graph.get_edges(player_id, edge_type="owns", direction="out")

        for edge in owned_edges:
            item_id = edge.get("to")
            item_node = graph.get_node(item_id)
            if item_node:
                item_name = item_node.get("name", item_id)
                # Quantity can be stored in edge data or node
                quantity = edge.get("data", {}).get("quantity", 1)
                if "quantity" in item_node.get("data", {}):
                    quantity = item_node["data"]["quantity"]

                inventory.append({
                    "name": item_name,
                    "quantity": quantity
                })

        # Get current location via "at" edges
        location = None
        location_edges = graph.get_edges(player_id, edge_type="at", direction="out")
        if location_edges:
            location_id = location_edges[0].get("to")
            location_node = graph.get_node(location_id)
            if location_node:
                location = location_node.get("name", location_id)

        # Build result
        result = {
            "name": player_name,
            "hp": hp,
            "max_hp": max_hp,
            "xp": xp,
            "gold": gold,
            "inventory": inventory
        }

        if location:
            result["location"] = location

        # Save to cache
        _character_cache = result
        _cache_timestamp = datetime.now()

        return result

    except Exception as e:
        return {
            "error": f"Failed to get character status: {str(e)}"
        }


def invalidate_cache() -> None:
    """Invalidate character state cache.

    Called after executing tools that modify character state
    (HP changes, add/remove items, gain XP, spend gold).
    """
    global _character_cache, _cache_timestamp
    _character_cache = None
    _cache_timestamp = None


def get_inventory(campaign_dir: Optional[Path] = None) -> List[Dict]:
    """Get only character inventory.

    Args:
        campaign_dir: Path to campaign directory (optional)

    Returns:
        List[Dict]: Item list [{name, quantity}] or empty list on error
    """
    status = get_character_status(campaign_dir=campaign_dir)
    return status.get("inventory", [])


def get_player_stats(campaign_dir: Optional[Path] = None) -> Dict:
    """Get only base character stats (without inventory).

    Args:
        campaign_dir: Path to campaign directory (optional)

    Returns:
        Dict with keys: name, hp, max_hp, xp, gold, location (if exists)
    """
    status = get_character_status(campaign_dir=campaign_dir)

    # Remove inventory from result
    result = {k: v for k, v in status.items() if k != "inventory"}

    return result
