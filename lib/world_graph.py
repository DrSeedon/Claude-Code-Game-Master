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
import re
import sys
import argparse
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
    "fact", "quest", "consequence", "spell", "technique"
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


def main():
    parser = argparse.ArgumentParser(description="World graph — unified entity manager")
    sub = parser.add_subparsers(dest="command")

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

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    g = WorldGraph()

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


if __name__ == "__main__":
    main()
