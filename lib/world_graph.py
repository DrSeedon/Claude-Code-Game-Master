#!/usr/bin/env python3
"""
WorldGraph — unified graph-based world state manager.
Nodes (player, npc, location, item, creature, fact, quest, consequence, spell, technique)
connected by typed edges (at, owns, connected, requires, involves, trained, sells,
spawns_at, known_by, relationship, triggers, crafted_with).
Data lives in world.json per campaign.
"""

import json
import os
import random
import re
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))

try:
    from colors import Colors
except ImportError:
    class Colors:
        RESET = RS = B = C = G = R = Y = DIM = DM = MAGENTA = BOLD_GREEN = BOLD_RED = BOLD_CYAN = BOLD_YELLOW = CYAN = ""

NODE_TYPES = [
    "player", "npc", "location", "item", "creature",
    "fact", "quest", "consequence", "spell", "technique",
    "potion", "material", "artifact", "weapon", "armor",
    "tool", "book", "chapter", "cantrip", "effect", "misc"
]

EDGE_TYPES = [
    "at", "owns", "connected", "requires", "involves",
    "trained", "sells", "spawns_at", "known_by", "relationship",
    "triggers", "crafted_with"
]

SCHEMA_VERSION = 2

TYPE_COLORS = {
    "player":      Colors.BOLD_CYAN,
    "npc":         Colors.BOLD_GREEN,
    "location":    Colors.BOLD_YELLOW,
    "item":        Colors.CYAN,
    "creature":    Colors.BOLD_RED,
    "fact":        Colors.DIM,
    "quest":       Colors.MAGENTA,
    "consequence": Colors.R,
    "spell":       Colors.BOLD_CYAN,
    "technique":   Colors.G,
}


def _find_campaign_dir() -> Path:
    root = next(p for p in Path(__file__).parents if (p / ".git").exists())
    active_file = root / "world-state" / "active-campaign.txt"
    if active_file.exists():
        name = active_file.read_text().strip()
        d = root / "world-state" / "campaigns" / name
        if d.exists():
            return d
    print("No active campaign", file=sys.stderr)
    sys.exit(1)


