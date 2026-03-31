#!/usr/bin/env python3
"""
Tool registry for DM web interface
Maps all lib/ modules as Anthropic tool schemas
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from dice import DiceRoller, format_enhanced
from world_graph import WorldGraph
from player_manager import PlayerManager
from session_manager import SessionManager


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Return all tool schemas for Anthropic API
    Each schema defines a game operation that the DM can perform
    """
    return [
        {
            "name": "roll_dice",
            "description": "Roll dice with modifiers, advantage/disadvantage, and difficulty checks. Supports standard notation (1d20+5), advantage (2d20kh1), disadvantage (2d20kl1). Can auto-lookup skills, saves, and attacks from character sheet.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "notation": {
                        "type": "string",
                        "description": "Dice notation (e.g. '1d20+5', '3d6', '2d20kh1+3')"
                    },
                    "label": {
                        "type": "string",
                        "description": "Description of what the roll is for (e.g. 'Perception check', 'Attack with longsword')"
                    },
                    "dc": {
                        "type": "integer",
                        "description": "Difficulty Class to check against (success if roll >= DC)"
                    },
                    "ac": {
                        "type": "integer",
                        "description": "Armor Class to check against (hit if roll >= AC)"
                    },
                    "skill": {
                        "type": "string",
                        "description": "Skill name to auto-lookup modifier from character sheet (e.g. 'perception', 'stealth')"
                    },
                    "save": {
                        "type": "string",
                        "description": "Saving throw name: str/dex/con/int/wis/cha"
                    },
                    "attack": {
                        "type": "string",
                        "description": "Weapon name for attack roll (auto-lookup from equipped weapons)"
                    },
                    "advantage": {
                        "type": "boolean",
                        "description": "Roll with advantage (keep highest of 2d20)"
                    },
                    "disadvantage": {
                        "type": "boolean",
                        "description": "Roll with disadvantage (keep lowest of 2d20)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "inventory_show",
            "description": "Display character or party member inventory with items, weights, and encumbrance status",
            "input_schema": {
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player). Use '_auto' for current player."
                    }
                },
                "required": []
            }
        },
        {
            "name": "inventory_add",
            "description": "Add item to character inventory",
            "input_schema": {
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player)"
                    },
                    "item": {
                        "type": "string",
                        "description": "Item name"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items to add (default: 1)"
                    },
                    "weight": {
                        "type": "number",
                        "description": "Weight per item in kg (default: auto-detect from category)"
                    }
                },
                "required": ["item"]
            }
        },
        {
            "name": "inventory_remove",
            "description": "Remove item from character inventory (for selling, destroying, or consuming)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player)"
                    },
                    "item": {
                        "type": "string",
                        "description": "Item name"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items to remove (default: 1)"
                    }
                },
                "required": ["item"]
            }
        },
        {
            "name": "player_award_xp",
            "description": "Award XP to player character. Automatically checks for level up and updates character sheet.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "XP amount to award (can be negative for penalties)"
                    },
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player)"
                    }
                },
                "required": ["amount"]
            }
        },
        {
            "name": "player_update_hp",
            "description": "Update player HP (damage or healing). Prevents HP from going below 0 or above max.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "change": {
                        "type": "integer",
                        "description": "HP change (positive for healing, negative for damage)"
                    },
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player)"
                    }
                },
                "required": ["change"]
            }
        },
        {
            "name": "player_update_gold",
            "description": "Update player gold/currency (gains or expenses)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "change": {
                        "type": "integer",
                        "description": "Gold change (positive for gains, negative for expenses)"
                    },
                    "character": {
                        "type": "string",
                        "description": "Character name (default: active player)"
                    }
                },
                "required": ["change"]
            }
        },
        {
            "name": "session_move",
            "description": "Move party to a new location. Auto-creates location if it doesn't exist and establishes connections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Destination location name"
                    },
                    "elapsed_hours": {
                        "type": "number",
                        "description": "Travel time in hours (triggers time advancement and consequences)"
                    }
                },
                "required": ["location"]
            }
        },
        {
            "name": "npc_add",
            "description": "Add or update NPC in world",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "NPC name"
                    },
                    "description": {
                        "type": "string",
                        "description": "NPC description and personality"
                    },
                    "location": {
                        "type": "string",
                        "description": "Current location of NPC"
                    },
                    "attitude": {
                        "type": "string",
                        "description": "Attitude toward party: friendly, neutral, hostile, unknown"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "location_add",
            "description": "Add or update location in world",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Location name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Location description"
                    },
                    "type": {
                        "type": "string",
                        "description": "Location type: city, village, dungeon, wilderness, building"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "note_add",
            "description": "Add world fact or lore note",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Fact content"
                    },
                    "category": {
                        "type": "string",
                        "description": "Fact category: lore, rumor, clue, quest, rule"
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "time_advance",
            "description": "Advance game time by specified hours. Auto-triggers timed consequences and recurring events.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "number",
                        "description": "Hours to advance (can be fractional, e.g. 0.5 for 30 minutes)"
                    },
                    "sleeping": {
                        "type": "boolean",
                        "description": "Whether the party is sleeping (affects HP regeneration)"
                    }
                },
                "required": ["hours"]
            }
        }
    ]


