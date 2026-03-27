#!/usr/bin/env python3
"""
Wiki Manager — structured knowledge base for campaign entities.
Stores items, recipes, materials, abilities, effects with cross-references and game mechanics.
Data lives in wiki.json per campaign.
"""

import json
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))

ENTITY_TYPES = [
    "potion", "material", "artifact", "ability", "technique", "spell", "cantrip",
    "effect", "tool", "weapon", "armor", "book", "chapter", "creature", "misc"
]

ANSI = {
    "B": "\033[1m", "DM": "\033[2m", "RS": "\033[0m",
    "C": "\033[36m", "G": "\033[32m", "R": "\033[31m",
    "Y": "\033[33m", "M": "\033[35m",
}


class WikiManager:
    def __init__(self, campaign_dir: str):
        self.campaign_dir = Path(campaign_dir)
        self.wiki_file = self.campaign_dir / "wiki.json"

    def _load(self) -> Dict:
        if self.wiki_file.exists():
            with open(self.wiki_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save(self, data: Dict):
        with open(self.wiki_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(self, entity_id: str, entity_data: Dict) -> Dict:
        wiki = self._load()
        wiki[entity_id] = entity_data
        self._save(wiki)
        return {"success": True, "id": entity_id}

    def remove(self, entity_id: str) -> Dict:
        wiki = self._load()
        eid = self._fuzzy_find(wiki, entity_id)
        if not eid:
            return {"success": False, "error": f"'{entity_id}' not found"}
        del wiki[eid]
        self._save(wiki)
        return {"success": True, "id": eid}

    def show(self, entity_id: str) -> Optional[Dict]:
        wiki = self._load()
        eid = self._fuzzy_find(wiki, entity_id)
        if eid:
            result = wiki[eid].copy()
            result["_id"] = eid
            children = self._get_children(wiki, eid)
            if children:
                result["_children"] = children
            parent_id = self._get_parent_id(eid)
            if parent_id and parent_id in wiki:
                result["_parent"] = {"id": parent_id, "name": wiki[parent_id].get("name", parent_id)}
            return result
        return None

    def list_entities(self, type_filter: str = None, tag_filter: str = None,
                      show_children: bool = False) -> List[Dict]:
        wiki = self._load()
        results = []
        for eid, data in wiki.items():
            if not show_children and "." in eid:
                continue
            if type_filter and data.get("type") != type_filter:
                continue
            if tag_filter and tag_filter not in data.get("tags", []):
                continue
            children = self._get_children(wiki, eid)
            entry = {"id": eid, "name": data.get("name", eid), "type": data.get("type", "?")}
            if children:
                entry["children_count"] = len(children)
            results.append(entry)
        return sorted(results, key=lambda x: (x["type"], x["name"]))

    def search(self, query: str) -> List[Dict]:
        wiki = self._load()
        query_lower = query.lower()
        results = []
        for eid, data in wiki.items():
            score = 0
            name = data.get("name", eid).lower()
            if query_lower in name:
                score += 10
            if query_lower in eid.lower():
                score += 8
            if query_lower in data.get("description", "").lower():
                score += 3
            for tag in data.get("tags", []):
                if query_lower in tag.lower():
                    score += 5
            if score > 0:
                results.append({"id": eid, "name": data.get("name", eid),
                                "type": data.get("type", "?"), "score": score})
        return sorted(results, key=lambda x: -x["score"])

    def recipe_tree(self, entity_id: str, depth: int = 0, max_depth: int = 5) -> Optional[Dict]:
        if depth > max_depth:
            return {"id": entity_id, "error": "max depth"}
        wiki = self._load()
        eid = self._fuzzy_find(wiki, entity_id)
        if not eid:
            return None
        data = wiki[eid]
        recipe = data.get("recipe")
        if not recipe:
            return {"id": eid, "name": data.get("name", eid), "type": data.get("type"), "recipe": None}
        tree = {
            "id": eid,
            "name": data.get("name", eid),
            "type": data.get("type"),
            "recipe": {
                "dc": recipe.get("dc"),
                "skill": recipe.get("skill"),
                "ingredients": {}
            }
        }
        for ing_id, qty in recipe.get("ingredients", {}).items():
            sub = self.recipe_tree(ing_id, depth + 1, max_depth)
            tree["recipe"]["ingredients"][ing_id] = {"qty": qty, "subtree": sub}
        return tree

    def _get_children(self, wiki: Dict, parent_id: str) -> List[Dict]:
        prefix = parent_id + "."
        children = []
        for eid, data in wiki.items():
            if eid.startswith(prefix) and "." not in eid[len(prefix):]:
                children.append({"id": eid, "suffix": eid[len(prefix):],
                                 "name": data.get("name", eid), "type": data.get("type", "?"),
                                 "data": data})
        children.sort(key=lambda x: x["data"].get("mechanics", {}).get("sequence", 999))
        return children

    def _get_parent_id(self, entity_id: str) -> Optional[str]:
        if "." in entity_id:
            return entity_id.rsplit(".", 1)[0]
        return None

    def _fuzzy_find(self, wiki: Dict, query: str) -> Optional[str]:
        if query in wiki:
            return query
        query_lower = query.lower()
        for eid in wiki:
            if eid.lower() == query_lower:
                return eid
        for eid, data in wiki.items():
            if data.get("name", "").lower() == query_lower:
                return eid
        best_score, best_id = 0, None
        for eid, data in wiki.items():
            for candidate in [eid, data.get("name", "")]:
                score = SequenceMatcher(None, query_lower, candidate.lower()).ratio()
                if score > best_score and score > 0.6:
                    best_score, best_id = score, eid
        return best_id

    # --- Display ---

    def format_entity(self, data: Dict) -> str:
        B, DM, RS, C, G, R, Y, M = [ANSI[k] for k in ["B", "DM", "RS", "C", "G", "R", "Y", "M"]]
        lines = []
        eid = data.get("_id", "?")
        etype = data.get("type", "?")
        name = data.get("name", eid)

        lines.append(f"{'=' * 60}")
        lines.append(f"  {B}{name}{RS}  {DM}[{etype}]{RS}  {DM}id:{eid}{RS}")
        lines.append(f"{'─' * 60}")

        if data.get("description"):
            lines.append(f"  {data['description']}")
            lines.append("")

        mech = data.get("mechanics", {})
        if mech:
            lines.append(f"  {B}MECHANICS{RS}")
            for k, v in mech.items():
                if isinstance(v, dict):
                    v_str = ", ".join(f"{kk}: {vv}" for kk, vv in v.items())
                else:
                    v_str = str(v)
                lines.append(f"    {k}: {C}{v_str}{RS}")
            lines.append("")

        recipe = data.get("recipe", {})
        if recipe:
            lines.append(f"  {B}RECIPE{RS}")
            if recipe.get("skill"):
                dc = recipe.get("dc", "?")
                lines.append(f"    Skill: {recipe['skill']}  DC: {C}{dc}{RS}")
            if recipe.get("ingredients"):
                lines.append(f"    Ingredients:")
                for ing, qty in recipe["ingredients"].items():
                    lines.append(f"      {G}•{RS} {ing} x{qty}")
            if recipe.get("tools"):
                lines.append(f"    Tools: {', '.join(recipe['tools'])}")
            if recipe.get("source"):
                lines.append(f"    {DM}Source: {recipe['source']}{RS}")
            lines.append("")

        children = data.get("_children", [])
        if children:
            lines.append(f"  {B}CONTENTS{RS} ({len(children)} entries)")
            status_icons = {
                "COMPLETE": f"{G}✅{RS}", "COMPLETE_WITH_GAPS": f"{Y}⚠️{RS}",
                "PARTIAL": f"{Y}🔶{RS}", "NOT_READ": f"{DM}🔒{RS}"
            }
            for child in children:
                cd = child["data"]
                cm = cd.get("mechanics", {})
                status = cm.get("status", "")
                icon = status_icons.get(status, "  ")
                suffix = child["suffix"].upper()
                cname = cd.get("name", child["id"])
                dc = cm.get("dc", "")
                dc_str = f" DC {C}{dc}{RS}" if dc else ""
                lines.append(f"    {icon} {suffix}. {cname}{dc_str}")
            lines.append("")

        parent = data.get("_parent")
        if parent:
            lines.append(f"  {B}PARENT{RS}: {M}{parent['name']}{RS} {DM}({parent['id']}){RS}")

        refs = data.get("refs", [])
        if refs:
            lines.append(f"  {B}REFS{RS}: {', '.join(f'{M}{r}{RS}' for r in refs)}")

        tags = data.get("tags", [])
        if tags:
            lines.append(f"  {B}TAGS{RS}: {', '.join(f'{DM}#{t}{RS}' for t in tags)}")

        lines.append(f"{'=' * 60}")
        return "\n".join(lines)

    def format_recipe_tree(self, tree: Dict, indent: int = 0) -> str:
        if not tree:
            return "  Not found"
        B, RS, C, G, DM = ANSI["B"], ANSI["RS"], ANSI["C"], ANSI["G"], ANSI["DM"]
        prefix = "  " * indent
        lines = []

        name = tree.get("name", tree.get("id", "?"))
        recipe = tree.get("recipe")

        if indent == 0:
            lines.append(f"{prefix}{B}{name}{RS}")
        else:
            lines.append(f"{prefix}{G}•{RS} {name}")

        if recipe and recipe.get("ingredients"):
            dc = recipe.get("dc", "?")
            skill = recipe.get("skill", "?")
            lines.append(f"{prefix}  {DM}[{skill} DC {dc}]{RS}")
            for ing_id, ing_data in recipe["ingredients"].items():
                qty = ing_data.get("qty", 1)
                sub = ing_data.get("subtree")
                if sub and sub.get("recipe"):
                    lines.append(self.format_recipe_tree(sub, indent + 1))
                else:
                    sub_name = sub.get("name", ing_id) if sub else ing_id
                    lines.append(f"{prefix}  {G}•{RS} {sub_name} x{qty}")

        return "\n".join(lines)

    def format_list(self, items: List[Dict]) -> str:
        B, RS, DM, C = ANSI["B"], ANSI["RS"], ANSI["DM"], ANSI["C"]
        if not items:
            return "  (empty)"
        current_type = None
        lines = []
        for item in items:
            if item["type"] != current_type:
                current_type = item["type"]
                lines.append(f"\n  {B}[{current_type.upper()}]{RS}")
            cc = item.get("children_count", 0)
            suffix = f" {DM}({cc} parts){RS}" if cc else ""
            lines.append(f"    {C}{item['name']}{RS} {DM}({item['id']}){RS}{suffix}")
        return "\n".join(lines)


def _find_campaign_dir():
    root = next(p for p in Path(__file__).parents if (p / ".git").exists())
    active_file = root / "world-state" / "active-campaign.txt"
    if active_file.exists():
        name = active_file.read_text().strip()
        d = root / "world-state" / "campaigns" / name
        if d.exists():
            return str(d)
    print("No active campaign", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Wiki knowledge base")
    sub = parser.add_subparsers(dest="command")

    # add
    add_p = sub.add_parser("add")
    add_p.add_argument("id", help="Entity ID (kebab-case)")
    add_p.add_argument("--name", required=True)
    add_p.add_argument("--type", choices=ENTITY_TYPES, required=True)
    add_p.add_argument("--desc", default="")
    add_p.add_argument("--dc", type=int)
    add_p.add_argument("--skill")
    add_p.add_argument("--effect")
    add_p.add_argument("--cost", help="e.g. 'dark_power:2,hp:-1'")
    add_p.add_argument("--ingredient", action="append", help="id:qty e.g. 'полынь-сушёная:1'")
    add_p.add_argument("--tool", action="append")
    add_p.add_argument("--source")
    add_p.add_argument("--ref", action="append")
    add_p.add_argument("--tag", action="append")
    add_p.add_argument("--stat", action="append", help="key:value for mechanics e.g. 'hp:13'")

    # show
    show_p = sub.add_parser("show")
    show_p.add_argument("id")

    # list
    list_p = sub.add_parser("list")
    list_p.add_argument("--type", choices=ENTITY_TYPES)
    list_p.add_argument("--tag")
    list_p.add_argument("--children", action="store_true", help="Show child entries (dot-separated)")

    # search
    search_p = sub.add_parser("search")
    search_p.add_argument("query")

    # recipe
    recipe_p = sub.add_parser("recipe")
    recipe_p.add_argument("id")

    # remove
    remove_p = sub.add_parser("remove")
    remove_p.add_argument("id")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    mgr = WikiManager(_find_campaign_dir())

    if args.command == "add":
        entity = {"type": args.type, "name": args.name, "description": args.desc}

        mechanics = {}
        if args.effect:
            mechanics["effect"] = args.effect
        if args.cost:
            for pair in args.cost.split(","):
                k, v = pair.split(":")
                mechanics[k.strip()] = int(v.strip()) if v.strip().lstrip('-').isdigit() else v.strip()
        if args.stat:
            for pair in args.stat:
                k, v = pair.split(":", 1)
                mechanics[k.strip()] = int(v.strip()) if v.strip().lstrip('-').isdigit() else v.strip()
        if mechanics:
            entity["mechanics"] = mechanics

        if args.ingredient or args.dc or args.skill:
            recipe = {}
            if args.dc:
                recipe["dc"] = args.dc
            if args.skill:
                recipe["skill"] = args.skill
            if args.ingredient:
                recipe["ingredients"] = {}
                for ing in args.ingredient:
                    parts = ing.rsplit(":", 1)
                    recipe["ingredients"][parts[0]] = int(parts[1]) if len(parts) > 1 else 1
            if args.tool:
                recipe["tools"] = args.tool
            if args.source:
                recipe["source"] = args.source
            entity["recipe"] = recipe

        if args.ref:
            entity["refs"] = args.ref
        if args.tag:
            entity["tags"] = args.tag

        result = mgr.add(args.id, entity)
        print(f"  ✓ Added: {args.name} ({args.id})")

    elif args.command == "show":
        data = mgr.show(args.id)
        if data:
            print(mgr.format_entity(data))
        else:
            print(f"  Not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        items = mgr.list_entities(args.type, args.tag, show_children=args.children)
        print(mgr.format_list(items))

    elif args.command == "search":
        results = mgr.search(args.query)
        if results:
            for r in results[:10]:
                print(f"  [{r['type']}] {r['name']} ({r['id']})")
        else:
            print("  No results")

    elif args.command == "recipe":
        tree = mgr.recipe_tree(args.id)
        if tree:
            print(mgr.format_recipe_tree(tree))
        else:
            print(f"  Not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "remove":
        result = mgr.remove(args.id)
        if result["success"]:
            print(f"  ✓ Removed: {result['id']}")
        else:
            print(f"  {result['error']}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