class WorldGraph:
    def __init__(self, campaign_dir: Path = None):
        self.campaign_dir = Path(campaign_dir) if campaign_dir else _find_campaign_dir()
        self.world_file = self.campaign_dir / "world.json"

    def _load(self) -> dict:
        if self.world_file.exists():
            with open(self.world_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._empty_world()

    def _save(self, data: dict) -> bool:
        tmp = self.world_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.world_file)
        return True

    def _empty_world(self) -> dict:
        return {
            "meta": {"version": SCHEMA_VERSION, "schema": "graph"},
            "nodes": {},
            "edges": []
        }

    def _validate_node_id(self, node_id: str) -> bool:
        if ":" not in node_id:
            return False
        parts = node_id.split(":", 1)
        if parts[0] not in NODE_TYPES:
            return False
        return bool(re.match(r"^[a-z0-9][a-z0-9-]*$", parts[1]))

    def add_node(self, node_id: str, node_type: str, name: str, data: dict = None, **extra) -> bool:
        if not self._validate_node_id(node_id):
            print(f"  Invalid node ID '{node_id}'. Format: type:kebab-name", file=sys.stderr)
            return False
        w = self._load()
        if node_id in w["nodes"]:
            print(f"  Node '{node_id}' already exists", file=sys.stderr)
            return False
        node = {"type": node_type, "name": name, "data": data or {}}
        node.update(extra)
        w["nodes"][node_id] = node
        return self._save(w)

    def get_node(self, node_id: str) -> Optional[dict]:
        w = self._load()
        return w["nodes"].get(node_id)

    def update_node(self, node_id: str, updates: dict) -> bool:
        w = self._load()
        if node_id not in w["nodes"]:
            print(f"  Node '{node_id}' not found", file=sys.stderr)
            return False
        node = w["nodes"][node_id]
        if "data" in updates and isinstance(updates["data"], dict) and isinstance(node.get("data"), dict):
            node["data"].update(updates.pop("data"))
        node.update(updates)
        return self._save(w)

    def remove_node(self, node_id: str, cascade: bool = True) -> bool:
        w = self._load()
        if node_id not in w["nodes"]:
            print(f"  Node '{node_id}' not found", file=sys.stderr)
            return False
        del w["nodes"][node_id]
        if cascade:
            w["edges"] = [
                e for e in w["edges"]
                if e["from"] != node_id and e["to"] != node_id
            ]
        return self._save(w)

    def list_nodes(self, node_type: str = None) -> List[dict]:
        w = self._load()
        result = []
        for nid, node in w["nodes"].items():
            if node_type and node.get("type") != node_type:
                continue
            result.append({"id": nid, **node})
        return sorted(result, key=lambda x: (x.get("type", ""), x.get("name", "")))

    def search_nodes(self, query: str, node_type: str = None) -> List[dict]:
        if not query or not query.strip():
            return []
        w = self._load()
        query_lower = query.lower()
        results = []
        for nid, node in w["nodes"].items():
            if node_type and node.get("type") != node_type:
                continue
            score = 0
            name = node.get("name", nid).lower()
            if query_lower in name:
                score += 10
            elif query_lower in nid.lower():
                score += 8
            else:
                sm = SequenceMatcher(None, query_lower, name).ratio()
                if sm > 0.6:
                    score += int(sm * 7)
            data_str = json.dumps(node.get("data", {}), ensure_ascii=False).lower()
            if query_lower in data_str:
                score += 3
            if score > 0:
                results.append({"id": nid, "score": score, **node})
        return sorted(results, key=lambda x: -x["score"])

    def add_edge(self, from_id: str, to_id: str, edge_type: str, data: dict = None) -> bool:
        w = self._load()
        if from_id not in w["nodes"]:
            print(f"  Node '{from_id}' not found", file=sys.stderr)
            return False
        if to_id not in w["nodes"]:
            print(f"  Node '{to_id}' not found", file=sys.stderr)
            return False
        for e in w["edges"]:
            if e["from"] == from_id and e["to"] == to_id and e["type"] == edge_type:
                print(f"  Edge {from_id} -[{edge_type}]-> {to_id} already exists", file=sys.stderr)
                return False
        edge = {"from": from_id, "to": to_id, "type": edge_type}
        if data:
            edge["data"] = data
        w["edges"].append(edge)
        return self._save(w)

    def get_edges(self, node_id: str, edge_type: str = None, direction: str = "both") -> List[dict]:
        w = self._load()
        result = []
        for e in w["edges"]:
            if direction in ("out", "both") and e["from"] == node_id:
                if not edge_type or e["type"] == edge_type:
                    result.append(e)
            elif direction in ("in", "both") and e["to"] == node_id:
                if not edge_type or e["type"] == edge_type:
                    result.append(e)
        return result

    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> bool:
        w = self._load()
        before = len(w["edges"])
        w["edges"] = [
            e for e in w["edges"]
            if not (e["from"] == from_id and e["to"] == to_id and e["type"] == edge_type)
        ]
        if len(w["edges"]) == before:
            print(f"  Edge {from_id} -[{edge_type}]-> {to_id} not found", file=sys.stderr)
            return False
        return self._save(w)

    def get_neighbors(self, node_id: str, edge_type: str = None, direction: str = "out") -> List[dict]:
        w = self._load()
        neighbor_ids = set()
        for e in w["edges"]:
            if direction in ("out", "both") and e["from"] == node_id:
                if not edge_type or e["type"] == edge_type:
                    neighbor_ids.add(e["to"])
            if direction in ("in", "both") and e["to"] == node_id:
                if not edge_type or e["type"] == edge_type:
                    neighbor_ids.add(e["from"])
        return [
            {"id": nid, **w["nodes"][nid]}
            for nid in neighbor_ids
            if nid in w["nodes"]
        ]

    def format_node(self, node_id: str) -> str:
        B, RS, C, DM, G = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.G
        node = self.get_node(node_id)
        if not node:
            return f"  Node '{node_id}' not found"
        ntype = node.get("type", "?")
        tcolor = TYPE_COLORS.get(ntype, "")
        name = node.get("name", node_id)
        lines = [
            f"{'=' * 60}",
            f"  {B}{name}{RS}  {tcolor}[{ntype}]{RS}  {DM}id:{node_id}{RS}",
            f"{'─' * 60}",
        ]
        data = node.get("data", {})
        if data:
            lines.append(f"  {B}DATA{RS}")
            for k, v in data.items():
                if isinstance(v, dict):
                    v_str = ", ".join(f"{kk}: {vv}" for kk, vv in v.items())
                elif isinstance(v, list):
                    v_str = ", ".join(str(i) for i in v)
                else:
                    v_str = str(v)
                lines.append(f"    {k}: {C}{v_str}{RS}")
            lines.append("")
        inventory = node.get("inventory", {})
        if inventory:
            lines.append(f"  {B}INVENTORY{RS}")
            stackable = inventory.get("stackable", {})
            for iname, idata in stackable.items():
                qty = idata.get("qty", 1) if isinstance(idata, dict) else idata
                lines.append(f"    {G}•{RS} {iname} x{qty}")
            for item in inventory.get("unique", []):
                lines.append(f"    {G}•{RS} {item}")
            lines.append("")
        events = node.get("events", [])
        if events:
            lines.append(f"  {B}EVENTS{RS} ({len(events)})")
            for ev in events[-3:]:
                lines.append(f"    {DM}{ev.get('timestamp', '?')}{RS} {ev.get('event', '')}")
            lines.append("")
        w = self._load()
        edges_out = [e for e in w["edges"] if e["from"] == node_id]
        edges_in = [e for e in w["edges"] if e["to"] == node_id]
        if edges_out:
            lines.append(f"  {B}EDGES OUT{RS}")
            for e in edges_out:
                ed = f"  {DM}{e.get('data', '')}{RS}" if e.get("data") else ""
                target_name = w["nodes"].get(e["to"], {}).get("name", e["to"])
                lines.append(f"    -{C}[{e['type']}]{RS}-> {target_name} {DM}({e['to']}){RS}{ed}")
            lines.append("")
        if edges_in:
            lines.append(f"  {B}EDGES IN{RS}")
            for e in edges_in:
                ed = f"  {DM}{e.get('data', '')}{RS}" if e.get("data") else ""
                src_name = w["nodes"].get(e["from"], {}).get("name", e["from"])
                lines.append(f"    <-{C}[{e['type']}]{RS}- {src_name} {DM}({e['from']}){RS}{ed}")
            lines.append("")
        lines.append(f"{'=' * 60}")
        return "\n".join(lines)

    def format_node_list(self, nodes: List[dict]) -> str:
        B, RS, DM, C = Colors.B, Colors.RESET, Colors.DIM, Colors.C
        if not nodes:
            return "  (empty)"
        current_type = None
        lines = []
        for node in nodes:
            ntype = node.get("type", "?")
            if ntype != current_type:
                current_type = ntype
                tcolor = TYPE_COLORS.get(ntype, "")
                lines.append(f"\n  {B}{tcolor}[{ntype.upper()}]{RS}")
            nid = node.get("id", "?")
            name = node.get("name", nid)
            lines.append(f"    {C}{name}{RS}  {DM}{nid}{RS}")
        return "\n".join(lines)

    def stats(self) -> str:
        B, RS, C, DM = Colors.B, Colors.RESET, Colors.C, Colors.DIM
        w = self._load()
        node_counts: Dict[str, int] = {}
        for node in w["nodes"].values():
            t = node.get("type", "?")
            node_counts[t] = node_counts.get(t, 0) + 1
        edge_counts: Dict[str, int] = {}
        for e in w["edges"]:
            t = e.get("type", "?")
            edge_counts[t] = edge_counts.get(t, 0) + 1
        lines = [
            f"{'=' * 40}",
            f"  {B}WORLD GRAPH STATS{RS}",
            f"{'─' * 40}",
            f"  {B}Nodes{RS}: {C}{len(w['nodes'])}{RS}",
        ]
        for t in NODE_TYPES:
            cnt = node_counts.get(t, 0)
            if cnt:
                lines.append(f"    {t:<14} {C}{cnt}{RS}")
        lines.append(f"  {B}Edges{RS}: {C}{len(w['edges'])}{RS}")
        for t in EDGE_TYPES:
            cnt = edge_counts.get(t, 0)
            if cnt:
                lines.append(f"    {t:<14} {C}{cnt}{RS}")
        lines.append(f"{'=' * 40}")
        return "\n".join(lines)


    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    def _slug(self, name: str) -> str:
        _TRANSLIT = {
            'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
            'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
            'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
            'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
        }
        s = name.lower()
        out = []
        for ch in s:
            if ch in _TRANSLIT:
                out.append(_TRANSLIT[ch])
            else:
                out.append(ch)
        slug = re.sub(r"[^a-z0-9]+", "-", "".join(out)).strip("-")
        return slug if slug else f"id-{abs(hash(name)) % 99999:05d}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _resolve_id(self, name_or_id: str, node_type: str = None) -> Optional[str]:
        if ":" in name_or_id:
            return name_or_id
        results = self.search_nodes(name_or_id, node_type)
        if results:
            return results[0]["id"]
        return None

    def _player_id(self) -> Optional[str]:
        w = self._load()
        for nid, node in w["nodes"].items():
            if node.get("type") == "player":
                return nid
        return None

    def _fact_next_id(self, category: str) -> str:
        slug = self._slug(category)
        prefix = f"fact:{slug}-"
        w = self._load()
        existing = [k for k in w["nodes"] if k.startswith(prefix)]
        nums = []
        for k in existing:
            try:
                nums.append(int(k[len(prefix):]))
            except ValueError:
                pass
        n = max(nums, default=0) + 1
        return f"{prefix}{n:03d}"

    # ─────────────────────────────────────────────
    # NPC domain
    # ─────────────────────────────────────────────

    def npc_create(self, name: str, description: str, attitude: str = "neutral") -> str:
        node_id = f"npc:{self._slug(name)}"
        w = self._load()
        if node_id in w["nodes"]:
            suffix = 2
            while f"{node_id}-{suffix}" in w["nodes"]:
                suffix += 1
            node_id = f"{node_id}-{suffix}"
        self.add_node(node_id, "npc", name, {
            "description": description,
            "attitude": attitude,
        })
        return node_id

    def npc_event(self, node_id: str, event_text: str) -> bool:
        w = self._load()
        if node_id not in w["nodes"]:
            print(f"  Node '{node_id}' not found", file=sys.stderr)
            return False
        node = w["nodes"][node_id]
        if "events" not in node:
            node["events"] = []
        node["events"].append({"timestamp": self._now(), "event": event_text})
        return self._save(w)

    def npc_promote(self, node_id: str) -> bool:
        w = self._load()
        if node_id not in w["nodes"]:
            print(f"  Node '{node_id}' not found", file=sys.stderr)
            return False
        node = w["nodes"][node_id]
        node["data"].setdefault("party_member", True)
        node["data"].setdefault("character_sheet", {
            "hp": 10, "hp_max": 10, "ac": 10, "level": 1,
        })
        return self._save(w)

    def npc_locate(self, node_id: str, location_id: str) -> bool:
        w = self._load()
        if node_id not in w["nodes"]:
            print(f"  Node '{node_id}' not found", file=sys.stderr)
            return False
        if location_id not in w["nodes"]:
            print(f"  Node '{location_id}' not found", file=sys.stderr)
            return False
        w["edges"] = [
            e for e in w["edges"]
            if not (e["from"] == node_id and e["type"] == "at")
        ]
        w["edges"].append({"from": node_id, "to": location_id, "type": "at"})
        return self._save(w)

    # ─────────────────────────────────────────────
    # Location domain
    # ─────────────────────────────────────────────

    def location_create(self, name: str, description: str = "") -> str:
        node_id = f"location:{self._slug(name)}"
        w = self._load()
        if node_id in w["nodes"]:
            suffix = 2
            while f"{node_id}-{suffix}" in w["nodes"]:
                suffix += 1
            node_id = f"{node_id}-{suffix}"
        self.add_node(node_id, "location", name, {"description": description})
        return node_id

    def location_connect(self, from_id: str, to_id: str, path_type: str = "traveled") -> bool:
        w = self._load()
        for nid in (from_id, to_id):
            if nid not in w["nodes"]:
                print(f"  Node '{nid}' not found", file=sys.stderr)
                return False
        def _has_edge(a, b):
            return any(
                e["from"] == a and e["to"] == b and e["type"] == "connected"
                for e in w["edges"]
            )
        if not _has_edge(from_id, to_id):
            w["edges"].append({"from": from_id, "to": to_id, "type": "connected",
                               "data": {"path_type": path_type}})
        if not _has_edge(to_id, from_id):
            w["edges"].append({"from": to_id, "to": from_id, "type": "connected",
                               "data": {"path_type": path_type}})
        return self._save(w)

    # ─────────────────────────────────────────────
    # Fact domain
    # ─────────────────────────────────────────────

    def fact_add(self, category: str, text: str) -> str:
        node_id = self._fact_next_id(category)
        self.add_node(node_id, "fact", f"[{category}] {text[:40]}", {
            "category": category,
            "text": text,
            "added": self._now(),
        })
        return node_id

    # ─────────────────────────────────────────────
    # Quest domain
    # ─────────────────────────────────────────────

    def quest_create(self, name: str, quest_type: str = "side", description: str = "") -> str:
        node_id = f"quest:{self._slug(name)}"
        w = self._load()
        if node_id in w["nodes"]:
            suffix = 2
            while f"{node_id}-{suffix}" in w["nodes"]:
                suffix += 1
            node_id = f"{node_id}-{suffix}"
        self.add_node(node_id, "quest", name, {
            "quest_type": quest_type,
            "description": description,
            "status": "active",
            "objectives": [],
            "created": self._now(),
        })
        return node_id

    def quest_objective_add(self, quest_id: str, text: str) -> bool:
        w = self._load()
        if quest_id not in w["nodes"]:
            print(f"  Quest '{quest_id}' not found", file=sys.stderr)
            return False
        node = w["nodes"][quest_id]
        node["data"].setdefault("objectives", [])
        node["data"]["objectives"].append({"text": text, "done": False})
        return self._save(w)

    def quest_objective_complete(self, quest_id: str, index: int) -> bool:
        w = self._load()
        if quest_id not in w["nodes"]:
            print(f"  Quest '{quest_id}' not found", file=sys.stderr)
            return False
        objs = w["nodes"][quest_id]["data"].get("objectives", [])
        if index < 0 or index >= len(objs):
            print(f"  Objective index {index} out of range (0-{len(objs)-1})", file=sys.stderr)
            return False
        objs[index]["done"] = True
        return self._save(w)

    def quest_complete(self, quest_id: str) -> bool:
        return self.update_node(quest_id, {"data": {"status": "completed",
                                                    "completed": self._now()}})

    def quest_fail(self, quest_id: str) -> bool:
        return self.update_node(quest_id, {"data": {"status": "failed",
                                                    "failed": self._now()}})

    # ─────────────────────────────────────────────
    # Consequence domain
    # ─────────────────────────────────────────────

    def consequence_add(self, description: str, trigger: str, hours: float = None) -> str:
        slug = self._slug(description[:30])
        node_id = f"consequence:{slug}"
        w = self._load()
        if node_id in w["nodes"]:
            suffix = 2
            while f"{node_id}-{suffix}" in w["nodes"]:
                suffix += 1
            node_id = f"{node_id}-{suffix}"
        data = {
            "description": description,
            "trigger": trigger,
            "status": "pending",
            "created": self._now(),
        }
        if hours is not None:
            data["hours_remaining"] = hours
        self.add_node(node_id, "consequence", description[:40], data)
        return node_id

    def consequence_tick(self, elapsed_hours: float) -> List[dict]:
        w = self._load()
        triggered = []
        for nid, node in w["nodes"].items():
            if node.get("type") != "consequence":
                continue
            d = node.get("data", {})
            if d.get("status") != "pending":
                continue
            if "hours_remaining" not in d:
                continue
            d["hours_remaining"] = round(d["hours_remaining"] - elapsed_hours, 4)
            if d["hours_remaining"] <= 0:
                d["status"] = "triggered"
                d["triggered_at"] = self._now()
                triggered.append({"id": nid, **node})
        self._save(w)
        return triggered

    def consequence_list_resolved(self) -> List[dict]:
        w = self._load()
        result = []
        for nid, node in w["nodes"].items():
            if node.get("type") != "consequence":
                continue
            if node.get("data", {}).get("status") == "resolved":
                result.append({"id": nid, **node})
        return sorted(result, key=lambda x: x.get("data", {}).get("resolved", ""))

    def consequence_resolve(self, node_id: str, resolution: str = "") -> bool:
        data_update: dict = {"status": "resolved", "resolved": self._now()}
        if resolution:
            data_update["resolution"] = resolution
        return self.update_node(node_id, {"data": data_update})

    # ─────────────────────────────────────────────
    # Inventory domain
    # ─────────────────────────────────────────────

    def _ensure_inventory(self, w: dict, owner_id: str) -> bool:
        if owner_id not in w["nodes"]:
            print(f"  Node '{owner_id}' not found", file=sys.stderr)
            return False
        w["nodes"][owner_id].setdefault("inventory", {"stackable": {}, "unique": []})
        return True

    def inventory_add(self, owner_id: str, item_name: str, qty: int = 1, weight: float = 0.5) -> bool:
        w = self._load()
        if not self._ensure_inventory(w, owner_id):
            return False
        inv = w["nodes"][owner_id]["inventory"]["stackable"]
        if item_name in inv:
            inv[item_name]["qty"] = inv[item_name].get("qty", 0) + qty
        else:
            inv[item_name] = {"qty": qty, "weight": weight}
        return self._save(w)

    def inventory_add_unique(self, owner_id: str, item_desc: str) -> bool:
        w = self._load()
        if not self._ensure_inventory(w, owner_id):
            return False
        w["nodes"][owner_id]["inventory"]["unique"].append(item_desc)
        return self._save(w)

    def inventory_remove(self, owner_id: str, item_name: str, qty: int = 1) -> bool:
        w = self._load()
        if not self._ensure_inventory(w, owner_id):
            return False
        inv = w["nodes"][owner_id]["inventory"]["stackable"]
        if item_name not in inv:
            print(f"  Item '{item_name}' not in inventory", file=sys.stderr)
            return False
        current = inv[item_name].get("qty", 0)
        if current < qty:
            print(f"  Not enough '{item_name}': have {current}, need {qty}", file=sys.stderr)
            return False
        if current == qty:
            del inv[item_name]
        else:
            inv[item_name]["qty"] = current - qty
        return self._save(w)

    def inventory_remove_unique(self, owner_id: str, item_name: str) -> bool:
        w = self._load()
        if not self._ensure_inventory(w, owner_id):
            return False
        unique = w["nodes"][owner_id]["inventory"]["unique"]
        name_lower = item_name.lower()
        matches = [i for i, x in enumerate(unique) if name_lower in x.lower()]
        if not matches:
            print(f"  No unique item matching '{item_name}'", file=sys.stderr)
            return False
        w["nodes"][owner_id]["inventory"]["unique"].pop(matches[0])
        return self._save(w)

    def inventory_show(self, owner_id: str) -> str:
        B, RS, G, DM, C = Colors.B, Colors.RESET, Colors.G, Colors.DIM, Colors.C
        node = self.get_node(owner_id)
        if not node:
            return f"  Node '{owner_id}' not found"
        name = node.get("name", owner_id)
        inv = node.get("inventory", {})
        stackable = inv.get("stackable", {})
        unique = inv.get("unique", [])
        lines = [f"  {B}Inventory: {name}{RS}"]
        if stackable:
            total_weight = sum(
                v.get("qty", 1) * v.get("weight", 0.5)
                for v in stackable.values()
                if isinstance(v, dict)
            )
            for iname, idata in sorted(stackable.items()):
                qty = idata.get("qty", 1) if isinstance(idata, dict) else idata
                w_each = idata.get("weight", 0.5) if isinstance(idata, dict) else 0.5
                lines.append(f"    {G}•{RS} {iname} {C}x{qty}{RS}  {DM}{w_each}kg/ea{RS}")
            lines.append(f"    {DM}Total weight: {total_weight:.1f}kg{RS}")
        for item in unique:
            lines.append(f"    {G}◆{RS} {item}")
        if not stackable and not unique:
            lines.append(f"    {DM}(empty){RS}")
        return "\n".join(lines)

    def inventory_transfer(self, from_id: str, to_id: str, item_name: str, qty: int) -> bool:
        w = self._load()
        for nid in (from_id, to_id):
            if not self._ensure_inventory(w, nid):
                return False
        self._save(w)
        if not self.inventory_remove(from_id, item_name, qty):
            return False
        w2 = self._load()
        src_inv = w2["nodes"][from_id]["inventory"]["stackable"]
        weight = 0.5
        if item_name in src_inv:
            weight = src_inv[item_name].get("weight", 0.5)
        return self.inventory_add(to_id, item_name, qty, weight)

    # ─────────────────────────────────────────────
    # Player domain
    # ─────────────────────────────────────────────

    def player_update_stat(self, stat: str, delta: int) -> bool:
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        w = self._load()
        node = w["nodes"][pid]
        d = node.get("data", {})
        current = d.get(stat, 0)
        d[stat] = current + delta
        if stat == "hp" and "hp_max" in d:
            d["hp"] = max(0, min(d["hp"], d["hp_max"]))
        node["data"] = d
        return self._save(w)

    def player_hp_max(self, delta: int) -> bool:
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        w = self._load()
        node = w["nodes"][pid]
        d = node.get("data", {})
        d["hp_max"] = d.get("hp_max", 0) + delta
        node["data"] = d
        return self._save(w)

    def player_condition(self, action: str, condition_name: str = None) -> bool:
        B, RS, C, DM = Colors.B, Colors.RESET, Colors.C, Colors.DIM
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        w = self._load()
        node = w["nodes"][pid]
        d = node.get("data", {})
        conditions = d.setdefault("conditions", [])
        if action == "list":
            if not conditions:
                print(f"  {DM}(no active conditions){RS}")
            else:
                print(f"  {B}Active conditions:{RS} " + ", ".join(f"{C}{c}{RS}" for c in conditions))
            return True
        if not condition_name:
            print("  condition_name required for add/remove", file=sys.stderr)
            return False
        if action == "add":
            if condition_name in conditions:
                print(f"  Condition '{condition_name}' already active", file=sys.stderr)
                return False
            conditions.append(condition_name)
            node["data"] = d
            ok = self._save(w)
            if ok:
                print(f"  ✓ Condition added: {C}{condition_name}{RS}")
            return ok
        elif action == "remove":
            if condition_name not in conditions:
                print(f"  Condition '{condition_name}' not active", file=sys.stderr)
                return False
            conditions.remove(condition_name)
            node["data"] = d
            ok = self._save(w)
            if ok:
                print(f"  ✓ Condition removed: {C}{condition_name}{RS}")
            return ok
        else:
            print(f"  Unknown action: {action}", file=sys.stderr)
            return False

    def player_set(self, name: str) -> bool:
        overview_file = self.campaign_dir / "campaign-overview.json"
        if not overview_file.exists():
            print(f"  campaign-overview.json not found in {self.campaign_dir}", file=sys.stderr)
            return False
        with open(overview_file, "r", encoding="utf-8") as f:
            overview = json.load(f)
        overview["character"] = name
        tmp = overview_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(overview, f, indent=2, ensure_ascii=False)
        os.replace(tmp, overview_file)
        print(f"  ✓ Active character set: {name}")
        return True

    def player_show(self) -> str:
        B, RS, C, G, DM, Y = Colors.B, Colors.RESET, Colors.C, Colors.G, Colors.DIM, Colors.Y
        pid = self._player_id()
        if not pid:
            return "  No player node found"
        node = self.get_node(pid)
        name = node.get("name", pid)
        d = node.get("data", {})
        hp = d.get("hp", "?")
        hp_max = d.get("hp_max", "?")
        xp = d.get("xp", 0)
        money = d.get("money", 0)
        lines = [
            f"{'─' * 40}",
            f"  {B}{name}{RS}  {DM}{pid}{RS}",
            f"  {G}HP{RS} {C}{hp}/{hp_max}{RS}   {Y}XP{RS} {C}{xp}{RS}   {G}Gold{RS} {C}{money}{RS}",
        ]
        conditions = d.get("conditions", [])
        if conditions:
            lines.append(f"  {B}Conditions:{RS} " + ", ".join(conditions))
        inv = node.get("inventory", {})
        if inv.get("stackable") or inv.get("unique"):
            lines.append(self.inventory_show(pid))
        lines.append(f"{'─' * 40}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────
    # Wiki / Item domain
    # ─────────────────────────────────────────────

    def wiki_add(self, entity_id: str, entity_type: str, name: str,
                 mechanics: dict = None, recipe: dict = None) -> str:
        full_id = f"{entity_type}:{self._slug(entity_id)}" if ":" not in entity_id else entity_id
        data = {"mechanics": mechanics or {}}
        if recipe:
            data["recipe"] = recipe
        w = self._load()
        if full_id in w["nodes"]:
            node = w["nodes"][full_id]
            node["data"].update(data)
            self._save(w)
        else:
            self.add_node(full_id, entity_type, name, data)
        if recipe and "ingredients" in recipe:
            for ing_id, qty in recipe["ingredients"].items():
                w2 = self._load()
                if ing_id not in w2["nodes"]:
                    self.add_node(ing_id, "item", ing_id.split(":")[-1].replace("-", " ").title(), {})
                self.add_edge(full_id, ing_id, "requires",
                              {"qty": qty} if not any(
                                  e["from"] == full_id and e["to"] == ing_id and e["type"] == "requires"
                                  for e in self._load()["edges"]
                              ) else None)
        return full_id

    def inventory_craft(self, owner_id: str, recipe_id: str, qty: int = 1) -> bool:
        B, RS, C, DM, G_ = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.G
        w = self._load()
        if owner_id not in w["nodes"]:
            print(f"  Node '{owner_id}' not found", file=sys.stderr)
            return False
        rid = self._resolve_id(recipe_id) or recipe_id
        if rid not in w["nodes"]:
            print(f"  Recipe node '{recipe_id}' not found", file=sys.stderr)
            return False
        recipe_node = w["nodes"][rid]
        recipe_data = recipe_node.get("data", {}).get("recipe", {})
        ingredients: dict = recipe_data.get("ingredients", {})
        if not ingredients:
            req_edges = [e for e in w["edges"] if e["from"] == rid and e["type"] == "requires"]
            for e in req_edges:
                q = e.get("data", {}).get("qty", 1) if e.get("data") else 1
                ingredients[e["to"]] = q
        if not ingredients:
            print(f"  No recipe/ingredients found for '{rid}'", file=sys.stderr)
            return False
        inv = w["nodes"][owner_id].get("inventory", {}).get("stackable", {})
        for ing_id, need_qty in ingredients.items():
            total_need = need_qty * qty
            ing_name = w["nodes"].get(ing_id, {}).get("name", ing_id)
            have_qty = inv.get(ing_name, {}).get("qty", 0) if isinstance(inv.get(ing_name), dict) else 0
            if ing_name not in inv and ing_id not in inv:
                print(f"  Missing ingredient: {ing_name} x{total_need}", file=sys.stderr)
                return False
            key = ing_name if ing_name in inv else ing_id
            have = inv[key].get("qty", 0) if isinstance(inv[key], dict) else int(inv[key])
            if have < total_need:
                print(f"  Not enough {ing_name}: have {have}, need {total_need}", file=sys.stderr)
                return False
        skill = recipe_data.get("skill", "any")
        dc = recipe_data.get("dc")
        craft_name = recipe_node.get("name", rid)
        if dc:
            print(f"  {DM}Run:{RS} dm-roll.sh --skill \"{skill}\" --dc {dc} --label \"Craft {craft_name}\"")
        for ing_id, need_qty in ingredients.items():
            ing_name = w["nodes"].get(ing_id, {}).get("name", ing_id)
            key = ing_name if ing_name in inv else ing_id
            self.inventory_remove(owner_id, key, need_qty * qty)
        self.inventory_add(owner_id, craft_name, qty)
        print(f"  {G_}✓{RS} Crafted: {B}{craft_name}{RS} x{qty}")
        return True

    def inventory_use(self, owner_id: str, item_name: str) -> Optional[dict]:
        B, RS, C, DM = Colors.B, Colors.RESET, Colors.C, Colors.DIM
        w = self._load()
        if owner_id not in w["nodes"]:
            print(f"  Node '{owner_id}' not found", file=sys.stderr)
            return None
        inv = w["nodes"][owner_id].get("inventory", {}).get("stackable", {})
        item_key = None
        for k in inv:
            if k.lower() == item_name.lower():
                item_key = k
                break
        if not item_key:
            print(f"  Item '{item_name}' not in inventory", file=sys.stderr)
            return None
        if not self.inventory_remove(owner_id, item_key, 1):
            return None
        results = self.search_nodes(item_name)
        effects = {}
        for r in results[:3]:
            mechanics = r.get("data", {}).get("mechanics", {})
            if mechanics.get("effect") or mechanics.get("heal") or mechanics.get("damage"):
                effects = mechanics
                break
        if effects:
            print(f"  {B}Used:{RS} {item_key}")
            for k, v in effects.items():
                print(f"    {k}: {C}{v}{RS}")
        else:
            print(f"  {B}Used:{RS} {item_key}  {DM}(no effects found in wiki){RS}")
        return effects if effects else {}

    def inventory_loot(self, owner_id: str, items: list = None, gold: int = 0, xp: int = 0) -> bool:
        G_, RS, B = Colors.G, Colors.RESET, Colors.B
        w = self._load()
        if owner_id not in w["nodes"]:
            print(f"  Node '{owner_id}' not found", file=sys.stderr)
            return False
        for entry in (items or []):
            name, qty, weight = entry[0], int(entry[1]) if len(entry) > 1 else 1, float(entry[2]) if len(entry) > 2 else 0.5
            self.inventory_add(owner_id, name, qty, weight)
            print(f"  {G_}+{RS} {name} x{qty}")
        if gold:
            pid = self._player_id()
            if pid and pid == owner_id:
                self.player_update_stat("money", gold)
            else:
                node = w["nodes"][owner_id]
                node["data"]["money"] = node["data"].get("money", 0) + gold
                self._save(w)
            print(f"  {G_}+{RS} {B}{gold}{RS} gold")
        if xp:
            pid = self._player_id()
            if pid:
                self.player_update_stat("xp", xp)
                print(f"  {G_}+{RS} {B}{xp}{RS} XP")
        return True

    # ─────────────────────────────────────────────
    # Custom stat domain (player node)
    # ─────────────────────────────────────────────

    def _player_data(self, w: dict) -> Optional[dict]:
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return None
        return w["nodes"][pid].get("data", {})

    def custom_stat_get(self, stat_name: str) -> Optional[dict]:
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return None
        node = self.get_node(pid)
        cs = node.get("data", {}).get("custom_stats", {})
        return cs.get(stat_name)

    def custom_stat_set(self, stat_name: str, delta: float = None, absolute: float = None, reason: str = "") -> bool:
        B, RS, C, G, R = Colors.B, Colors.RESET, Colors.C, Colors.G, Colors.R
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        w = self._load()
        d = w["nodes"][pid].get("data", {})
        cs = d.setdefault("custom_stats", {})
        if stat_name not in cs:
            print(f"  Stat '{stat_name}' not found", file=sys.stderr)
            return False
        stat = cs[stat_name]
        old_val = round(stat.get("value", 0), 2)
        if absolute is not None:
            new_val = round(float(absolute), 2)
        elif delta is not None:
            new_val = round(old_val + delta, 2)
        else:
            print("  Provide delta or absolute", file=sys.stderr)
            return False
        mn = stat.get("min", 0)
        mx = stat.get("max")
        if mn is not None:
            new_val = max(mn, new_val)
        if mx is not None:
            new_val = min(mx, new_val)
        new_val = round(new_val, 2)
        stat["value"] = new_val
        w["nodes"][pid]["data"] = d
        ok = self._save(w)
        if ok:
            diff = round(new_val - old_val, 2)
            color = G if diff < 0 else R if diff > 0 else C
            reason_str = f"  — {reason}" if reason else ""
            print(f"  📊 {stat_name}: {old_val} → {C}{new_val}{RS} {color}({diff:+g}){RS}{reason_str}")
        return ok

    def custom_stat_list(self) -> List[dict]:
        B, RS, C, G, R, DM, Y = Colors.B, Colors.RESET, Colors.C, Colors.G, Colors.R, Colors.DIM, Colors.Y
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return []
        node = self.get_node(pid)
        cs = node.get("data", {}).get("custom_stats", {})
        if not cs:
            print(f"  {DM}(no custom stats){RS}")
            return []
        print(f"  {B}📊 CUSTOM STATS:{RS}")
        result = []
        for name, stat in cs.items():
            val = stat.get("value", 0)
            mx = stat.get("max")
            mn = stat.get("min", 0)
            rate = stat.get("rate", 0)
            sleep_rate = stat.get("sleep_rate")
            if mx:
                bar_len = 20
                pct = (val - mn) / (mx - mn) if mx != mn else 0
                fill = int(pct * bar_len)
                bar_color = G if pct < 0.3 else Y if pct < 0.7 else R
                bar = f"{bar_color}{'█' * fill}{DM}{'░' * (bar_len - fill)}{RS}"
                rate_str = f"  {DM}rate:{rate:+g}/h{RS}" if rate else ""
                sleep_str = f"  {DM}sleep:{sleep_rate:+g}/h{RS}" if sleep_rate is not None else ""
                print(f"  {name:16s} {bar} {C}{val:.1f}{RS}/{mx}{rate_str}{sleep_str}")
            else:
                print(f"  {name}: {C}{val}{RS}")
            result.append({"name": name, **stat})
        return result

    def custom_stat_define(self, stat_name: str, value: float = 0,
                           max: float = 100, min: float = 0,
                           max_val: float = None, min_val: float = None,
                           rate: float = 0, sleep_rate: float = None) -> bool:
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        resolved_max = max_val if max_val is not None else max
        resolved_min = min_val if min_val is not None else min
        w = self._load()
        d = w["nodes"][pid].get("data", {})
        cs = d.setdefault("custom_stats", {})
        entry: dict = {"value": value, "max": resolved_max, "min": resolved_min, "rate": rate}
        if sleep_rate is not None:
            entry["sleep_rate"] = sleep_rate
        cs[stat_name] = entry
        w["nodes"][pid]["data"] = d
        ok = self._save(w)
        if ok:
            print(f"  ✓ Defined stat: {stat_name} = {value} (max {resolved_max}, rate {rate:+g}/h)")
        return ok

    # ─────────────────────────────────────────────
    # Timed effects (player node)
    # ─────────────────────────────────────────────

    def timed_effect_add(self, name: str, stat: str = None, rate_mod: float = 0,
                         instant: float = 0, hours: float = 1) -> bool:
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return False
        w = self._load()
        d = w["nodes"][pid].get("data", {})
        effects = d.setdefault("timed_effects", [])
        effect: dict = {"name": name, "hours_left": hours}
        if stat:
            effect["stat"] = stat
        if rate_mod:
            effect["rate_mod"] = rate_mod
        if instant:
            effect["instant"] = instant
            if stat:
                cs = d.get("custom_stats", {}).get(stat)
                if cs:
                    old = cs.get("value", 0)
                    new_v = round(old + instant, 2)
                    mn = cs.get("min", 0)
                    mx = cs.get("max")
                    if mn is not None:
                        new_v = max(mn, new_v)
                    if mx is not None:
                        new_v = min(mx, new_v)
                    cs["value"] = round(new_v, 2)
        effects.append(effect)
        w["nodes"][pid]["data"] = d
        ok = self._save(w)
        if ok:
            print(f"  ✓ Timed effect '{name}': {hours}h" +
                  (f", {stat} rate_mod {rate_mod:+g}/h" if rate_mod and stat else "") +
                  (f", instant {instant:+g}" if instant else ""))
        return ok

    def timed_effect_list(self) -> List[dict]:
        B, RS, C, DM, G, Y, R = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.G, Colors.Y, Colors.R
        pid = self._player_id()
        if not pid:
            print("  No player node found", file=sys.stderr)
            return []
        node = self.get_node(pid)
        effects = node.get("data", {}).get("timed_effects", [])
        if not effects:
            print(f"  {DM}(no active timed effects){RS}")
            return []
        print(f"  {B}✦ Timed Effects:{RS}")
        for eff in effects:
            hrs = eff.get("hours_left", 0)
            color = G if hrs > 2 else Y if hrs > 0.5 else R
            parts = []
            if eff.get("stat"):
                parts.append(f"{C}{eff['stat']}{RS}")
            if eff.get("rate_mod"):
                v = eff["rate_mod"]
                parts.append(f"rate_mod {'+' if v > 0 else ''}{v:g}/h")
            if eff.get("instant"):
                parts.append(f"instant {eff['instant']:+g}")
            detail = "  " + " ".join(parts) if parts else ""
            print(f"  {B}{eff['name']:<22}{RS} {color}{hrs:.1f}h{RS}{detail}")
        return effects

    # ─────────────────────────────────────────────
    # Tick engine
    # ─────────────────────────────────────────────

    def _tick_custom_stats(self, w: dict, elapsed_hours: float, sleeping: bool) -> List[dict]:
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid].get("data", {})
        cs = d.get("custom_stats", {})
        if not cs:
            return []

        effects = d.get("timed_effects", [])
        rate_mods: Dict[str, float] = {}
        for eff in effects:
            if eff.get("hours_left", 0) > 0 and eff.get("stat") and eff.get("rate_mod"):
                rate_mods[eff["stat"]] = rate_mods.get(eff["stat"], 0) + eff["rate_mod"]

        changes = []
        for name, stat in cs.items():
            base_rate = stat.get("sleep_rate", stat.get("rate", 0)) if sleeping else stat.get("rate", 0)
            effective_rate = base_rate + rate_mods.get(name, 0)
            if abs(effective_rate) < 0.0001:
                continue
            old_val = round(stat.get("value", 0), 2)
            raw_change = round(effective_rate * elapsed_hours, 4)
            new_val = round(old_val + raw_change, 4)
            mn = stat.get("min", 0)
            mx = stat.get("max")
            if mn is not None:
                new_val = max(mn, new_val)
            if mx is not None:
                new_val = min(mx, new_val)
            new_val = round(new_val, 2)
            actual_change = round(new_val - old_val, 2)
            if abs(actual_change) < 0.001:
                continue
            stat["value"] = new_val
            changes.append({"stat": name, "old": old_val, "new": new_val, "change": actual_change})

        return changes

    def _tick_timed_effects(self, w: dict, elapsed_hours: float) -> List[str]:
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid].get("data", {})
        effects = d.get("timed_effects", [])
        if not effects:
            return []
        expired = []
        surviving = []
        for eff in effects:
            eff["hours_left"] = round(eff.get("hours_left", 0) - elapsed_hours, 4)
            if eff["hours_left"] <= 0:
                expired.append(eff["name"])
            else:
                surviving.append(eff)
        d["timed_effects"] = surviving
        return expired

    def _check_stat_thresholds(self, w: dict) -> List[dict]:
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid].get("data", {})
        cs = d.get("custom_stats", {})
        thresholds = d.get("stat_thresholds", {})
        warnings = []
        for stat_name, stat in cs.items():
            val = stat.get("value", 0)
            mn = stat.get("min")
            mx = stat.get("max")
            if mn is not None and val <= mn:
                warnings.append({"stat": stat_name, "msg": f"{stat_name} at minimum ({mn})"})
            if mx is not None and val >= mx:
                warnings.append({"stat": stat_name, "msg": f"{stat_name} at maximum ({mx})"})
        for stat_name, checks in thresholds.items():
            val = cs.get(stat_name, {}).get("value", 0) if stat_name in cs else None
            if val is None:
                continue
            for check in checks:
                at = check.get("at", 0)
                direction = check.get("direction", "above")
                effect = check.get("effect", "")
                triggered = (direction == "above" and val >= at) or (direction == "below" and val <= at)
                if triggered:
                    warnings.append({"stat": stat_name, "msg": f"{stat_name} {direction} {at}: {effect}"})
        return warnings

    def _tick_production(self, w: dict, elapsed_hours: float) -> dict:
        def _roll(expr: str) -> int:
            try:
                from dice import roll as _dice_roll
                return _dice_roll(str(expr))
            except Exception:
                m = re.match(r"(\d+)d(\d+)([+-]\d+)?", str(expr).lower())
                if m:
                    n, d_, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                    return sum(random.randint(1, d_) for _ in range(n)) + mod
                return int(expr)

        results: dict = {}
        for nid, node in w["nodes"].items():
            if node.get("type") != "location":
                continue
            productions = node.get("data", {}).get("production", [])
            if not productions:
                continue
            loc_results = []
            for prod in productions:
                interval = prod.get("interval_hours", 0)
                if interval > 0:
                    acc_key = "_acc_hours"
                    prod[acc_key] = prod.get(acc_key, 0) + elapsed_hours
                    triggers = int(prod[acc_key] / interval)
                    if triggers < 1:
                        continue
                    prod[acc_key] = prod[acc_key] % interval
                else:
                    triggers = 1 if elapsed_hours > 0 else 0
                    if triggers < 1:
                        continue

                worker = prod.get("worker", "?")
                qty_dice = prod.get("qty_dice", "1")
                item = prod.get("item", "?")
                dc = prod.get("skill_dc", 0)
                bonus = prod.get("skill_bonus", 0)
                target_id = prod.get("inventory_target")
                consumes: dict = prod.get("consumes", {})

                for _ in range(triggers):
                    qty = _roll(str(qty_dice))
                    raw = random.randint(1, 20)
                    total = raw + bonus
                    success = total >= dc if dc else True
                    outcome = "success" if success else "fail"

                    if success:
                        produced = {item: qty}
                        consumed = dict(consumes)
                        if target_id and target_id in w["nodes"]:
                            w["nodes"][target_id].setdefault("inventory", {"stackable": {}, "unique": []})
                            inv = w["nodes"][target_id]["inventory"]["stackable"]
                            inv.setdefault(item, {"qty": 0, "weight": 0.5})
                            inv[item]["qty"] += qty
                            for ci, cq in consumes.items():
                                if ci in inv:
                                    inv[ci]["qty"] = max(0, inv[ci].get("qty", 0) - cq)
                    else:
                        produced = {}
                        consumed = {}

                    loc_results.append({
                        "worker": worker,
                        "item": item,
                        "qty": qty,
                        "raw": raw,
                        "bonus": bonus,
                        "total": total,
                        "dc": dc,
                        "outcome": outcome,
                        "produced": produced,
                        "consumed": consumed,
                        "target": target_id,
                    })
            if loc_results:
                results[nid] = loc_results
        return results

    def _tick_expenses(self, w: dict, elapsed_hours: float) -> List[dict]:
        economy_id = "campaign:economy"
        if economy_id not in w["nodes"]:
            return []
        econ = w["nodes"][economy_id].get("data", {})
        expenses = econ.get("expenses", [])
        if not expenses:
            return []
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid]["data"]
        money = d.get("money", 0)

        try:
            from currency import load_config as _lc, format_money as _fm
            cfg = _lc(self.campaign_dir)
        except Exception:
            cfg = None
            def _fm(amount, conf=None, **kw):
                return f"{amount}c"

        results = []
        for exp in expenses:
            exp["_acc"] = exp.get("_acc", 0) + elapsed_hours
            per_hours = exp.get("per_hours", 24)
            triggers = int(exp["_acc"] / per_hours)
            if triggers < 1:
                continue
            exp["_acc"] = exp["_acc"] % per_hours
            cost = exp.get("cost", 0) * triggers
            name = exp.get("name", "?")
            if money >= cost:
                money -= cost
                results.append({"name": name, "cost": cost, "success": True, "remaining": money,
                                 "cfg": cfg, "fmt": _fm})
            else:
                results.append({"name": name, "cost": cost, "success": False, "remaining": money,
                                 "cfg": cfg, "fmt": _fm})

        d["money"] = money
        return results

    def _tick_income(self, w: dict, elapsed_hours: float) -> List[dict]:
        economy_id = "campaign:economy"
        if economy_id not in w["nodes"]:
            return []
        econ = w["nodes"][economy_id].get("data", {})
        incomes = econ.get("income", [])
        if not incomes:
            return []
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid]["data"]
        money = d.get("money", 0)

        def _roll(expr: str) -> int:
            try:
                from dice import roll as _dice_roll
                return _dice_roll(str(expr))
            except Exception:
                m = re.match(r"(\d+)d(\d+)([+-]\d+)?", str(expr).lower())
                if m:
                    n, s, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                    return sum(random.randint(1, s) for _ in range(n)) + mod
                return int(expr)

        try:
            from currency import load_config as _lc, format_money as _fm
            cfg = _lc(self.campaign_dir)
        except Exception:
            cfg = None
            def _fm(amount, conf=None, **kw):
                return f"{amount}c"

        results = []
        for inc in incomes:
            inc["_acc"] = inc.get("_acc", 0) + elapsed_hours
            per_hours = inc.get("per_hours", 24)
            triggers = int(inc["_acc"] / per_hours)
            if triggers < 1:
                continue
            inc["_acc"] = inc["_acc"] % per_hours

            name = inc.get("name", "?")
            dice_expr = inc.get("dice", "")
            dc = inc.get("dc")
            pay_success = inc.get("pay_success", 0)
            pay_fail = inc.get("pay_fail", 0)

            for _ in range(triggers):
                if dice_expr and dc is not None:
                    raw = random.randint(1, 20)
                    modifier = int(re.search(r"[+-]\d+", dice_expr).group()) if re.search(r"[+-]\d+", dice_expr) else 0
                    total = raw + modifier
                    success = total >= dc
                    earned = pay_success if success else pay_fail
                    detail = f"🎲[{raw}]{modifier:+g}={total} vs DC {dc} — {'✓ SUCCESS' if success else '✗ FAIL'}"
                elif dice_expr:
                    earned = _roll(dice_expr)
                    detail = f"🎲{dice_expr}={earned}"
                else:
                    earned = inc.get("amount", 0)
                    detail = ""

                money += earned
                results.append({"name": name, "earned": earned, "detail": detail,
                                 "remaining": money, "cfg": cfg, "fmt": _fm})

        d["money"] = money
        return results

    def _tick_random_events(self, w: dict, elapsed_hours: float) -> List[dict]:
        economy_id = "campaign:economy"
        if economy_id not in w["nodes"]:
            return []
        econ = w["nodes"][economy_id].get("data", {})
        re_cfg = econ.get("random_events", {})
        if not re_cfg or not re_cfg.get("enabled"):
            return []

        days = elapsed_hours / 24.0
        chance = re_cfg.get("chance_per_day", 10) * days
        if random.random() * 100 > chance:
            return []

        types = re_cfg.get("types", {"neutral": 100})
        pool = []
        for t, w_ in types.items():
            pool.extend([t] * int(w_))
        if not pool:
            return []
        chosen = random.choice(pool)
        scope_roll = random.randint(1, 6)
        return [{"type": chosen, "scope_roll": scope_roll, "roll": random.randint(1, 100)}]

    def _tick_consequences_elapsed(self, w: dict, elapsed_hours: float) -> List[dict]:
        triggered = []
        for nid, node in w["nodes"].items():
            if node.get("type") != "consequence":
                continue
            d = node.get("data", {})
            if "hours_elapsed" not in d and "trigger_hours" not in d:
                continue
            d["hours_elapsed"] = round(d.get("hours_elapsed", 0) + elapsed_hours, 4)
            trigger_hours = d.get("trigger_hours")
            if trigger_hours is not None and d["hours_elapsed"] >= trigger_hours:
                d["status"] = d.get("status", "triggered")
                triggered.append({"id": nid, **node})
        return triggered

    def _find_economy_node(self, w: dict) -> Optional[dict]:
        for nid, node in w["nodes"].items():
            if "economy" in nid.lower():
                return node.get("data", {})
        return None

    def _tick_expenses_from_world(self, w: dict, elapsed_hours: float) -> List[dict]:
        econ = self._find_economy_node(w)
        if not econ:
            return []
        expenses = econ.get("expenses", [])
        if not expenses:
            return []
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid]["data"]
        money = d.get("money", 0)

        try:
            from currency import load_config as _lc, format_money as _fm
            cfg = _lc(self.campaign_dir)
        except Exception:
            cfg = None
            def _fm(amount, conf=None, **kw):
                return f"{amount}c"

        results = []
        for exp in expenses:
            exp["_acc"] = exp.get("_acc", 0) + elapsed_hours
            interval = exp.get("interval_hours", exp.get("per_hours", 24))
            triggers = int(exp["_acc"] / interval)
            if triggers < 1:
                continue
            exp["_acc"] = exp["_acc"] % interval
            cost_per = exp.get("amount", exp.get("cost", 0))
            cost = cost_per * triggers
            name = exp.get("name", "?")
            if money >= cost:
                money -= cost
                results.append({"name": name, "cost": cost, "success": True,
                                 "remaining": money, "cfg": cfg, "fmt": _fm})
            else:
                results.append({"name": name, "cost": cost, "success": False,
                                 "remaining": money, "cfg": cfg, "fmt": _fm})

        d["money"] = money
        return results

    def _tick_income_from_world(self, w: dict, elapsed_hours: float) -> List[dict]:
        econ = self._find_economy_node(w)
        if not econ:
            return []
        incomes = econ.get("income", [])
        if not incomes:
            return []
        pid = self._player_id()
        if not pid or pid not in w["nodes"]:
            return []
        d = w["nodes"][pid]["data"]
        money = d.get("money", 0)

        def _roll(expr: str) -> int:
            try:
                from dice import roll as _dice_roll
                return _dice_roll(str(expr))
            except Exception:
                m = re.match(r"(\d+)d(\d+)([+-]\d+)?", str(expr).lower())
                if m:
                    n, s, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                    return sum(random.randint(1, s) for _ in range(n)) + mod
                return int(expr)

        try:
            from currency import load_config as _lc, format_money as _fm
            cfg = _lc(self.campaign_dir)
        except Exception:
            cfg = None
            def _fm(amount, conf=None, **kw):
                return f"{amount}c"

        results = []
        for inc in incomes:
            inc["_acc"] = inc.get("_acc", 0) + elapsed_hours
            per_hours = inc.get("per_hours", inc.get("interval_hours", 24))
            triggers = int(inc["_acc"] / per_hours)
            if triggers < 1:
                continue
            inc["_acc"] = inc["_acc"] % per_hours
            name = inc.get("name", "?")
            dice_expr = inc.get("dice", "")
            dc = inc.get("dc")
            pay_success = inc.get("pay_success", 0)
            pay_fail = inc.get("pay_fail", 0)

            for _ in range(triggers):
                if dice_expr and dc is not None:
                    raw = random.randint(1, 20)
                    modifier = 0
                    m = re.search(r"[+-]\d+", dice_expr)
                    if m:
                        modifier = int(m.group())
                    total = raw + modifier
                    success = total >= dc
                    earned = pay_success if success else pay_fail
                    detail = f"🎲[{raw}]{modifier:+g}={total} vs DC {dc} — {'✓ SUCCESS' if success else '✗ FAIL'}"
                elif dice_expr:
                    earned = _roll(dice_expr)
                    detail = f"🎲{dice_expr}={earned}"
                else:
                    earned = inc.get("amount", 0)
                    detail = ""
                money += earned
                results.append({"name": name, "earned": earned, "detail": detail,
                                 "remaining": money, "cfg": cfg, "fmt": _fm})

        d["money"] = money
        return results

    def _tick_random_events_from_world(self, w: dict, elapsed_hours: float) -> List[dict]:
        econ = self._find_economy_node(w)
        if not econ:
            return []
        re_cfg = econ.get("random_events", {})
        if not re_cfg or not re_cfg.get("enabled"):
            return []
        days = elapsed_hours / 24.0
        chance = re_cfg.get("chance_per_day", 10) * days
        if random.random() * 100 > chance:
            return []
        types = re_cfg.get("types", {"neutral": 100})
        pool = []
        for t, wt in types.items():
            pool.extend([t] * int(wt))
        if not pool:
            return []
        chosen = random.choice(pool)
        return [{"type": chosen, "scope_roll": random.randint(1, 6),
                 "roll": random.randint(1, 100)}]

    def tick(self, elapsed_hours: float, sleeping: bool = False) -> dict:
        B, RS, C, G, R, Y, DM = Colors.B, Colors.RESET, Colors.C, Colors.G, Colors.R, Colors.Y, Colors.DIM
        w = self._load()

        stat_changes_list = self._tick_custom_stats(w, elapsed_hours, sleeping)
        expired_effects = self._tick_timed_effects(w, elapsed_hours)
        production = self._tick_production(w, elapsed_hours)
        self._tick_consequences_elapsed(w, elapsed_hours)
        expenses = self._tick_expenses_from_world(w, elapsed_hours)
        income = self._tick_income_from_world(w, elapsed_hours)
        events = self._tick_random_events_from_world(w, elapsed_hours)
        threshold_warnings = self._check_stat_thresholds(w)
        self._save(w)

        consequences_triggered = self.consequence_tick(elapsed_hours)

        stat_changes: dict = {ch["stat"]: ch for ch in stat_changes_list}

        if stat_changes_list:
            print(f"\n{B}⏱️  Survival Effects:{RS}")
            for ch in stat_changes_list:
                diff = ch["change"]
                color = R if diff > 0 else G
                print(f"  📊 {ch['stat']}: {ch['old']} → {C}{ch['new']}{RS} {color}({diff:+g}){RS} — decay")

        if expired_effects:
            for name in expired_effects:
                print(f"  {DM}[EXPIRED]{RS} effect '{name}' has worn off")

        if threshold_warnings:
            print(f"\n{B}⚠️  Threshold Warnings:{RS}")
            for warn in threshold_warnings:
                print(f"  {Y}⚠{RS} {warn['msg']}")

        if production:
            print(f"\n{B}🏭 Production:{RS}")
            for loc_id, prods in production.items():
                for p in prods:
                    color = G if p["outcome"] == "success" else R
                    mark = "✓" if p["outcome"] == "success" else "✗"
                    dc_str = f" vs DC {p['dc']}" if p["dc"] else ""
                    print(f"  {mark} {p['worker']}: 🎲[{p['raw']}]+{p['bonus']}={p['total']}{dc_str} — {color}{p['outcome'].upper()}{RS}")
                    for item, qty in p["produced"].items():
                        print(f"     {G}+{qty}{RS} {item}")
                    for item, qty in p["consumed"].items():
                        print(f"     {R}-{qty}{RS} {item}")

        if income:
            print(f"\n{B}💰 Recurring Income:{RS}")
            for inc in income:
                _fm = inc["fmt"]
                cfg = inc["cfg"]
                amt_str = _fm(inc["earned"], cfg)
                rem_str = _fm(inc["remaining"], cfg)
                detail = f" {inc['detail']}" if inc.get("detail") else ""
                print(f"  💰 {inc['name']}: {G}+{amt_str}{RS}{detail} {DM}({C}{rem_str}{RS}{DM} remaining){RS}")

        if expenses:
            print(f"\n{B}🍞 Recurring Expenses:{RS}")
            for exp in expenses:
                _fm = exp["fmt"]
                cfg = exp["cfg"]
                cost_str = _fm(exp["cost"], cfg)
                rem_str = _fm(exp["remaining"], cfg)
                if exp["success"]:
                    print(f"  🍞 {exp['name']}: {R}-{cost_str}{RS} {DM}({C}{rem_str}{RS}{DM} remaining){RS}")
                else:
                    print(f"  {Y}⚠{RS} {exp['name']}: НЕ ХВАТАЕТ! Нужно {cost_str}, есть {rem_str}")

        if consequences_triggered:
            print(f"\n{B}⚠️  Consequences Triggered:{RS}")
            for con in consequences_triggered:
                print(f"  {R}[{con['id']}]{RS} {con['data'].get('description', '')} → {con['data'].get('trigger', '')}")

        if events:
            print(f"\n{B}🎲 Random Events:{RS}")
            for ev in events:
                print(f"  {Y}{ev['type'].upper()}{RS} (d100={ev['roll']}, scope d6={ev['scope_roll']})")
                print(f"  {DM}[DM: narrate based on event type above]{RS}")

        return {
            "stat_changes": stat_changes,
            "expired_effects": expired_effects,
            "expenses_paid": [e for e in expenses if e["success"]],
            "production": production,
            "income": income,
            "events": events,
            "warnings": threshold_warnings,
            "consequences": consequences_triggered,
        }

    def wiki_recipe(self, entity_id: str) -> str:
        B, RS, C, DM, G = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.G
        node = self.get_node(entity_id)
        if not node:
            return f"  '{entity_id}' not found"
        name = node.get("name", entity_id)
        recipe_data = node.get("data", {}).get("recipe", {})
        lines = [f"  {B}Recipe: {name}{RS}"]
        if recipe_data.get("dc"):
            lines.append(f"  DC {C}{recipe_data['dc']}{RS}  skill: {recipe_data.get('skill', 'any')}")
        w = self._load()
        req_edges = [e for e in w["edges"]
                     if e["from"] == entity_id and e["type"] == "requires"]
        if req_edges:
            lines.append(f"  {B}Ingredients:{RS}")
            for e in req_edges:
                ing = w["nodes"].get(e["to"], {})
                qty = e.get("data", {}).get("qty", 1) if e.get("data") else 1
                lines.append(f"    {G}•{RS} {ing.get('name', e['to'])} {C}x{qty}{RS}  {DM}{e['to']}{RS}")
        elif not recipe_data:
            lines.append(f"  {DM}(no recipe){RS}")
        mechanics = node.get("data", {}).get("mechanics", {})
        if mechanics:
            lines.append(f"  {B}Mechanics:{RS}")
            for k, v in mechanics.items():
                lines.append(f"    {k}: {C}{v}{RS}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="World graph — unified entity manager")
    sub = parser.add_subparsers(dest="command")

    # ── Low-level graph primitives ────────────────────────────────────────────
    p = sub.add_parser("add-node", help="Add a node")
    p.add_argument("id", help="Node ID in format type:kebab-name")
    p.add_argument("--name", required=True, help="Display name (Unicode allowed)")
    p.add_argument("--type", choices=NODE_TYPES, required=True, dest="node_type")
    p.add_argument("--data", default="{}", help="JSON data dict")

    p = sub.add_parser("get-node", help="Show a node")
    p.add_argument("id")

    p = sub.add_parser("update-node", help="Update node data")
    p.add_argument("id")
    p.add_argument("--data", required=True, help="JSON updates dict")

    p = sub.add_parser("remove-node", help="Remove a node")
    p.add_argument("id")
    p.add_argument("--no-cascade", action="store_true", help="Do not remove attached edges")

    p = sub.add_parser("list-nodes", help="List nodes")
    p.add_argument("--type", choices=NODE_TYPES, dest="node_type")

    p = sub.add_parser("search", help="Search nodes by name or data")
    p.add_argument("query")
    p.add_argument("--type", choices=NODE_TYPES, dest="node_type")

    p = sub.add_parser("add-edge", help="Add a directed edge")
    p.add_argument("from_id")
    p.add_argument("to_id")
    p.add_argument("edge_type", choices=EDGE_TYPES)
    p.add_argument("--data", default="{}", help="JSON data dict")

    p = sub.add_parser("get-edges", help="Get edges for a node")
    p.add_argument("node_id")
    p.add_argument("--type", dest="edge_type")
    p.add_argument("--direction", choices=["in", "out", "both"], default="both")

    p = sub.add_parser("remove-edge", help="Remove an edge")
    p.add_argument("from_id")
    p.add_argument("to_id")
    p.add_argument("edge_type")

    p = sub.add_parser("neighbors", help="Get neighboring nodes")
    p.add_argument("node_id")
    p.add_argument("--type", dest="edge_type")
    p.add_argument("--direction", choices=["in", "out", "both"], default="out")

    sub.add_parser("stats", help="Node and edge counts by type")

    # ── NPC ──────────────────────────────────────────────────────────────────
    p = sub.add_parser("npc-create", help="Create NPC node")
    p.add_argument("name")
    p.add_argument("description")
    p.add_argument("--attitude", default="neutral")

    p = sub.add_parser("npc-event", help="Append event to NPC")
    p.add_argument("id", help="NPC name or ID")
    p.add_argument("text")

    sub.add_parser("npc-list", help="List all NPCs")

    p = sub.add_parser("npc-show", help="Show NPC details")
    p.add_argument("id", help="NPC name or ID")

    p = sub.add_parser("npc-promote", help="Promote NPC to party member")
    p.add_argument("id", help="NPC name or ID")

    p = sub.add_parser("npc-locate", help="Set NPC location")
    p.add_argument("id", help="NPC name or ID")
    p.add_argument("location", help="Location name or ID")

    # ── Location ─────────────────────────────────────────────────────────────
    p = sub.add_parser("location-create", help="Create location node")
    p.add_argument("name")
    p.add_argument("--desc", default="")

    p = sub.add_parser("location-connect", help="Connect two locations bidirectionally")
    p.add_argument("from_loc", help="Location name or ID")
    p.add_argument("to_loc", help="Location name or ID")
    p.add_argument("--path", default="traveled", dest="path_type")

    sub.add_parser("location-list", help="List all locations")

    p = sub.add_parser("location-show", help="Show location details")
    p.add_argument("id", help="Location name or ID")

    # ── Fact ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("fact-add", help="Add a fact node")
    p.add_argument("category")
    p.add_argument("text")

    p = sub.add_parser("fact-list", help="List facts")
    p.add_argument("--category", default=None)

    p = sub.add_parser("fact-search", help="Search facts")
    p.add_argument("query")

    # ── Quest ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("quest-create", help="Create quest node")
    p.add_argument("name")
    p.add_argument("--type", default="side", dest="quest_type")
    p.add_argument("--desc", default="")

    p = sub.add_parser("quest-list", help="List quests")
    p.add_argument("--status", default=None, help="Filter by status: active/completed/failed")

    p = sub.add_parser("quest-show", help="Show quest details")
    p.add_argument("id", help="Quest name or ID")

    p = sub.add_parser("quest-objective", help="Manage quest objectives")
    p.add_argument("quest_id", help="Quest name or ID")
    p.add_argument("action", choices=["add", "complete"])
    p.add_argument("value", help="Text for add, index number for complete")

    p = sub.add_parser("quest-complete", help="Mark quest as completed")
    p.add_argument("id", help="Quest name or ID")

    p = sub.add_parser("quest-fail", help="Mark quest as failed")
    p.add_argument("id", help="Quest name or ID")

    # ── Consequence ───────────────────────────────────────────────────────────
    p = sub.add_parser("consequence-add", help="Add a consequence")
    p.add_argument("description")
    p.add_argument("trigger")
    p.add_argument("--hours", type=float, default=None)

    sub.add_parser("consequence-check", help="Show all pending/triggered consequences")

    p = sub.add_parser("consequence-resolve", help="Resolve a consequence")
    p.add_argument("id", help="Consequence name or ID")
    p.add_argument("resolution", nargs="?", default="")

    # ── Inventory ─────────────────────────────────────────────────────────────
    p = sub.add_parser("inventory-show", help="Show inventory of a node")
    p.add_argument("owner", help="Node name or ID")

    p = sub.add_parser("inventory-add", help="Add stackable item to node")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("item")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--weight", type=float, default=0.5)

    p = sub.add_parser("inventory-add-unique", help="Add unique item to node")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("item_desc")

    p = sub.add_parser("inventory-remove", help="Remove stackable item from node")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("item")
    p.add_argument("--qty", type=int, default=1)

    p = sub.add_parser("inventory-transfer", help="Transfer item between nodes")
    p.add_argument("from_owner", help="Source node name or ID")
    p.add_argument("to_owner", help="Target node name or ID")
    p.add_argument("item")
    p.add_argument("--qty", type=int, default=1)

    # ── Player ────────────────────────────────────────────────────────────────
    sub.add_parser("player-show", help="Show player character sheet")

    p = sub.add_parser("player-hp", help="Adjust player HP by delta")
    p.add_argument("delta", type=int)

    p = sub.add_parser("player-xp", help="Adjust player XP by delta")
    p.add_argument("delta", type=int)

    p = sub.add_parser("player-gold", help="Adjust player gold by delta")
    p.add_argument("delta", type=int)

    p = sub.add_parser("player-hp-max", help="Adjust player max HP by delta")
    p.add_argument("delta", type=int)

    p = sub.add_parser("player-condition", help="Manage player conditions")
    p.add_argument("action", choices=["add", "remove", "list"])
    p.add_argument("condition", nargs="?", default=None)

    p = sub.add_parser("player-set", help="Set active character in campaign-overview.json")
    p.add_argument("name")

    # ── Inventory extended ────────────────────────────────────────────────────
    p = sub.add_parser("inventory-craft", help="Craft item from recipe")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("recipe_id", help="Recipe node ID or name")
    p.add_argument("--qty", type=int, default=1)

    p = sub.add_parser("inventory-use", help="Use a consumable item")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("item")

    p = sub.add_parser("inventory-loot", help="Batch add items + gold + xp")
    p.add_argument("owner", help="Node name or ID")
    p.add_argument("--items", nargs="+", metavar="name:qty:weight",
                   help="Items in format name:qty:weight (qty and weight optional)")
    p.add_argument("--gold", type=int, default=0)
    p.add_argument("--xp", type=int, default=0)

    sub.add_parser("consequence-list-resolved", help="List resolved consequences")

    # ── Wiki ──────────────────────────────────────────────────────────────────
    p = sub.add_parser("wiki-add", help="Add entity to wiki")
    p.add_argument("id", help="Entity ID (slug, without type prefix)")
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, choices=NODE_TYPES, dest="wiki_type")
    p.add_argument("--stat", action="append", default=[], metavar="key:val",
                   help="Mechanic stat (repeatable)")
    p.add_argument("--ingredient", action="append", default=[], metavar="id:qty",
                   help="Recipe ingredient (repeatable)")
    p.add_argument("--dc", type=int, default=None, help="Craft DC")
    p.add_argument("--skill", default=None, help="Craft skill")

    p = sub.add_parser("wiki-show", help="Show wiki entity with recipe")
    p.add_argument("id")

    p = sub.add_parser("wiki-list", help="List wiki entities")
    p.add_argument("--type", dest="wiki_type", default=None, choices=NODE_TYPES)

    p = sub.add_parser("wiki-search", help="Search wiki")
    p.add_argument("query")

    p = sub.add_parser("wiki-remove", help="Remove wiki entity")
    p.add_argument("id")

    # ── Tick / Custom stats ───────────────────────────────────────────────────
    p = sub.add_parser("tick", help="Advance time and tick all systems")
    p.add_argument("--elapsed", type=float, required=True, help="Hours elapsed")
    p.add_argument("--sleeping", action="store_true", help="Use sleep rates for stats")

    p = sub.add_parser("custom-stat", help="Get or modify a custom stat")
    p.add_argument("name", help="Stat name")
    p.add_argument("delta", nargs="?", default=None, help="Delta value (+/-N) or absolute (=N)")
    p.add_argument("--reason", default="", help="Reason for the change")

    sub.add_parser("custom-stat-list", help="List all custom stats")

    p = sub.add_parser("custom-stat-define", help="Define a new custom stat")
    p.add_argument("name", help="Stat name")
    p.add_argument("--value", type=float, default=0)
    p.add_argument("--max", type=float, default=100, dest="max_val")
    p.add_argument("--min", type=float, default=0, dest="min_val")
    p.add_argument("--rate", type=float, default=0)
    p.add_argument("--sleep-rate", type=float, default=None, dest="sleep_rate")

    p = sub.add_parser("timed-effect-add", help="Add a timed effect to player")
    p.add_argument("name", help="Effect name")
    p.add_argument("--stat", default=None, help="Target stat")
    p.add_argument("--rate-mod", type=float, default=0, dest="rate_mod")
    p.add_argument("--instant", type=float, default=0)
    p.add_argument("--hours", type=float, default=1)

    sub.add_parser("timed-effect-list", help="List active timed effects")

    # ─────────────────────────────────────────────────────────────────────────
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    g = WorldGraph()

    def resolve(name_or_id: str, node_type: str = None) -> str:
        nid = g._resolve_id(name_or_id, node_type)
        if not nid:
            print(f"  Cannot resolve '{name_or_id}'", file=sys.stderr)
            sys.exit(1)
        return nid

    # ── Low-level handlers ───────────────────────────────────────────────────
    if args.command == "add-node":
        data = json.loads(args.data)
        ok = g.add_node(args.id, args.node_type, args.name, data)
        if ok:
            print(f"  ✓ Added: {args.name} ({args.id})")
        else:
            sys.exit(1)

    elif args.command == "get-node":
        print(g.format_node(args.id))

    elif args.command == "update-node":
        updates = json.loads(args.data)
        ok = g.update_node(args.id, updates)
        if ok:
            print(f"  ✓ Updated: {args.id}")
        else:
            sys.exit(1)

    elif args.command == "remove-node":
        ok = g.remove_node(args.id, cascade=not args.no_cascade)
        if ok:
            print(f"  ✓ Removed: {args.id}")
        else:
            sys.exit(1)

    elif args.command == "list-nodes":
        nodes = g.list_nodes(args.node_type)
        print(g.format_node_list(nodes))

    elif args.command == "search":
        results = g.search_nodes(args.query, args.node_type)
        if not results:
            print("  No results")
        else:
            for r in results[:15]:
                tcolor = TYPE_COLORS.get(r.get("type", ""), "")
                print(f"  {tcolor}[{r['type']}]{Colors.RESET} {r['name']}  {Colors.DIM}{r['id']}{Colors.RESET}")

    elif args.command == "add-edge":
        data = json.loads(args.data) if args.data != "{}" else None
        ok = g.add_edge(args.from_id, args.to_id, args.edge_type, data)
        if ok:
            print(f"  ✓ Edge: {args.from_id} -[{args.edge_type}]-> {args.to_id}")
        else:
            sys.exit(1)

    elif args.command == "get-edges":
        edges = g.get_edges(args.node_id, args.edge_type, args.direction)
        if not edges:
            print("  No edges")
        else:
            for e in edges:
                d = f"  {Colors.DIM}{e['data']}{Colors.RESET}" if e.get("data") else ""
                print(f"  {e['from']} -{Colors.C}[{e['type']}]{Colors.RESET}-> {e['to']}{d}")

    elif args.command == "remove-edge":
        ok = g.remove_edge(args.from_id, args.to_id, args.edge_type)
        if ok:
            print(f"  ✓ Removed edge: {args.from_id} -[{args.edge_type}]-> {args.to_id}")
        else:
            sys.exit(1)

    elif args.command == "neighbors":
        nodes = g.get_neighbors(args.node_id, args.edge_type, args.direction)
        if not nodes:
            print("  No neighbors")
        else:
            print(g.format_node_list(nodes))

    elif args.command == "stats":
        print(g.stats())

    # ── NPC handlers ─────────────────────────────────────────────────────────
    elif args.command == "npc-create":
        nid = g.npc_create(args.name, args.description, args.attitude)
        print(f"  ✓ NPC created: {args.name} ({nid})")

    elif args.command == "npc-event":
        nid = resolve(args.id, "npc")
        ok = g.npc_event(nid, args.text)
        if ok:
            print(f"  ✓ Event logged on {nid}")
        else:
            sys.exit(1)

    elif args.command == "npc-list":
        nodes = g.list_nodes("npc")
        B, RS, C, DM, G_ = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.BOLD_GREEN
        for n in nodes:
            att = n.get("data", {}).get("attitude", "")
            party = " [PARTY]" if n.get("data", {}).get("party_member") else ""
            print(f"  {G_}{n['name']}{RS}{party}  {DM}{n['id']}{RS}  {C}{att}{RS}")

    elif args.command == "npc-show":
        nid = resolve(args.id, "npc")
        print(g.format_node(nid))

    elif args.command == "npc-promote":
        nid = resolve(args.id, "npc")
        ok = g.npc_promote(nid)
        if ok:
            print(f"  ✓ Promoted {nid} to party member")
        else:
            sys.exit(1)

    elif args.command == "npc-locate":
        nid = resolve(args.id, "npc")
        lid = resolve(args.location, "location")
        ok = g.npc_locate(nid, lid)
        if ok:
            print(f"  ✓ {nid} → {lid}")
        else:
            sys.exit(1)

    # ── Location handlers ────────────────────────────────────────────────────
    elif args.command == "location-create":
        lid = g.location_create(args.name, args.desc)
        print(f"  ✓ Location created: {args.name} ({lid})")

    elif args.command == "location-connect":
        fid = resolve(args.from_loc, "location")
        tid = resolve(args.to_loc, "location")
        ok = g.location_connect(fid, tid, args.path_type)
        if ok:
            print(f"  ✓ Connected: {fid} ↔ {tid} [{args.path_type}]")
        else:
            sys.exit(1)

    elif args.command == "location-list":
        nodes = g.list_nodes("location")
        B, RS, Y, DM = Colors.B, Colors.RESET, Colors.BOLD_YELLOW, Colors.DIM
        for n in nodes:
            desc = n.get("data", {}).get("description", "")[:50]
            print(f"  {Y}{n['name']}{RS}  {DM}{n['id']}{RS}")
            if desc:
                print(f"    {DM}{desc}{RS}")

    elif args.command == "location-show":
        lid = resolve(args.id, "location")
        print(g.format_node(lid))

    # ── Fact handlers ────────────────────────────────────────────────────────
    elif args.command == "fact-add":
        fid = g.fact_add(args.category, args.text)
        print(f"  ✓ Fact added: {fid}")

    elif args.command == "fact-list":
        nodes = g.list_nodes("fact")
        DM, RS, C = Colors.DIM, Colors.RESET, Colors.C
        for n in nodes:
            cat = n.get("data", {}).get("category", "")
            text = n.get("data", {}).get("text", "")[:80]
            if args.category and cat != args.category:
                continue
            print(f"  {C}[{cat}]{RS} {text}  {DM}{n['id']}{RS}")

    elif args.command == "fact-search":
        results = g.search_nodes(args.query, "fact")
        DM, RS, C = Colors.DIM, Colors.RESET, Colors.C
        if not results:
            print("  No results")
        else:
            for r in results[:20]:
                text = r.get("data", {}).get("text", "")[:80]
                cat = r.get("data", {}).get("category", "")
                print(f"  {C}[{cat}]{RS} {text}  {DM}{r['id']}{RS}")

    # ── Quest handlers ────────────────────────────────────────────────────────
    elif args.command == "quest-create":
        qid = g.quest_create(args.name, args.quest_type, args.desc)
        print(f"  ✓ Quest created: {args.name} ({qid})")

    elif args.command == "quest-list":
        nodes = g.list_nodes("quest")
        B, RS, M, DM, C, G_ = Colors.B, Colors.RESET, Colors.MAGENTA, Colors.DIM, Colors.C, Colors.G
        for n in nodes:
            status = n.get("data", {}).get("status", "active")
            if args.status and status != args.status:
                continue
            objs = n.get("data", {}).get("objectives", [])
            done = sum(1 for o in objs if o.get("done"))
            marker = f"{G_}✓{RS}" if status == "completed" else (f"{Colors.R}✗{RS}" if status == "failed" else f"{M}●{RS}")
            progress = f" {C}({done}/{len(objs)}){RS}" if objs else ""
            print(f"  {marker} {B}{n['name']}{RS}{progress}  {DM}{n['id']}{RS}")

    elif args.command == "quest-show":
        qid = resolve(args.id, "quest")
        node = g.get_node(qid)
        if not node:
            print(f"  Quest '{qid}' not found")
            sys.exit(1)
        B, RS, C, DM, G_ = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.G
        d = node.get("data", {})
        print(f"\n  {B}{node['name']}{RS}  {DM}{qid}{RS}")
        print(f"  Status: {C}{d.get('status','active')}{RS}  Type: {d.get('quest_type','side')}")
        if d.get("description"):
            print(f"  {d['description']}")
        objs = d.get("objectives", [])
        if objs:
            print(f"  {B}Objectives:{RS}")
            for i, obj in enumerate(objs):
                mark = f"{G_}[x]{RS}" if obj.get("done") else "[ ]"
                print(f"    {i}. {mark} {obj['text']}")

    elif args.command == "quest-objective":
        qid = resolve(args.quest_id, "quest")
        if args.action == "add":
            ok = g.quest_objective_add(qid, args.value)
            if ok:
                print(f"  ✓ Objective added to {qid}")
            else:
                sys.exit(1)
        elif args.action == "complete":
            idx = int(args.value)
            ok = g.quest_objective_complete(qid, idx)
            if ok:
                print(f"  ✓ Objective {idx} completed in {qid}")
            else:
                sys.exit(1)

    elif args.command == "quest-complete":
        qid = resolve(args.id, "quest")
        ok = g.quest_complete(qid)
        if ok:
            print(f"  ✓ Quest completed: {qid}")
        else:
            sys.exit(1)

    elif args.command == "quest-fail":
        qid = resolve(args.id, "quest")
        ok = g.quest_fail(qid)
        if ok:
            print(f"  ✓ Quest failed: {qid}")
        else:
            sys.exit(1)

    # ── Consequence handlers ──────────────────────────────────────────────────
    elif args.command == "consequence-add":
        cid = g.consequence_add(args.description, args.trigger, args.hours)
        print(f"  ✓ Consequence added: {cid}")
        if args.hours:
            print(f"    Triggers in {args.hours}h: {args.trigger}")

    elif args.command == "consequence-check":
        nodes = g.list_nodes("consequence")
        B, RS, C, DM, R, G_ = Colors.B, Colors.RESET, Colors.C, Colors.DIM, Colors.R, Colors.G
        if not nodes:
            print("  (no consequences)")
        for n in nodes:
            d = n.get("data", {})
            status = d.get("status", "pending")
            hrs = d.get("hours_remaining")
            marker = f"{R}[TRIGGERED]{RS}" if status == "triggered" else (
                f"{G_}[resolved]{RS}" if status == "resolved" else f"{C}[pending]{RS}")
            timer = f"  {DM}{hrs:.1f}h remaining{RS}" if hrs is not None and status == "pending" else ""
            print(f"  {marker} {B}{n['name']}{RS}{timer}  {DM}{n['id']}{RS}")
            if d.get("trigger"):
                print(f"    → {d['trigger']}")

    elif args.command == "consequence-resolve":
        cid = resolve(args.id, "consequence")
        ok = g.consequence_resolve(cid, args.resolution)
        if ok:
            print(f"  ✓ Resolved: {cid}")
        else:
            sys.exit(1)

    # ── Inventory handlers ────────────────────────────────────────────────────
    elif args.command == "inventory-show":
        oid = resolve(args.owner)
        print(g.inventory_show(oid))

    elif args.command == "inventory-add":
        oid = resolve(args.owner)
        ok = g.inventory_add(oid, args.item, args.qty, args.weight)
        if ok:
            print(f"  ✓ Added {args.item} x{args.qty} → {oid}")
        else:
            sys.exit(1)

    elif args.command == "inventory-add-unique":
        oid = resolve(args.owner)
        ok = g.inventory_add_unique(oid, args.item_desc)
        if ok:
            print(f"  ✓ Added unique item → {oid}: {args.item_desc}")
        else:
            sys.exit(1)

    elif args.command == "inventory-remove":
        oid = resolve(args.owner)
        ok = g.inventory_remove(oid, args.item, args.qty)
        if ok:
            print(f"  ✓ Removed {args.item} x{args.qty} from {oid}")
        else:
            sys.exit(1)

    elif args.command == "inventory-transfer":
        fid = resolve(args.from_owner)
        tid = resolve(args.to_owner)
        ok = g.inventory_transfer(fid, tid, args.item, args.qty)
        if ok:
            print(f"  ✓ Transferred {args.item} x{args.qty}: {fid} → {tid}")
        else:
            sys.exit(1)

    # ── Player handlers ───────────────────────────────────────────────────────
    elif args.command == "player-show":
        print(g.player_show())

    elif args.command == "player-hp":
        ok = g.player_update_stat("hp", args.delta)
        if ok:
            print(f"  ✓ HP {'+' if args.delta >= 0 else ''}{args.delta}")
        else:
            sys.exit(1)

    elif args.command == "player-xp":
        ok = g.player_update_stat("xp", args.delta)
        if ok:
            print(f"  ✓ XP {'+' if args.delta >= 0 else ''}{args.delta}")
        else:
            sys.exit(1)

    elif args.command == "player-gold":
        ok = g.player_update_stat("money", args.delta)
        if ok:
            print(f"  ✓ Gold {'+' if args.delta >= 0 else ''}{args.delta}")
        else:
            sys.exit(1)

    elif args.command == "player-hp-max":
        ok = g.player_hp_max(args.delta)
        if ok:
            print(f"  ✓ HP max {'+' if args.delta >= 0 else ''}{args.delta}")
        else:
            sys.exit(1)

    elif args.command == "player-condition":
        ok = g.player_condition(args.action, args.condition)
        if not ok and args.action != "list":
            sys.exit(1)

    elif args.command == "player-set":
        ok = g.player_set(args.name)
        if not ok:
            sys.exit(1)

    elif args.command == "inventory-craft":
        oid = resolve(args.owner)
        ok = g.inventory_craft(oid, args.recipe_id, args.qty)
        if not ok:
            sys.exit(1)

    elif args.command == "inventory-use":
        oid = resolve(args.owner)
        result = g.inventory_use(oid, args.item)
        if result is None:
            sys.exit(1)

    elif args.command == "inventory-loot":
        oid = resolve(args.owner)
        parsed_items = []
        for raw in (args.items or []):
            parts = raw.split(":")
            name = parts[0]
            qty = int(parts[1]) if len(parts) > 1 else 1
            weight = float(parts[2]) if len(parts) > 2 else 0.5
            parsed_items.append((name, qty, weight))
        ok = g.inventory_loot(oid, parsed_items, args.gold, args.xp)
        if not ok:
            sys.exit(1)

    elif args.command == "consequence-list-resolved":
        nodes = g.consequence_list_resolved()
        B, RS, C, DM = Colors.B, Colors.RESET, Colors.C, Colors.DIM
        if not nodes:
            print("  (no resolved consequences)")
        for n in nodes:
            d = n.get("data", {})
            resolved_at = d.get("resolved", "?")
            resolution = d.get("resolution", "")
            print(f"  {Colors.G}[resolved]{RS} {B}{n['name']}{RS}  {DM}{n['id']}{RS}")
            if resolution:
                print(f"    {DM}→ {resolution}{RS}")
            print(f"    {DM}at {resolved_at}{RS}")

    # ── Wiki handlers ─────────────────────────────────────────────────────────
    elif args.command == "wiki-add":
        mechanics = {}
        for s in args.stat:
            if ":" in s:
                k, v = s.split(":", 1)
                mechanics[k.strip()] = v.strip()
        recipe = None
        if args.ingredient or args.dc:
            recipe = {}
            if args.dc:
                recipe["dc"] = args.dc
            if args.skill:
                recipe["skill"] = args.skill
            if args.ingredient:
                recipe["ingredients"] = {}
                for ing in args.ingredient:
                    if ":" in ing:
                        iid, qty = ing.rsplit(":", 1)
                        recipe["ingredients"][iid.strip()] = int(qty)
                    else:
                        recipe["ingredients"][ing.strip()] = 1
        eid = g.wiki_add(args.id, args.wiki_type, args.name, mechanics or None, recipe)
        print(f"  ✓ Wiki entry: {args.name} ({eid})")

    elif args.command == "wiki-show":
        eid = g._resolve_id(args.id) or args.id
        print(g.format_node(eid))
        print(g.wiki_recipe(eid))

    elif args.command == "wiki-list":
        nodes = g.list_nodes(args.wiki_type)
        wiki_types = {"item", "creature", "spell", "technique"}
        filtered = [n for n in nodes if n.get("type") in wiki_types] if not args.wiki_type else nodes
        print(g.format_node_list(filtered))

    elif args.command == "wiki-search":
        results = g.search_nodes(args.query)
        wiki_types = {"item", "creature", "spell", "technique"}
        if not results:
            print("  No results")
        else:
            for r in results[:20]:
                if r.get("type") not in wiki_types:
                    continue
                tcolor = TYPE_COLORS.get(r.get("type", ""), "")
                print(f"  {tcolor}[{r['type']}]{Colors.RESET} {r['name']}  {Colors.DIM}{r['id']}{Colors.RESET}")

    elif args.command == "wiki-remove":
        ok = g.remove_node(args.id)
        if ok:
            print(f"  ✓ Removed: {args.id}")
        else:
            sys.exit(1)

    # ── Tick handlers ─────────────────────────────────────────────────────────
    elif args.command == "tick":
        g.tick(args.elapsed, args.sleeping)

    elif args.command == "custom-stat":
        stat = g.custom_stat_get(args.name)
        if args.delta is None:
            if stat:
                print(f"  {args.name}: {Colors.C}{stat.get('value', 0)}{Colors.RESET}"
                      f"  (max {stat.get('max')}, rate {stat.get('rate', 0):+g}/h)")
            else:
                print(f"  Stat '{args.name}' not found", file=sys.stderr)
                sys.exit(1)
        else:
            raw = args.delta
            if raw.startswith("="):
                ok = g.custom_stat_set(args.name, absolute=float(raw[1:]), reason=args.reason)
            else:
                ok = g.custom_stat_set(args.name, delta=float(raw), reason=args.reason)
            if not ok:
                sys.exit(1)

    elif args.command == "custom-stat-list":
        g.custom_stat_list()

    elif args.command == "custom-stat-define":
        ok = g.custom_stat_define(args.name, value=args.value, max_val=args.max_val,
                                  min_val=args.min_val, rate=args.rate,
                                  sleep_rate=args.sleep_rate)
        if not ok:
            sys.exit(1)

    elif args.command == "timed-effect-add":
        ok = g.timed_effect_add(args.name, args.stat, args.rate_mod, args.instant, args.hours)
        if not ok:
            sys.exit(1)

    elif args.command == "timed-effect-list":
        g.timed_effect_list()


if __name__ == "__main__":
    main()
