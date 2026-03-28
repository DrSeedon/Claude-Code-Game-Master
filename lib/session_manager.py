#!/usr/bin/env python3
"""
Session management module for DM tools
Handles session lifecycle, party movement, and JSON-based saves
"""

import sys
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from world_graph import WorldGraph
from currency import load_config, format_money, migrate_gold
from colors import tag_success, tag_error, Colors


class SessionManager(EntityManager):
    """Manage D&D session operations. Inherits from EntityManager for common functionality."""

    def __init__(self, world_state_dir: str = None):
        super().__init__(world_state_dir)

        self.world_state_dir = self.campaign_dir
        self.saves_dir = self.campaign_dir / "saves"
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        self.campaign_file = "campaign-overview.json"
        self.session_log = self.campaign_dir / "session-log.md"

    def _wg(self) -> WorldGraph:
        return WorldGraph(str(self.campaign_dir))

    def get_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def get_iso_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # ==================== Session Lifecycle ====================

    def start_session(self) -> Dict[str, Any]:
        if not self.session_log.exists():
            self.session_log.write_text("# Campaign Session Log\n\n")

        summary = {
            "facts_count": self._count_items("fact"),
            "npcs_count": self._count_items("npc"),
            "locations_count": self._count_items("location"),
            "current_location": self._get_current_location(),
            "active_character": self._get_active_character(),
            "timestamp": self.get_timestamp()
        }

        with open(self.session_log, 'a') as f:
            f.write(f"## Session Started: {summary['timestamp']}\n\n")

        print(tag_success(f"Session started at {summary['timestamp']}"))
        return summary

    def end_session(self, summary: str) -> bool:
        timestamp = self.get_timestamp()
        session_num = self._get_session_number()

        with open(self.session_log, 'a') as f:
            f.write(f"### Session Ended: {timestamp}\n")
            f.write(f"{summary}\n\n")
            f.write("---\n\n")

        print(tag_success(f"Session {session_num} ended and logged"))
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "facts_count": self._count_items("fact"),
            "npcs_count": self._count_items("npc"),
            "locations_count": self._count_items("location"),
            "current_location": self._get_current_location(),
            "active_character": self._get_active_character(),
            "session_number": self._get_session_number(),
            "recent_sessions": self._get_recent_sessions(5)
        }

    # ==================== Party Movement ====================

    def _ensure_location_and_connection(self, old_location: str, new_location: str) -> None:
        wg = self._wg()

        def _slug(name: str) -> str:
            return wg._slug(name)

        new_id = f"location:{_slug(new_location)}"
        if not wg.get_node(new_id):
            wg.add_node(new_id, "location", new_location, {
                "description": "",
                "discovered": self.get_timestamp()
            })

        if old_location and old_location != "Unknown":
            old_id = f"location:{_slug(old_location)}"
            if wg.get_node(old_id) and wg.get_node(new_id):
                wg.location_connect(old_id, new_id)

    def move_party(self, location: str) -> Dict[str, str]:
        campaign = self.json_ops.load_json(self.campaign_file)

        if 'player_position' not in campaign:
            campaign['player_position'] = {}

        old_location = campaign['player_position'].get('current_location', 'Unknown')

        self._ensure_location_and_connection(old_location, location)

        campaign['player_position']['previous_location'] = old_location
        campaign['player_position']['current_location'] = location
        campaign['player_position']['arrival_time'] = self.get_timestamp()

        self.json_ops.save_json(self.campaign_file, campaign)

        wg = self._wg()
        player_id = wg._player_id()
        if player_id:
            wg.update_node(player_id, {"data": {"current_location": location}})

        result = {
            "previous_location": old_location,
            "current_location": location
        }

        print(f"📍 {old_location} → {Colors.BC}{location}{Colors.RS}")
        return result

    # ==================== Save System ====================

    def create_save(self, name: str) -> str:
        safe_name = name.lower().replace(' ', '-')
        timestamp = self.get_iso_timestamp()
        filename = f"{timestamp}-{safe_name}.json"

        world_file = self.campaign_dir / "world.json"
        world_data = None
        if world_file.exists():
            with open(world_file, 'r', encoding='utf-8') as f:
                world_data = json.load(f)

        snapshot = {
            "campaign_overview": self.json_ops.load_json(self.campaign_file),
            "world": world_data,
        }

        save_data = {
            "name": name,
            "created": datetime.now(timezone.utc).isoformat(),
            "session_number": self._get_session_number(),
            "snapshot": snapshot
        }

        save_path = self.saves_dir / filename
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        print(tag_success(f"Save created: {filename}"))
        return filename

    def restore_save(self, name: str) -> bool:
        save_file = self._find_save(name)
        if not save_file:
            print(tag_error(f"Save point '{name}' not found"))
            return False

        try:
            with open(save_file, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(tag_error(f"Failed to load save: {e}"))
            return False

        snapshot = save_data.get('snapshot', {})

        if 'campaign_overview' in snapshot:
            self.json_ops.save_json(self.campaign_file, snapshot['campaign_overview'])

        if 'world' in snapshot and snapshot['world'] is not None:
            world_file = self.campaign_dir / "world.json"
            tmp = world_file.with_suffix(".json.tmp")
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(snapshot['world'], f, indent=2, ensure_ascii=False)
            import os
            os.replace(tmp, world_file)
        else:
            # Backward compat: old saves with flat files
            for key, filename in [
                ('npcs', 'npcs.json'),
                ('locations', 'locations.json'),
                ('facts', 'facts.json'),
                ('consequences', 'consequences.json'),
            ]:
                if key in snapshot:
                    self.json_ops.save_json(filename, snapshot[key])
            if 'characters' in snapshot:
                self._restore_characters_legacy(snapshot['characters'])

        print(tag_success(f"Restored from save: {save_file.name}"))
        return True

    def list_saves(self) -> List[Dict[str, Any]]:
        saves = []
        for save_file in sorted(self.saves_dir.glob("*.json"), reverse=True):
            try:
                with open(save_file, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                saves.append({
                    "filename": save_file.name,
                    "name": save_data.get("name", "Unknown"),
                    "created": save_data.get("created", "Unknown"),
                    "session_number": save_data.get("session_number", "?")
                })
            except (json.JSONDecodeError, IOError):
                continue
        return saves

    def delete_save(self, name: str) -> bool:
        save_file = self._find_save(name)
        if not save_file:
            print(tag_error(f"Save point '{name}' not found"))
            return False

        save_file.unlink()
        print(tag_success(f"Deleted save: {save_file.name}"))
        return True

    def get_history(self) -> List[str]:
        if not self.session_log.exists():
            return []

        content = self.session_log.read_text()
        lines = content.split('\n')

        sessions = []
        for line in lines:
            if 'Session Started:' in line or 'Session Ended:' in line:
                sessions.append(line.strip())

        return sessions[-10:]

    # ==================== Full Session Context ====================

    def _truncate(self, text: str, limit: int, full: bool) -> str:
        if full or not text or len(text) <= limit:
            return text
        return text[:limit - 3].rstrip() + "..."

    def get_full_context(self, full: bool = False) -> str:
        lines = []

        campaign = self.json_ops.load_json(self.campaign_file) or {}
        campaign_name = campaign.get('name', campaign.get('campaign_name', 'Unknown Campaign'))
        session_num = self._get_session_number()
        location = campaign.get('player_position', {}).get('current_location', 'Unknown')
        time_of_day = campaign.get('time', {}).get('time_of_day', campaign.get('time_of_day', ''))
        current_date = campaign.get('time', {}).get('current_date', campaign.get('current_date', ''))
        time_str = f"{time_of_day}, {current_date}" if time_of_day and current_date else time_of_day or current_date or 'Unknown'

        lines.append("=== SESSION CONTEXT ===")
        lines.append(f"Campaign: {campaign_name} | Session #{session_num}")
        lines.append(f"Location: {location} | Time: {time_str}")

        lines.append("")
        lines.append("--- CHARACTER ---")
        char = self._get_character_for_session()

        if char:
            name = char.get('name', 'Unknown')
            level = char.get('level', 1)
            race = char.get('race', '?')
            cls = char.get('class', '?')
            hp = char.get('hp', {})
            hp_cur = hp.get('current', 0)
            hp_max = hp.get('max', 0)
            ac = char.get('ac', '?')
            xp = char.get('xp', {})
            if isinstance(xp, dict):
                xp_val = xp.get('current', 0)
            else:
                xp_val = xp
            currency_config = load_config(self.campaign_dir)
            raw_money = char.get('money', None)
            if raw_money is None:
                raw_money = migrate_gold(char.get('gold', 0), currency_config)
            money_str = format_money(raw_money, currency_config)
            conditions = char.get('conditions', [])
            cond_str = ', '.join(conditions) if conditions else '(none)'
            lines.append(f"{name} - Level {level} {race} {cls} | HP: {hp_cur}/{hp_max} | AC: {ac} | XP: {xp_val} | Gold: {money_str}")
            lines.append(f"Conditions: {cond_str}")
        else:
            lines.append("No character found.")

        lines.append("")
        lines.append("--- PARTY MEMBERS ---")
        wg = self._wg()
        npc_nodes = wg.list_nodes(node_type="npc")
        party_nodes = [
            n for n in npc_nodes
            if n.get("data", {}).get("party_member") or n.get("data", {}).get("is_party_member")
        ]

        if party_nodes:
            max_party = len(party_nodes) if full else 8
            shown_party = party_nodes[:max_party]
            for node in shown_party:
                npc_name = node.get("name", node.get("id", "?"))
                npc_data = node.get("data", {})
                sheet = npc_data.get('character_sheet', {})
                if isinstance(sheet.get('hp'), dict):
                    hp = sheet['hp']
                else:
                    hp_val = sheet.get('hp', 10)
                    hp_max_val = sheet.get('hp_max', hp_val)
                    hp = {'current': hp_val, 'max': hp_max_val}
                ac = sheet.get('ac', 10)
                level = sheet.get('level', 1)
                race = sheet.get('race', 'Unknown')
                cls = sheet.get('class', 'Commoner')
                conditions = sheet.get('conditions', [])
                cond_str = f" [{', '.join(conditions)}]" if conditions else ""
                desc = self._truncate(npc_data.get('description', ''), 180, full)

                lines.append(f"{npc_name} (Lvl {level} {race} {cls}) HP: {hp['current']}/{hp['max']} AC: {ac}{cond_str}")
                if desc:
                    lines.append(f"  {desc}")

                events = node.get('events', [])
                if events:
                    recent = events[-3:] if full else events[-2:]
                    event_strs = []
                    for ev in recent:
                        if isinstance(ev, dict):
                            event_strs.append(f"\"{self._truncate(ev.get('event', ''), 120, full)}\"")
                        else:
                            event_strs.append(f"\"{self._truncate(str(ev), 120, full)}\"")
                    lines.append(f"  Recent: {' -> '.join(event_strs)}")
                lines.append("")
            if not full and len(party_nodes) > max_party:
                lines.append(f"... and {len(party_nodes) - max_party} more party members (use --full)")
                lines.append("")
        else:
            lines.append("(none)")
            lines.append("")

        lines.append("--- PENDING CONSEQUENCES ---")
        consequence_nodes = wg.list_nodes(node_type="consequence")
        pending = []
        for node in consequence_nodes:
            cdata = node.get("data", {})
            if cdata.get('status', 'pending') == 'pending':
                event = cdata.get('event', cdata.get('description', node.get('name', 'Unknown')))
                trigger = cdata.get('trigger', 'Unknown')
                cid = node.get('id', '?')
                short_id = cid[:4] if len(cid) >= 4 else cid
                pending.append(f"[{short_id}] {event} -> triggers: {trigger}")

        if pending:
            max_pending = len(pending) if full else 10
            for p in pending[:max_pending]:
                lines.append(p)
            if not full and len(pending) > max_pending:
                lines.append(f"... and {len(pending) - max_pending} more pending consequences (use --full)")
        else:
            lines.append("(none)")

        rules = campaign.get('campaign_rules', {})
        if rules:
            lines.append("")
            lines.append("--- CAMPAIGN RULES ---")
            if isinstance(rules, dict):
                for key, val in rules.items():
                    value_text = self._truncate(str(val), 220, full)
                    lines.append(f"- {key}: {value_text}")
            elif isinstance(rules, list):
                max_rules = len(rules) if full else 12
                for rule in rules[:max_rules]:
                    lines.append(f"- {self._truncate(str(rule), 220, full)}")
                if not full and len(rules) > max_rules:
                    lines.append(f"- ... and {len(rules) - max_rules} more rules (use --full)")

        return "\n".join(lines)

    # ==================== Private Helpers ====================

    def _count_items(self, node_type: str) -> int:
        wg = self._wg()
        return len(wg.list_nodes(node_type=node_type))

    def _get_current_location(self) -> Optional[str]:
        campaign = self.json_ops.load_json(self.campaign_file)
        return campaign.get('player_position', {}).get('current_location')

    def _get_active_character(self) -> Optional[str]:
        campaign = self.json_ops.load_json(self.campaign_file)
        return campaign.get('current_character')

    def _get_session_number(self) -> int:
        if not self.session_log.exists():
            return 0
        content = self.session_log.read_text()
        return content.count('Session Started:')

    def _get_recent_sessions(self, count: int) -> List[str]:
        history = self.get_history()
        return history[-count:] if history else []

    def _get_character_for_session(self) -> Optional[Dict[str, Any]]:
        wg = self._wg()
        player_id = wg._player_id()
        if player_id:
            node = wg.get_node(player_id)
            if node:
                char = dict(node.get("data", {}))
                if "name" not in char:
                    char["name"] = node.get("name", "Unknown")
                return char
        return None

    def _restore_characters_legacy(self, characters: Dict[str, Any]) -> None:
        wg = self._wg()
        char_data = characters.get('character') or (
            next(iter(characters.values()), None) if len(characters) == 1 else None
        )
        if char_data:
            player_id = wg._player_id()
            if player_id:
                wg.update_node(player_id, {"data": char_data})

    def _find_save(self, name: str) -> Optional[Path]:
        exact_match = self.saves_dir / name
        if exact_match.exists():
            return exact_match

        if not name.endswith('.json'):
            exact_match = self.saves_dir / f"{name}.json"
            if exact_match.exists():
                return exact_match

        for save_file in self.saves_dir.glob("*.json"):
            if name.lower() in save_file.name.lower():
                return save_file

        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Session management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    subparsers.add_parser('start', help='Start new session')

    end_parser = subparsers.add_parser('end', help='End session')
    end_parser.add_argument('summary', nargs='+', help='Session summary')

    subparsers.add_parser('status', help='Get campaign status')

    move_parser = subparsers.add_parser('move', help='Move party to location')
    move_parser.add_argument('location', nargs='+', help='Location name')

    save_parser = subparsers.add_parser('save', help='Create save point')
    save_parser.add_argument('name', nargs='+', help='Save name')

    restore_parser = subparsers.add_parser('restore', help='Restore from save')
    restore_parser.add_argument('name', help='Save name or filename')

    subparsers.add_parser('list-saves', help='List all save points')

    delete_parser = subparsers.add_parser('delete-save', help='Delete a save point')
    delete_parser.add_argument('name', help='Save name or filename')

    subparsers.add_parser('history', help='Show session history')

    context_parser = subparsers.add_parser('context', help='Get full session context (one-command startup)')
    context_parser.add_argument('--full', action='store_true', help='Show full context with less truncation')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = SessionManager()

    if args.action == 'start':
        summary = manager.start_session()
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    elif args.action == 'end':
        summary_text = ' '.join(args.summary)
        if not manager.end_session(summary_text):
            sys.exit(1)

    elif args.action == 'status':
        status = manager.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif args.action == 'move':
        location = ' '.join(args.location)
        manager.move_party(location)

    elif args.action == 'save':
        name = ' '.join(args.name)
        manager.create_save(name)

    elif args.action == 'restore':
        if not manager.restore_save(args.name):
            sys.exit(1)

    elif args.action == 'list-saves':
        saves = manager.list_saves()
        if saves:
            print(json.dumps(saves, indent=2, ensure_ascii=False))
        else:
            print("No saves found")

    elif args.action == 'delete-save':
        if not manager.delete_save(args.name):
            sys.exit(1)

    elif args.action == 'history':
        history = manager.get_history()
        for entry in history:
            print(entry)

    elif args.action == 'context':
        print(manager.get_full_context(full=getattr(args, 'full', False)))


if __name__ == "__main__":
    main()
