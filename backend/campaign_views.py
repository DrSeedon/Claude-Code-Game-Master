"""Player-safe read projections for the web campaign dashboard.

WorldGraph remains the source of truth.  This module deliberately returns
small, JSON-safe DTOs instead of exposing raw nodes, edges, or DM-only fields.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from lib.currency import format_money, load_config
from lib.world_graph import WorldGraph


WIKI_TYPES = {
    "armor",
    "artifact",
    "book",
    "cantrip",
    "chapter",
    "creature",
    "effect",
    "item",
    "material",
    "misc",
    "potion",
    "spell",
    "technique",
    "tool",
    "weapon",
}

_HIDDEN_VISIBILITY = {"dm", "dm-only", "hidden", "secret", "unrevealed"}
_VISIBLE_VISIBILITY = {"known", "player", "player-known", "public", "revealed"}
_PRIVATE_FIELD_NAMES = {
    "dm",
    "dm_only",
    "dm_notes",
    "gm",
    "gm_only",
    "gm_notes",
    "hidden",
    "internal",
    "secret",
    "secrets",
    "unknown",
    "unrevealed",
}
_PARTY_SHEET_FIELDS = {
    "ac",
    "abilities",
    "class",
    "hp",
    "hp_max",
    "level",
    "prot",
    "race",
    "saves",
    "skills",
    "speed",
    "stats",
}
_LEGACY_ITEM_WEIGHT_RE = re.compile(
    r"\s*\[(?P<weight>\d+(?:[.,]\d+)?)\s*kg\]\s*$",
    re.IGNORECASE,
)


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data", {})
    return data if isinstance(data, dict) else {}


def _field(node: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read canonical node.data first, retaining read-only legacy fallback."""
    data = _node_data(node)
    if key in data:
        return data[key]
    return node.get(key, default)


def _private_field(key: Any) -> bool:
    normalized = str(key).strip().casefold().replace("-", "_").replace(" ", "_")
    return (
        normalized in _PRIVATE_FIELD_NAMES
        or normalized.startswith("dm_")
        or normalized.startswith("gm_")
    )


def _player_safe_copy(value: Any) -> Any:
    """Copy nested player-facing data while removing explicit GM-only branches."""
    if isinstance(value, dict):
        if _explicitly_hidden(value):
            return None
        result = {}
        for key, item in value.items():
            if _private_field(key):
                continue
            cleaned = _player_safe_copy(item)
            if cleaned is not None:
                result[key] = cleaned
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            cleaned = _player_safe_copy(item)
            if cleaned is not None:
                result.append(cleaned)
        return result
    return copy.deepcopy(value)


def _clean_mapping(value: Any) -> dict[str, Any]:
    cleaned = _player_safe_copy(value)
    return cleaned if isinstance(cleaned, dict) else {}


def _clean_list(value: Any) -> list[Any]:
    cleaned = _player_safe_copy(value)
    return cleaned if isinstance(cleaned, list) else []


def _explicitly_hidden(value: dict[str, Any]) -> bool:
    containers = [value]
    data = _node_data(value)
    if data is not value:
        containers.append(data)
    return any(
        container.get("hidden") is True
        or container.get("secret") is True
        or container.get("player_visible") is False
        or str(container.get("visibility", "")).strip().casefold()
        in _HIDDEN_VISIBILITY
        for container in containers
    )


def _explicitly_visible(value: dict[str, Any]) -> bool:
    containers = [value]
    data = _node_data(value)
    if data is not value:
        containers.append(data)
    return any(
        container.get("player_visible") is True
        or container.get("known") is True
        or container.get("discovered") is True
        or container.get("revealed") is True
        or str(container.get("visibility", "")).strip().casefold()
        in _VISIBLE_VISIBILITY
        for container in containers
    )


def _number(value: Any, default: int | float = 0) -> int | float:
    if isinstance(value, bool):
        return default
    return value if isinstance(value, (int, float)) else default