def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a game tool and return result

    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters from Claude

    Returns:
        Dict with execution result and any output
    """
    try:
        if tool_name == "roll_dice":
            return _execute_roll_dice(params)
        elif tool_name == "inventory_show":
            return _execute_inventory_show(params)
        elif tool_name == "inventory_add":
            return _execute_inventory_add(params)
        elif tool_name == "inventory_remove":
            return _execute_inventory_remove(params)
        elif tool_name == "player_award_xp":
            return _execute_player_award_xp(params)
        elif tool_name == "player_update_hp":
            return _execute_player_update_hp(params)
        elif tool_name == "player_update_gold":
            return _execute_player_update_gold(params)
        elif tool_name == "session_move":
            return _execute_session_move(params)
        elif tool_name == "npc_add":
            return _execute_npc_add(params)
        elif tool_name == "location_add":
            return _execute_location_add(params)
        elif tool_name == "note_add":
            return _execute_note_add(params)
        elif tool_name == "time_advance":
            return _execute_time_advance(params)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool execution failed: {str(e)}"
        }


def _execute_roll_dice(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute dice roll with all modifiers and checks"""
    try:
        roller = DiceRoller()

        notation = params.get("notation")
        label = params.get("label")
        dc = params.get("dc")
        ac = params.get("ac")

        # Handle advantage/disadvantage
        if params.get("advantage") and notation and "kh" not in notation:
            if "d20" in notation:
                notation = notation.replace("1d20", "2d20kh1")
        if params.get("disadvantage") and notation and "kl" not in notation:
            if "d20" in notation:
                notation = notation.replace("1d20", "2d20kl1")

        # For skill/save/attack, we need to call the CLI since it has character lookup
        if params.get("skill") or params.get("save") or params.get("attack"):
            args = []
            if params.get("skill"):
                args.extend(["--skill", params["skill"]])
            if params.get("save"):
                args.extend(["--save", params["save"]])
            if params.get("attack"):
                args.extend(["--attack", params["attack"]])
            if label:
                args.extend(["--label", label])
            if dc:
                args.extend(["--dc", str(dc)])
            if ac:
                args.extend(["--ac", str(ac)])
            if params.get("advantage"):
                args.append("--advantage")
            if params.get("disadvantage"):
                args.append("--disadvantage")

            result = subprocess.run(
                ["uv", "run", "python", "lib/dice.py"] + args,
                capture_output=True,
                text=True,
                check=True
            )
            return {
                "success": True,
                "output": result.stdout.strip()
            }

        # Simple roll
        if not notation:
            return {"success": False, "error": "No dice notation provided"}

        roll_result = roller.roll(notation)
        formatted = format_enhanced(roll_result, label=label, dc=dc, ac=ac)

        return {
            "success": True,
            "total": roll_result["total"],
            "rolls": roll_result["rolls"],
            "output": formatted
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_inventory_show(params: Dict[str, Any]) -> Dict[str, Any]:
    """Show character inventory"""
    character = params.get("character", "_auto")

    result = subprocess.run(
        ["bash", "tools/dm-inventory.sh", "show", character],
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_inventory_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add item to inventory"""
    character = params.get("character", "_auto")
    item = params["item"]
    qty = params.get("quantity", 1)
    weight = params.get("weight")

    args = ["bash", "tools/dm-inventory.sh", "update", character, "--add", item, str(qty)]
    if weight is not None:
        args.append(str(weight))
    else:
        args.append("0.5")

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_inventory_remove(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove item from inventory"""
    character = params.get("character", "_auto")
    item = params["item"]
    qty = params.get("quantity", 1)

    result = subprocess.run(
        ["bash", "tools/dm-inventory.sh", "remove", character, item, "--qty", str(qty)],
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_player_award_xp(params: Dict[str, Any]) -> Dict[str, Any]:
    """Award XP to player"""
    amount = params["amount"]
    character = params.get("character")

    args = ["bash", "tools/dm-player.sh", "xp", str(amount)]
    if character:
        args.extend(["--name", character])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_player_update_hp(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update player HP"""
    change = params["change"]
    character = params.get("character")

    args = ["bash", "tools/dm-player.sh", "hp", str(change)]
    if character:
        args.extend(["--name", character])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_player_update_gold(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update player gold"""
    change = params["change"]
    character = params.get("character")

    args = ["bash", "tools/dm-player.sh", "gold", str(change)]
    if character:
        args.extend(["--name", character])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_session_move(params: Dict[str, Any]) -> Dict[str, Any]:
    """Move party to new location"""
    location = params["location"]
    elapsed_hours = params.get("elapsed_hours")

    args = ["bash", "tools/dm-session.sh", "move", location]
    if elapsed_hours is not None:
        args.extend(["--elapsed", str(elapsed_hours)])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_npc_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update NPC"""
    name = params["name"]
    description = params.get("description", "")
    location = params.get("location")
    attitude = params.get("attitude")

    args = ["bash", "tools/dm-npc.sh", "add", name]
    if description:
        args.extend(["--description", description])
    if location:
        args.extend(["--location", location])
    if attitude:
        args.extend(["--attitude", attitude])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_location_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update location"""
    name = params["name"]
    description = params.get("description", "")
    loc_type = params.get("type", "unknown")

    args = ["bash", "tools/dm-location.sh", "add", name]
    if description:
        args.extend(["--description", description])
    if loc_type:
        args.extend(["--type", loc_type])

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_note_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add world fact/note"""
    content = params["content"]
    category = params.get("category", "lore")

    result = subprocess.run(
        ["bash", "tools/dm-note.sh", "add", content, "--category", category],
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


def _execute_time_advance(params: Dict[str, Any]) -> Dict[str, Any]:
    """Advance game time"""
    hours = params["hours"]
    sleeping = params.get("sleeping", False)

    args = ["bash", "tools/dm-time.sh", "current", "current", "--elapsed", str(hours)]
    if sleeping:
        args.append("--sleeping")

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    }


if __name__ == "__main__":
    # Test: print all tool schemas
    import json
    schemas = get_tool_schemas()
    print(f"Registered {len(schemas)} tools:")
    for schema in schemas:
        print(f"  - {schema['name']}: {schema['description'][:60]}...")
