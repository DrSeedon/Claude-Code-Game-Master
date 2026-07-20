"""Compile wizard creation rules and persist a complete campaign blueprint."""

from __future__ import annotations

import json
import re
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable

from backend.campaign_templates import get_campaign_template
from backend.config import get_project_root
from lib.json_ops import JsonOperations
from lib.module_data import ModuleDataManager
from lib.world_graph import EDGE_TYPES, NODE_TYPES, WorldGraph


MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CORE_CREATION_RULES = (
    ".claude/commands/new-game.md",
    ".claude/commands/create-character.md",
)


class CampaignSetupError(ValueError):
    """Raised when a wizard blueprint is incomplete or internally inconsistent."""


CAMPAIGN_SETUP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Complete playable campaign blueprint. Gameplay entities belong in nodes "
        "and edges; campaign metadata belongs in overview; optional module config "
        "belongs in module_data."
    ),
    "properties": {
        "starting_location_id": {
            "type": "string",
            "description": "ID of the starting location node.",
        },
        "overview": {
            "type": "object",
            "description": (
                "Metadata overrides including current_date, precise_time, "
                "time_of_day, currency, and calendar."
            ),
            "additionalProperties": True,
        },
        "player": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Complete character sheet. ALL listed properties are mandatory.",
                    "properties": {
                        "race": {"type": "string"},
                        "class": {"type": "string"},
                        "background": {"type": "string"},
                        "level": {"type": "integer", "minimum": 1},
                        "hp": {
                            "type": "object",
                            "properties": {
                                "current": {"type": "number"},
                                "max": {"type": "number"},
                            },
                            "required": ["current", "max"],
                        },
                        "ac": {"type": "number", "minimum": 1},
                        "stats": {
                            "type": "object",
                            "description": "Ability scores: str, dex, con, int, wis, cha (all positive numbers).",
                            "properties": {
                                "str": {"type": "number"},
                                "dex": {"type": "number"},
                                "con": {"type": "number"},
                                "int": {"type": "number"},
                                "wis": {"type": "number"},
                                "cha": {"type": "number"},
                            },
                            "required": ["str", "dex", "con", "int", "wis", "cha"],
                        },
                        "skills": {
                            "type": "object",
                            "description": "Skill name → modifier mapping. At least one entry.",
                        },
                        "saves": {
                            "type": "object",
                            "description": "Saving throw modifiers: str, dex, con, int, wis, cha.",
                            "properties": {
                                "str": {"type": "number"},
                                "dex": {"type": "number"},
                                "con": {"type": "number"},
                                "int": {"type": "number"},
                                "wis": {"type": "number"},
                                "cha": {"type": "number"},
                            },
                            "required": ["str", "dex", "con", "int", "wis", "cha"],
                        },
                        "save_proficiencies": {
                            "type": "array",
                            "description": "List of ability names the character is proficient in for saves.",
                            "items": {"type": "string"},
                        },
                        "proficiency_bonus": {"type": "number"},
                        "xp": {
                            "type": "object",
                            "properties": {
                                "current": {"type": "number", "minimum": 0},
                                "next_level": {"type": "number", "minimum": 1},
                            },
                            "required": ["current", "next_level"],
                        },
                        "money": {
                            "type": "number",
                            "description": "Currency in base units (e.g. copper pieces, credits).",
                        },
                        "conditions": {
                            "type": "array",
                            "description": "Active conditions. Usually empty at start.",
                            "items": {"type": "string"},
                        },
                        "features": {
                            "type": "array",
                            "description": "Class/racial features. At least one entry.",
                            "items": {"type": "string"},
                        },
                        "equipment": {
                            "type": "object",
                            "description": "Equipment slots → item name. E.g. {\"weapons\": [...], \"armor\": \"...\"}. At least one entry.",
                        },
                    },
                    "required": [
                        "race", "class", "background", "level",
                        "hp", "ac", "stats", "skills", "saves",
                        "save_proficiencies", "proficiency_bonus",
                        "xp", "money", "conditions", "features", "equipment",
                    ],
                    "additionalProperties": True,
                },
                "inventory": {
                    "type": "object",
                    "properties": {
                        "stackable": {"type": "object"},
                        "unique": {"type": "array"},
                    },
                    "required": ["stackable", "unique"],
                    "additionalProperties": False,
                },
            },
            "required": ["data", "inventory"],
            "additionalProperties": False,
        },
        "nodes": {
            "type": "array",
            "description": (
                "All non-player WorldGraph nodes. Include locations, six NPCs, "
                "three quests, three consequences, misc:economy, and module "
                "reference nodes required by loaded creation rules. "
                "Node IDs must be 'type:kebab-id'. Required data fields by type: "
                "location needs 'description'; "
                "npc needs 'description' and 'attitude' (friendly/neutral/hostile); "
                "quest needs 'description', 'status' (active/completed/failed), and "
                "'objectives' (array of {name, completed}); "
                "consequence needs 'description', 'trigger' (what activates it), "
                "and 'status' (pending/triggered/resolved). "
                "misc:economy needs 'expenses', 'income', 'production', 'random_events'."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": NODE_TYPES},
                    "name": {"type": "string"},
                    "data": {"type": "object"},
                    "inventory": {"type": "object"},
                },
                "required": ["id", "type", "name", "data"],
                "additionalProperties": False,
            },
        },
        "edges": {
            "type": "array",
            "description": (
                "Typed WorldGraph edges. Connect every location and place every "
                "NPC with an at edge."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "type": {"type": "string", "enum": EDGE_TYPES},
                    "data": {"type": "object"},
                },
                "required": ["from", "to", "type"],
                "additionalProperties": False,
            },
        },
        "module_data": {
            "type": "object",
            "description": (
                "Map of selected module ID to that module's campaign config. "
                "Never include unselected modules."
            ),
            "additionalProperties": {"type": "object"},
        },
        "session_zero": {
            "type": "string",
            "description": "Session 0 summary with the premise, starting cast, and hooks.",
        },
    },
    "required": [
        "starting_location_id",
        "overview",
        "player",
        "nodes",
        "edges",
        "module_data",
        "session_zero",
    ],
    "additionalProperties": False,
}