def _resolve_location_name(graph: WorldGraph, value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if ":" not in value:
        return value
    node = graph.get_node(value)
    return node.get("name", value) if node else value


def node_location(graph: WorldGraph, node_id: str, node: dict[str, Any]) -> str | None:
    """Return a node's canonical location, with graph-edge compatibility."""
    location = _field(node, "current_location")
    if location:
        return _resolve_location_name(graph, location)

    edges = graph.get_edges(node_id, edge_type="at", direction="out")
    if not edges:
        return None
    return _resolve_location_name(graph, edges[0].get("to"))


def player_location(
    graph: WorldGraph,
    player_id: str,
    player: dict[str, Any],
    overview: dict[str, Any] | None = None,
) -> str | None:
    """Return player location, falling back to campaign metadata."""
    location = node_location(graph, player_id, player)
    if location:
        return location

    overview = overview or {}
    position = overview.get("player_position", {})
    if isinstance(position, dict):
        location = position.get("current_location")
        if location:
            return _resolve_location_name(graph, location)
    return _resolve_location_name(graph, overview.get("current_location"))


def _item_name_and_weight(
    raw_name: Any,
    explicit_weight: Any = None,
) -> tuple[str, int | float | None]:
    """Normalize legacy ``Name [0.5kg]`` inventory strings for web views."""
    name = str(raw_name)
    match = _LEGACY_ITEM_WEIGHT_RE.search(name)
    weight = explicit_weight if isinstance(explicit_weight, (int, float)) else None
    if match:
        name = name[: match.start()].rstrip()
        if weight is None:
            weight = float(match.group("weight").replace(",", "."))
    return name, weight


def inventory_items(
    graph: WorldGraph,
    owner_id: str,
    owner: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Normalize canonical embedded inventory into dashboard item rows.

    An explicit embedded inventory, including an empty one, wins over legacy
    ``owns`` edges so stale compatibility data cannot resurrect removed items.
    """
    owner = owner or graph.get_node(owner_id) or {}
    if "inventory" in owner:
        inventory = owner.get("inventory")
    elif isinstance(owner.get("data"), dict) and "inventory" in owner["data"]:
        inventory = owner["data"].get("inventory")
    else:
        inventory = None

    result: list[dict[str, Any]] = []
    if isinstance(inventory, dict):
        stackable = inventory.get("stackable", {})
        if isinstance(stackable, dict):
            for name, raw in sorted(stackable.items(), key=lambda item: item[0].casefold()):
                details = raw if isinstance(raw, dict) else {}
                quantity = details.get("qty", raw if isinstance(raw, (int, float)) else 1)
                display_name, weight = _item_name_and_weight(
                    name,
                    details.get("weight"),
                )
                row = {
                    "name": display_name,
                    "quantity": _number(quantity, 1),
                    "unique": False,
                }
                if weight is not None:
                    row["weight"] = weight
                result.append(row)

        unique = inventory.get("unique", [])
        if isinstance(unique, list):
            for raw in unique:
                if isinstance(raw, dict):
                    source_name = (
                        raw.get("name") or raw.get("description") or "Unnamed item"
                    )
                    name, weight = _item_name_and_weight(
                        source_name,
                        raw.get("weight"),
                    )
                    row = {
                        "name": name,
                        "quantity": _number(raw.get("qty", 1), 1),
                        "unique": True,
                    }
                    if weight is not None:
                        row["weight"] = weight
                    if (
                        raw.get("description")
                        and raw.get("description") != source_name
                    ):
                        row["description"] = str(raw["description"])
                else:
                    name, weight = _item_name_and_weight(raw)
                    row = {"name": name, "quantity": 1, "unique": True}
                    if weight is not None:
                        row["weight"] = weight
                result.append(row)
        return result

    # Read-only compatibility for worlds not yet migrated to embedded inventory.
    for edge in graph.get_edges(owner_id, edge_type="owns", direction="out"):
        item_id = edge.get("to")
        item = graph.get_node(item_id) if item_id else None
        if not item:
            continue
        edge_data = edge.get("data", {})
        details = edge_data if isinstance(edge_data, dict) else {}
        item_data = _node_data(item)
        quantity = item_data.get("quantity", details.get("quantity", 1))
        row = {
            "id": item_id,
            "name": item.get("name", item_id),
            "quantity": _number(quantity, 1),
            "unique": False,
        }
        if isinstance(item_data.get("weight"), (int, float)):
            row["weight"] = item_data["weight"]
        result.append(row)
    return sorted(result, key=lambda item: item["name"].casefold())


class CampaignViewProjector:
    """Build related dashboard views from one campaign graph."""

    def __init__(self, campaign_dir: Path | str):
        self.campaign_dir = Path(campaign_dir)
        self.graph = WorldGraph(campaign_dir=self.campaign_dir)
        self.overview = self._load_overview()
        self.player_id, self.player = self._find_player()

    def _load_overview(self) -> dict[str, Any]:
        path = self.campaign_dir / "campaign-overview.json"
        if not path.exists():
            return {}
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("campaign-overview.json must contain an object")
        return value

    def _find_player(self) -> tuple[str, dict[str, Any]]:
        active = self.graph.get_node("player:active")
        if active and active.get("type") == "player":
            return "player:active", active
        players = self.graph.list_nodes(node_type="player")
        if not players:
            # A campaign can exist before the wizard has created its character.
            # Dashboard endpoints must remain usable for that intermediate state.
            return "player:active", {}
        player = players[0]
        return player["id"], player

    def _money(self) -> tuple[int, dict[str, Any]]:
        raw = _field(self.player, "money", _field(self.player, "gold", 0))
        amount = int(_number(raw, 0))
        config = load_config(self.campaign_dir)
        return amount, config

    def campaign(self) -> dict[str, Any]:
        return {
            "name": self.overview.get("name", self.campaign_dir.name),
            "campaign_name": self.overview.get(
                "campaign_name", self.overview.get("name", self.campaign_dir.name)
            ),
            "genre": self.overview.get("genre", ""),
            "tone": self.overview.get("tone", ""),
            "current_date": self.overview.get("current_date", ""),
            "precise_time": self.overview.get(
                "precise_time", self.overview.get("time_of_day", "")
            ),
            "play_mode": self.overview.get("play_mode", "interactive"),
            "location": player_location(
                self.graph, self.player_id, self.player, self.overview
            ),
        }

    def character(self) -> dict[str, Any]:
        hp_raw = _field(self.player, "hp", 0)
        if isinstance(hp_raw, dict):
            hp_current = int(_number(hp_raw.get("current"), 0))
            hp_max = int(_number(hp_raw.get("max"), hp_current))
        else:
            hp_current = int(_number(hp_raw, 0))
            hp_max = int(_number(_field(self.player, "hp_max", hp_current), hp_current))

        xp_raw = _field(self.player, "xp", 0)
        if isinstance(xp_raw, dict):
            xp_current = int(_number(xp_raw.get("current"), 0))
            xp_next = xp_raw.get("next_level")
        else:
            xp_current = int(_number(xp_raw, 0))
            xp_next = None

        money, currency = self._money()
        result = {
            "id": self.player_id,
            "name": self.player.get("name", "Unknown"),
            "race": _field(self.player, "race", ""),
            "class": _field(self.player, "class", ""),
            "subclass": _field(self.player, "subclass", ""),
            "level": int(_number(_field(self.player, "level", 1), 1)),
            "background": _field(self.player, "background", ""),
            "hp": {"current": hp_current, "max": hp_max},
            "xp": {"current": xp_current, "next_level": xp_next},
            "ac": _field(self.player, "ac"),
            "prot": _field(self.player, "prot"),
            "speed": _field(self.player, "speed"),
            "money": {
                "base_units": money,
                "formatted": format_money(money, currency),
                "base": currency.get("base", ""),
            },
            "location": player_location(
                self.graph, self.player_id, self.player, self.overview
            ),
            "conditions": _clean_list(_field(self.player, "conditions", [])),
            "stats": _clean_mapping(_field(self.player, "stats", {})),
            "abilities": _clean_mapping(_field(self.player, "abilities", {})),
            "skills": _clean_mapping(_field(self.player, "skills", {})),
            "saves": _clean_mapping(_field(self.player, "saves", {})),
            "save_proficiencies": _clean_list(
                _field(self.player, "save_proficiencies", [])
            ),
            "equipment": _clean_mapping(_field(self.player, "equipment", {})),
            "features": _clean_list(_field(self.player, "features", [])),
            "custom_stats": _clean_mapping(_field(self.player, "custom_stats", {})),
        }
        return result

    def inventory(self) -> dict[str, Any]:
        items = inventory_items(self.graph, self.player_id, self.player)
        total_weight = sum(
            float(item.get("weight", 0)) * float(item.get("quantity", 1))
            for item in items
        )
        return {
            "owner_id": self.player_id,
            "items": items,
            "total_quantity": sum(item.get("quantity", 1) for item in items),
            "total_weight": round(total_weight, 4),
        }

    def quests(self) -> list[dict[str, Any]]:
        result = []
        for quest in self.graph.list_nodes(node_type="quest"):
            if _explicitly_hidden(quest):
                continue
            data = _node_data(quest)
            objectives = []
            raw_objectives = data.get("objectives", [])
            if isinstance(raw_objectives, list):
                for raw in raw_objectives:
                    if isinstance(raw, dict):
                        if _explicitly_hidden(raw):
                            continue
                        objectives.append(
                            {
                                "text": str(raw.get("text", "")),
                                "done": bool(raw.get("done", raw.get("completed", False))),
                            }
                        )
                    else:
                        objectives.append({"text": str(raw), "done": False})
            done = sum(1 for objective in objectives if objective["done"])
            result.append(
                {
                    "id": quest["id"],
                    "name": quest.get("name", quest["id"]),
                    "type": data.get("quest_type", data.get("type", "side")),
                    "description": data.get("description", ""),
                    "status": data.get("status", "active"),
                    "objectives": objectives,
                    "progress": {"done": done, "total": len(objectives)},
                }
            )
        return sorted(result, key=lambda quest: (quest["status"] != "active", quest["name"]))

    def _known_entity_ids(self) -> set[str]:
        known = {self.player_id}
        for edge in self.graph.get_edges(self.player_id, edge_type="known_by", direction="both"):
            known.add(edge["to"] if edge.get("from") == self.player_id else edge["from"])
        has_embedded_inventory = (
            "inventory" in self.player
            or "inventory" in _node_data(self.player)
        )
        for edge in self.graph.get_edges(self.player_id, direction="out"):
            if edge.get("type") == "trained" or (
                edge.get("type") == "owns" and not has_embedded_inventory
            ):
                known.add(edge.get("to"))
        return known

    def npcs(self) -> dict[str, list[dict[str, Any]]]:
        known_ids = self._known_entity_ids()
        party: list[dict[str, Any]] = []
        known: list[dict[str, Any]] = []
        for npc in self.graph.npc_list():
            data = _node_data(npc)
            is_party = bool(data.get("party_member") or data.get("is_party_member"))
            is_known = is_party or npc["id"] in known_ids or _explicitly_visible(npc)
            if _explicitly_hidden(npc) or not is_known:
                continue

            common = {
                "id": npc["id"],
                "name": npc.get("name", npc["id"]),
                "description": data.get("description", data.get("desc", "")),
                "attitude": data.get("attitude", "neutral"),
                "location": node_location(self.graph, npc["id"], npc),
            }
            known.append(common)
            if is_party:
                sheet = data.get("character_sheet", {})
                safe_sheet = {
                    key: sheet[key]
                    for key in _PARTY_SHEET_FIELDS
                    if isinstance(sheet, dict) and key in sheet
                }
                party.append(
                    {
                        **common,
                        "character_sheet": _clean_mapping(safe_sheet),
                        "conditions": _clean_list(data.get("conditions", [])),
                        "inventory": inventory_items(self.graph, npc["id"], npc),
                    }
                )
        return {
            "party": sorted(party, key=lambda npc: npc["name"].casefold()),
            "known": sorted(known, key=lambda npc: npc["name"].casefold()),
        }

    def wiki(self) -> list[dict[str, Any]]:
        known_ids = self._known_entity_ids()
        inventory_names = {
            item["name"].casefold() for item in inventory_items(
                self.graph, self.player_id, self.player
            )
        }
        result = []
        for node_type in WIKI_TYPES:
            for node in self.graph.list_nodes(node_type=node_type):
                data = _node_data(node)
                known = (
                    node["id"] in known_ids
                    or node.get("name", "").casefold() in inventory_names
                    or _explicitly_visible(node)
                )
                if _explicitly_hidden(node) or not known:
                    continue
                result.append(
                    {
                        "id": node["id"],
                        "type": node_type,
                        "name": node.get("name", node["id"]),
                        "description": data.get("description", ""),
                        "mechanics": _clean_mapping(data.get("mechanics", {})),
                        "recipe": _clean_mapping(data.get("recipe", {})),
                    }
                )
        return sorted(result, key=lambda entry: (entry["type"], entry["name"].casefold()))

    @staticmethod
    def _visible_schedule(entries: Any, allowed: tuple[str, ...]) -> list[dict[str, Any]]:
        result = []
        if not isinstance(entries, list):
            return result
        for entry in entries:
            if not isinstance(entry, dict) or _explicitly_hidden(entry):
                continue
            projected = {key: copy.deepcopy(entry[key]) for key in allowed if key in entry}
            if projected:
                result.append(projected)
        return result

    def economy(self) -> dict[str, Any]:
        money, currency = self._money()
        economy_node = self.graph.get_node("misc:economy") or {}
        data = _node_data(economy_node)
        production = self._visible_schedule(
            data.get("production", []),
            ("name", "item", "qty", "qty_dice", "per_hours", "interval_hours", "worker"),
        )
        for location in self.graph.list_nodes(node_type="location"):
            for entry in self._visible_schedule(
                _node_data(location).get("production", []),
                ("name", "item", "qty", "qty_dice", "per_hours", "interval_hours", "worker"),
            ):
                production.append(
                    {
                        **entry,
                        "location": location.get("name", location["id"]),
                        "location_id": location["id"],
                    }
                )
        return {
            "balance": {
                "base_units": money,
                "formatted": format_money(money, currency),
            },
            "currency": copy.deepcopy(currency),
            "expenses": self._visible_schedule(
                data.get("expenses", []), ("name", "cost", "per_hours")
            ),
            "income": self._visible_schedule(
                data.get("income", []),
                ("name", "amount", "dice", "dc", "pay_success", "pay_fail", "per_hours"),
            ),
            "production": production,
        }

    def consequences(self) -> list[dict[str, Any]]:
        result = []
        visible_statuses = {"expired", "resolved", "triggered"}
        for node in self.graph.list_nodes(node_type="consequence"):
            data = _node_data(node)
            status = str(data.get("status", "pending")).casefold()
            if _explicitly_hidden(node):
                continue
            if status not in visible_statuses and not _explicitly_visible(node):
                continue
            item = {
                "id": node["id"],
                "name": node.get("name", node["id"]),
                "description": data.get("description", node.get("name", "")),
                "status": status,
            }
            for key in ("resolution", "resolved", "triggered_at"):
                if key in data:
                    item[key] = copy.deepcopy(data[key])
            if status == "pending" and "hours_remaining" in data:
                item["hours_remaining"] = data["hours_remaining"]
            result.append(item)
        return sorted(result, key=lambda item: (item["status"], item["name"].casefold()))

    def snapshot(self) -> dict[str, Any]:
        """Return the complete player-facing dashboard state."""
        result = {
            "visibility_policy": {
                "npcs": "party_or_explicitly_known",
                "wiki": "owned_trained_or_explicitly_known",
                "consequences": "occurred_or_explicitly_revealed",
                "future_random_events": "never_exposed",
            },
            "campaign": self.campaign(),
            "character": self.character(),
            "inventory": self.inventory(),
            "quests": self.quests(),
            "npcs": self.npcs(),
            "wiki": self.wiki(),
            "economy": self.economy(),
            "consequences": self.consequences(),
        }
        # Assert the API contract at its boundary and return a detached value.
        return json.loads(json.dumps(result, ensure_ascii=False))


def get_campaign_views(campaign_dir: Path | str) -> dict[str, Any]:
    """Build all dashboard projections for a campaign directory."""
    return CampaignViewProjector(campaign_dir).snapshot()