def _module_manifest(project_root: Path, module_id: str) -> dict[str, Any]:
    if not MODULE_ID_RE.fullmatch(module_id):
        raise CampaignSetupError(f"Invalid module id: {module_id!r}")
    path = project_root / "modules" / module_id / "module.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CampaignSetupError(f"Module '{module_id}' is not installed") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignSetupError(
            f"Module '{module_id}' has an unreadable manifest"
        ) from exc
    if manifest.get("id") != module_id:
        raise CampaignSetupError(f"Module manifest id mismatch for '{module_id}'")
    return manifest


def _selected_manifests(
    project_root: Path,
    module_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for raw_id in module_ids:
        module_id = str(raw_id).strip()
        if module_id and module_id not in selected:
            selected[module_id] = _module_manifest(project_root, module_id)
    return selected


def load_creation_context(
    module_ids: Iterable[str],
    template_id: str = "",
    project_root: Path | None = None,
) -> str:
    """Return CORE, character, template, and selected-module creation rules."""
    root = Path(project_root or get_project_root())
    manifests = _selected_manifests(root, module_ids)
    sections = [
        "# Compiled Campaign Creation Context",
        "",
        (
            "Follow every applicable requirement below. CORE rules always apply. "
            "Optional module rules augment CORE and only appear for selected modules."
        ),
    ]

    for relative_path in CORE_CREATION_RULES:
        path = root / relative_path
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CampaignSetupError(
                f"Required CORE creation rules are unavailable: {relative_path}"
            ) from exc
        sections.extend(["", f"## CORE source: `{relative_path}`", "", text])

    if template_id:
        template = get_campaign_template(template_id, root)
        if not template:
            raise CampaignSetupError(
                f"Campaign template '{template_id}' was not found"
            )
        sections.extend(
            [
                "",
                f"## Selected campaign template: `{template_id}`",
                "",
                "```json",
                json.dumps(template, ensure_ascii=False, indent=2),
                "```",
            ]
        )

    if manifests:
        sections.extend(["", "## Selected module creation rules"])
    else:
        sections.extend(
            [
                "",
                "## Selected module creation rules",
                "",
                "No optional gameplay modules are selected. Use vanilla CORE rules.",
            ]
        )

    for module_id in manifests:
        path = root / "modules" / module_id / "creation-rules.md"
        try:
            text = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            text = (
                "This module has no additional campaign-creation questions or "
                "persistent setup requirements."
            )
        except OSError as exc:
            raise CampaignSetupError(
                f"Creation rules for module '{module_id}' are unreadable"
            ) from exc
        contract = manifests[module_id].get("creation_contract", {})
        sections.extend(
            [
                "",
                f"### Module `{module_id}`",
                "",
                "#### Backend-enforced creation contract",
                "",
                "```json",
                json.dumps(contract, ensure_ascii=False, indent=2),
                "```",
                "",
                "#### Guided creation rules",
                "",
                text,
            ]
        )

    return "\n".join(sections).strip() + "\n"


def _nested_value(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _node_matches(node: dict[str, Any], requirement: dict[str, Any]) -> bool:
    if requirement.get("type") and node.get("type") != requirement["type"]:
        return False
    data = node.get("data", {})
    for key, expected in requirement.get("data_matches", {}).items():
        if _nested_value(data, key) != expected:
            return False
    return all(
        _nested_value(data, field) is not None
        for field in requirement.get("data_fields", [])
    )


def _validate_player(player: dict[str, Any]) -> None:
    data = player.get("data")
    inventory = player.get("inventory")
    if not isinstance(data, dict):
        raise CampaignSetupError("setup.player.data must be an object")
    if not isinstance(inventory, dict):
        raise CampaignSetupError("setup.player.inventory must be an object")

    hp = data.get("hp")
    if (
        not isinstance(hp, dict)
        or not isinstance(hp.get("current"), (int, float))
        or not isinstance(hp.get("max"), (int, float))
        or hp["current"] <= 0
        or hp["max"] <= 0
        or hp["current"] > hp["max"]
    ):
        raise CampaignSetupError("Player HP must be a positive current/max pair")
    if not isinstance(data.get("ac"), (int, float)) or data["ac"] <= 0:
        raise CampaignSetupError("Player AC must be a positive number")
    for field in ("race", "class", "background"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise CampaignSetupError(f"Player {field} must not be empty")
    if not isinstance(data.get("level"), int) or data["level"] < 1:
        raise CampaignSetupError("Player level must be a positive integer")

    stats = data.get("stats") or data.get("abilities")
    required_stats = {"str", "dex", "con", "int", "wis", "cha"}
    if not isinstance(stats, dict) or not required_stats.issubset(stats):
        raise CampaignSetupError(
            "Player stats must define str, dex, con, int, wis, and cha"
        )
    if not all(
        isinstance(stats[key], (int, float)) and stats[key] > 0
        for key in required_stats
    ):
        raise CampaignSetupError("Player ability scores must be positive numbers")

    xp = data.get("xp")
    if (
        not isinstance(xp, dict)
        or not isinstance(xp.get("current"), (int, float))
        or xp["current"] < 0
        or not isinstance(xp.get("next_level"), (int, float))
        or xp["next_level"] <= 0
    ):
        raise CampaignSetupError(
            "Player XP must define current and a positive next_level"
        )
    if not isinstance(data.get("money"), (int, float)):
        raise CampaignSetupError("Player money must be numeric")
    if not isinstance(data.get("proficiency_bonus"), (int, float)):
        raise CampaignSetupError("Player proficiency_bonus must be numeric")
    if not isinstance(data.get("skills"), dict) or not data["skills"]:
        raise CampaignSetupError("Player skills must not be empty")
    saves = data.get("saves")
    if not isinstance(saves, dict) or not required_stats.issubset(saves):
        raise CampaignSetupError(
            "Player saves must define str, dex, con, int, wis, and cha"
        )
    if not isinstance(data.get("save_proficiencies"), list):
        raise CampaignSetupError("Player save_proficiencies must be an array")
    if not isinstance(data.get("conditions"), list):
        raise CampaignSetupError("Player conditions must be an array")
    if not isinstance(data.get("features"), list) or not data["features"]:
        raise CampaignSetupError("Player features must not be empty")

    equipment = data.get("equipment")
    if not isinstance(equipment, dict) or not equipment:
        raise CampaignSetupError("Player starting equipment must not be empty")
    stackable = inventory.get("stackable")
    unique = inventory.get("unique")
    if not isinstance(stackable, dict) or not isinstance(unique, list):
        raise CampaignSetupError(
            "Player inventory must contain stackable and unique collections"
        )
    if not stackable and not unique:
        raise CampaignSetupError("Player starting inventory must not be empty")


def _validate_core_node_data(nodes: dict[str, dict[str, Any]]) -> None:
    """Require the minimum fields used by CORE views and gameplay tools."""
    requirements = {
        "location": ("description",),
        "npc": ("description", "attitude"),
        "quest": ("description", "status", "objectives"),
        "consequence": ("description", "trigger", "status"),
    }
    for node_id, node in nodes.items():
        required_fields = requirements.get(node["type"], ())
        for field in required_fields:
            value = node["data"].get(field)
            if value is None or value == "" or value == []:
                raise CampaignSetupError(
                    f"Node '{node_id}' requires non-empty data.{field}"
                )
    economy = nodes.get("misc:economy", {}).get("data", {})
    for field in ("expenses", "income", "production", "random_events"):
        if field not in economy:
            raise CampaignSetupError(
                f"misc:economy requires data.{field}"
            )


def validate_campaign_setup(
    setup: dict[str, Any],
    module_ids: Iterable[str],
    *,
    project_root: Path | None = None,
) -> None:
    """Reject a blueprint that cannot produce a ready-to-play campaign."""
    if not isinstance(setup, dict):
        raise CampaignSetupError("Campaign setup must be an object")
    root = Path(project_root or get_project_root())
    manifests = _selected_manifests(root, module_ids)

    required_sections = set(CAMPAIGN_SETUP_SCHEMA["required"])
    missing_sections = sorted(required_sections - setup.keys())
    if missing_sections:
        raise CampaignSetupError(
            f"Campaign setup is missing: {', '.join(missing_sections)}"
        )

    _validate_player(setup.get("player", {}))

    raw_nodes = setup.get("nodes")
    if not isinstance(raw_nodes, list):
        raise CampaignSetupError("setup.nodes must be an array")
    nodes: dict[str, dict[str, Any]] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise CampaignSetupError("Every setup node must be an object")
        node_id = str(raw_node.get("id") or "")
        node_type = str(raw_node.get("type") or "")
        name = str(raw_node.get("name") or "").strip()
        data = raw_node.get("data")
        if node_id == "player:active":
            raise CampaignSetupError("player:active belongs in setup.player")
        if (
            ":" not in node_id
            or node_type not in NODE_TYPES
            or node_id.split(":", 1)[0] != node_type
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", node_id.split(":", 1)[1])
        ):
            raise CampaignSetupError(f"Invalid WorldGraph node: {node_id!r}")
        if node_id in nodes:
            raise CampaignSetupError(f"Duplicate WorldGraph node: {node_id}")
        if not name or not isinstance(data, dict):
            raise CampaignSetupError(f"Node '{node_id}' needs a name and data object")
        nodes[node_id] = raw_node

    counts = Counter(node["type"] for node in nodes.values())
    minimums = {
        "location": 4,
        "npc": 6,
        "quest": 3,
        "consequence": 3,
    }
    for node_type, minimum in minimums.items():
        if counts[node_type] < minimum:
            raise CampaignSetupError(
                f"Campaign needs at least {minimum} {node_type} nodes"
            )
    if "misc:economy" not in nodes:
        raise CampaignSetupError("Campaign needs the misc:economy node")
    _validate_core_node_data(nodes)

    starting_location_id = setup.get("starting_location_id")
    if (
        starting_location_id not in nodes
        or nodes[starting_location_id].get("type") != "location"
    ):
        raise CampaignSetupError(
            "starting_location_id must reference a location node"
        )

    raw_edges = setup.get("edges")
    if not isinstance(raw_edges, list):
        raise CampaignSetupError("setup.edges must be an array")
    all_node_ids = set(nodes) | {"player:active"}
    edge_keys: set[tuple[str, str, str]] = set()
    for edge in raw_edges:
        if not isinstance(edge, dict):
            raise CampaignSetupError("Every setup edge must be an object")
        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type")
        if source not in all_node_ids or target not in all_node_ids:
            raise CampaignSetupError(
                f"Edge references an unknown node: {source!r} -> {target!r}"
            )
        if edge_type not in EDGE_TYPES:
            raise CampaignSetupError(f"Unknown edge type: {edge_type!r}")
        key = (source, target, edge_type)
        if key in edge_keys:
            raise CampaignSetupError(
                f"Duplicate edge: {source} -[{edge_type}]-> {target}"
            )
        edge_keys.add(key)

    location_ids = {
        node_id for node_id, node in nodes.items() if node["type"] == "location"
    }
    adjacency = {node_id: set() for node_id in location_ids}
    for source, target, edge_type in edge_keys:
        if (
            edge_type == "connected"
            and source in location_ids
            and target in location_ids
        ):
            adjacency[source].add(target)
            adjacency[target].add(source)
    reached = {starting_location_id}
    queue = deque([starting_location_id])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current] - reached:
            reached.add(neighbor)
            queue.append(neighbor)
    if reached != location_ids:
        raise CampaignSetupError("Every location must connect to the starting map")

    for node_id, node in nodes.items():
        if node["type"] != "npc":
            continue
        if not any(
            edge_type == "at"
            and source == node_id
            and target in location_ids
            for source, target, edge_type in edge_keys
        ):
            raise CampaignSetupError(f"NPC '{node_id}' has no location")

    overview = setup.get("overview")
    if not isinstance(overview, dict):
        raise CampaignSetupError("setup.overview must be an object")
    for field in ("current_date", "precise_time", "time_of_day", "currency", "calendar"):
        if field not in overview:
            raise CampaignSetupError(f"setup.overview.{field} is required")

    session_zero = setup.get("session_zero")
    if not isinstance(session_zero, str) or not session_zero.strip():
        raise CampaignSetupError("Session 0 summary must not be empty")

    module_data = setup.get("module_data")
    if not isinstance(module_data, dict):
        raise CampaignSetupError("setup.module_data must be an object")
    unexpected_configs = sorted(set(module_data) - set(manifests))
    if unexpected_configs:
        raise CampaignSetupError(
            "Setup contains config for unselected modules: "
            + ", ".join(unexpected_configs)
        )

    player = setup["player"]
    for module_id, manifest in manifests.items():
        contract = manifest.get("creation_contract", {})
        if not isinstance(contract, dict):
            raise CampaignSetupError(
                f"Module '{module_id}' has an invalid creation contract"
            )
        if contract.get("requires_module_data", False):
            config = module_data.get(module_id)
            if not isinstance(config, dict) or not config:
                raise CampaignSetupError(
                    f"Module '{module_id}' requires module_data config"
                )
            for field in contract.get("module_data_fields", []):
                if _nested_value(config, field) is None:
                    raise CampaignSetupError(
                        f"Module '{module_id}' config requires '{field}'"
                    )
        for field in contract.get("player_data_fields", []):
            if _nested_value(player["data"], field) is None:
                raise CampaignSetupError(
                    f"Module '{module_id}' requires player field '{field}'"
                )
        minimum_inventory = int(
            contract.get("player_inventory_min_stackable", 0) or 0
        )
        if len(player["inventory"]["stackable"]) < minimum_inventory:
            raise CampaignSetupError(
                f"Module '{module_id}' requires starting stackable inventory"
            )
        for requirement in contract.get("required_nodes", []):
            matches = [
                node for node in nodes.values()
                if _node_matches(node, requirement)
            ]
            minimum = int(requirement.get("min_count", 1))
            if len(matches) < minimum:
                label = requirement.get("label") or requirement.get("type") or "node"
                raise CampaignSetupError(
                    f"Module '{module_id}' requires at least {minimum} {label} nodes"
                )


def apply_campaign_setup(
    campaign_dir: Path,
    setup: dict[str, Any],
    module_ids: Iterable[str],
    *,
    character_name: str,
) -> None:
    """Persist one already-validated setup into a newly claimed campaign."""
    campaign_dir = Path(campaign_dir)
    selected_modules = list(dict.fromkeys(module_ids))
    validate_campaign_setup(
        setup,
        selected_modules,
        project_root=campaign_dir.parents[2],
    )

    graph = WorldGraph(campaign_dir)
    with graph.transaction() as world:
        player = world["nodes"].get("player:active")
        if player is None:
            raise CampaignSetupError("Campaign shell has no player:active node")
        player["name"] = character_name
        player["data"] = setup["player"]["data"]
        player["inventory"] = setup["player"]["inventory"]

        for node in setup["nodes"]:
            if not graph.add_node(
                node["id"],
                node["type"],
                node["name"],
                node["data"],
            ):
                raise CampaignSetupError(f"Failed to create node '{node['id']}'")
            if "inventory" in node:
                world["nodes"][node["id"]]["inventory"] = node["inventory"]

        for edge in setup["edges"]:
            if not graph.add_edge(
                edge["from"],
                edge["to"],
                edge["type"],
                edge.get("data"),
            ):
                raise CampaignSetupError(
                    f"Failed to create edge {edge['from']} -> {edge['to']}"
                )

    starting_id = setup["starting_location_id"]
    starting_name = graph.get_node(starting_id)["name"]
    with graph.transaction() as world:
        player = world["nodes"]["player:active"]
        player["data"]["current_location"] = starting_name
        player["current_location"] = starting_name
    if not graph.add_edge("player:active", starting_id, "at"):
        raise CampaignSetupError("Failed to place player at starting location")

    overview_updates = dict(setup["overview"])
    overview_updates.update(
        {
            "player_position": {
                "current_location": starting_name,
                "previous_location": None,
            },
            "current_character": character_name,
            "session_count": 0,
        }
    )
    overview_store = JsonOperations(str(campaign_dir))
    if not overview_store.update_json(
        "campaign-overview.json",
        overview_updates,
    ):
        raise CampaignSetupError("Failed to update campaign overview")

    module_store = ModuleDataManager(campaign_dir)
    for module_id in selected_modules:
        config = setup["module_data"].get(module_id)
        if config is not None and not module_store.save(module_id, config):
            raise CampaignSetupError(
                f"Failed to save module config for '{module_id}'"
            )

    session_log = campaign_dir / "session-log.md"
    with session_log.open("a", encoding="utf-8") as handle:
        handle.write("## Session 0: Campaign Creation\n\n")
        handle.write(setup["session_zero"].strip() + "\n\n---\n\n")


def campaign_readiness_errors(
    campaign_dir: Path,
    module_ids: Iterable[str],
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return post-persistence readiness errors for a created campaign."""
    campaign_dir = Path(campaign_dir)
    root = Path(project_root or get_project_root())
    errors: list[str] = []
    graph = WorldGraph(campaign_dir)
    player = graph.get_node("player:active")
    if not player:
        errors.append("player:active is missing")
    else:
        try:
            _validate_player(
                {
                    "data": player.get("data"),
                    "inventory": player.get("inventory"),
                }
            )
        except CampaignSetupError as exc:
            errors.append(str(exc))
    for node_type, minimum in {
        "location": 4,
        "npc": 6,
        "quest": 3,
        "consequence": 3,
    }.items():
        count = len(graph.list_nodes(node_type=node_type))
        if count < minimum:
            errors.append(f"expected {minimum} {node_type} nodes, found {count}")
    if not graph.get_node("misc:economy"):
        errors.append("misc:economy is missing")

    overview_path = campaign_dir / "campaign-overview.json"
    try:
        overview = json.loads(overview_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("campaign-overview.json is unreadable")
        overview = {}
    position = overview.get("player_position", {})
    if not isinstance(position, dict) or not position.get("current_location"):
        errors.append("starting player position is missing")

    manifests = _selected_manifests(root, module_ids)
    module_store = ModuleDataManager(campaign_dir)
    world_nodes = graph.list_nodes()
    for module_id, manifest in manifests.items():
        contract = manifest.get("creation_contract", {})
        if contract.get("requires_module_data") and not module_store.exists(module_id):
            errors.append(f"module config is missing for '{module_id}'")
        for requirement in contract.get("required_nodes", []):
            matches = [
                node for node in world_nodes
                if _node_matches(node, requirement)
            ]
            if len(matches) < int(requirement.get("min_count", 1)):
                errors.append(
                    f"module nodes are incomplete for '{module_id}'"
                )
                break
    return errors
