#!/usr/bin/env python3
"""
Simple dice rolling library for D&D
Supports standard notation: 1d20, 3d6+2, 2d20kh1 (advantage), etc.
"""

import random
import re
from typing import List, Tuple, Dict

# Import colors for formatted output
try:
    from lib.colors import Colors, format_roll_result
except ImportError:
    # Fallback if running directly
    try:
        from colors import Colors, format_roll_result
    except ImportError:
        # No colors available - use plain text
        class Colors:
            RESET = RS = ""
            RED = R = ""
            GREEN = G = ""
            YELLOW = Y = ""
            CYAN = C = ""
            BOLD = B = ""
            BOLD_RED = BR = ""
            BOLD_GREEN = BG = ""
            BOLD_YELLOW = BY = ""
            BOLD_CYAN = BC = ""
            DIM = DM = ""
            LIGHT_GREEN = ""
            LIGHT_RED = ""
            MAGENTA = ""
            BOLD_MAGENTA = ""

        def format_roll_result(notation, rolls, total, is_crit=False, is_fumble=False):
            rolls_str = '+'.join(str(r) for r in rolls)
            base = f"🎲 {notation}: [{rolls_str}] = {total}"
            if is_crit:
                base += " ⚔️ CRITICAL HIT!"
            elif is_fumble:
                base += " 💀 CRITICAL MISS!"
            return base

class DiceRoller:
    def __init__(self):
        # Regex patterns for different dice notations
        self.simple_pattern = re.compile(r'(\d+)d(\d+)([+-]\d+)?')
        self.advantage_pattern = re.compile(r'(\d+)d(\d+)kh(\d+)([+-]\d+)?')  # keep highest
        self.disadvantage_pattern = re.compile(r'(\d+)d(\d+)kl(\d+)([+-]\d+)?')  # keep lowest
        
    def roll(self, notation: str) -> Dict:
        """
        Roll dice based on notation and return detailed results
        
        Returns dict with:
        - notation: original notation
        - rolls: individual die results
        - total: final total
        - natural_20: True if d20 rolled natural 20
        - natural_1: True if d20 rolled natural 1
        """
        notation = notation.strip()
        
        # Check for advantage (keep highest)
        match = self.advantage_pattern.match(notation)
        if match:
            count, sides, keep = int(match.group(1)), int(match.group(2)), int(match.group(3))
            modifier = int(match.group(4)) if match.group(4) else 0
            if sides < 1:
                raise ValueError(f"Invalid die size: d{sides} (must be at least 1)")
            rolls = sorted([random.randint(1, sides) for _ in range(count)], reverse=True)
            kept = rolls[:keep]
            result = {
                'notation': notation,
                'rolls': rolls,
                'kept': kept,
                'discarded': rolls[keep:],
                'modifier': modifier,
                'total': sum(kept) + modifier,
                'type': 'advantage'
            }
            if sides == 20 and keep == 1:
                if kept[0] == 20:
                    result['natural_20'] = True
                elif kept[0] == 1:
                    result['natural_1'] = True
            return result

        # Check for disadvantage (keep lowest)
        match = self.disadvantage_pattern.match(notation)
        if match:
            count, sides, keep = int(match.group(1)), int(match.group(2)), int(match.group(3))
            modifier = int(match.group(4)) if match.group(4) else 0
            if sides < 1:
                raise ValueError(f"Invalid die size: d{sides} (must be at least 1)")
            rolls = sorted([random.randint(1, sides) for _ in range(count)])
            kept = rolls[:keep]
            result = {
                'notation': notation,
                'rolls': rolls,
                'kept': kept,
                'discarded': rolls[keep:],
                'modifier': modifier,
                'total': sum(kept) + modifier,
                'type': 'disadvantage'
            }
            if sides == 20 and keep == 1:
                if kept[0] == 20:
                    result['natural_20'] = True
                elif kept[0] == 1:
                    result['natural_1'] = True
            return result
        
        # Standard roll
        match = self.simple_pattern.match(notation)
        if match:
            count, sides = int(match.group(1)), int(match.group(2))
            if sides < 1:
                raise ValueError(f"Invalid die size: d{sides} (must be at least 1)")
            modifier = int(match.group(3)) if match.group(3) else 0

            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls) + modifier
            
            result = {
                'notation': notation,
                'rolls': rolls,
                'modifier': modifier,
                'total': total,
                'type': 'standard'
            }
            
            # Check for natural 20/1 on d20
            if sides == 20 and count == 1:
                if rolls[0] == 20:
                    result['natural_20'] = True
                elif rolls[0] == 1:
                    result['natural_1'] = True
                    
            return result
        
        raise ValueError(f"Invalid dice notation: {notation}")
    
    def format_result(self, result: Dict) -> str:
        """Format a roll result for display with colors"""
        if result['type'] in ('advantage', 'disadvantage'):
            kept_str = '+'.join(str(r) for r in result['kept'])
            discarded_str = '+'.join(str(r) for r in result['discarded'])
            mod = result.get('modifier', 0)
            mod_str = f" {mod:+d}" if mod != 0 else ""
            base = f"🎲 {result['notation']}: {Colors.CYAN}[{kept_str}]{Colors.RESET} {Colors.DIM}(discarded: {discarded_str}){Colors.RESET}{mod_str} = {Colors.CYAN}{result['total']}{Colors.RESET}"
            if result.get('natural_20'):
                base += f" ⚔️ {Colors.BOLD_GREEN}CRITICAL HIT!{Colors.RESET}"
            elif result.get('natural_1'):
                base += f" 💀 {Colors.BOLD_RED}CRITICAL MISS!{Colors.RESET}"
            return base

        else:  # standard
            is_crit = result.get('natural_20', False)
            is_fumble = result.get('natural_1', False)

            rolls_str = '+'.join(str(r) for r in result['rolls'])
            base = f"🎲 {result['notation']}: {Colors.CYAN}[{rolls_str}]{Colors.RESET}"

            if result['modifier'] != 0:
                mod_str = f"{result['modifier']:+d}"
                base += f" {mod_str}"

            base += f" = {Colors.CYAN}{result['total']}{Colors.RESET}"

            if is_crit:
                base += f" ⚔️ {Colors.BOLD_GREEN}CRITICAL HIT!{Colors.RESET}"
            elif is_fumble:
                base += f" 💀 {Colors.BOLD_RED}CRITICAL MISS!{Colors.RESET}"

            return base


def _dc_color(dc):
    """DC difficulty gradient: green→yellow→orange→red→magenta→bold magenta."""
    if dc <= 5:
        return "\033[32m"
    elif dc <= 10:
        return "\033[92m"
    elif dc <= 15:
        return "\033[33m"
    elif dc <= 20:
        return "\033[91m"
    elif dc <= 25:
        return "\033[31m"
    else:
        return "\033[1;35m"


def format_enhanced(result, label=None, dc=None, ac=None):
    """Format roll result with label, DC/AC check, and verdict. Used by dm-roll.sh."""
    RS = Colors.RS
    C = Colors.C
    G = Colors.G
    BG = Colors.BG
    R = Colors.R
    BR = Colors.BR
    BY = Colors.BY
    DM = Colors.DM

    rolls = result.get("kept", result["rolls"])
    rolls_str = "+".join(str(r) for r in rolls)

    mod = result.get("modifier", 0)
    total = result["total"]
    nat20 = result.get("natural_20", False)
    nat1 = result.get("natural_1", False)

    target = dc or ac
    target_label = "DC" if dc else ("AC" if ac else None)

    header = "🎲"
    if label:
        header += f" {label}"
    if target_label:
        tc = _dc_color(target)
        header += f" vs {target_label} {tc}{target}{RS}:"
    else:
        header += ":"

    roll_str = f"{C}[{rolls_str}]{RS}"

    if result["type"] in ("advantage", "disadvantage"):
        discarded_str = "+".join(str(r) for r in result["discarded"])
        roll_str += f" {DM}~({discarded_str})~{RS}"

    if mod != 0:
        mod_color = G if mod > 0 else R
        roll_str += f" {mod_color}{mod:+d}{RS}"
    roll_str += f" = {C}{total}{RS}"

    if nat20:
        verdict = f"{BG}⚔ CRITICAL!{RS}"
    elif nat1:
        verdict = f"{BR}💀 FUMBLE!{RS}"
    elif dc:
        verdict = f"{BG}✓ SUCCESS{RS}" if total >= dc else f"{BR}✗ FAIL{RS}"
    elif ac:
        verdict = f"{BG}✓ HIT!{RS}" if total >= ac else f"{BY}✗ MISS{RS}"
    else:
        verdict = ""

    line = f"{header} {roll_str}"
    if verdict:
        line += f" — {verdict}"
    return line


# Module-level convenience functions
_roller = DiceRoller()

def roll(notation: str) -> int:
    """Quick roll that returns just the total. Use for simple checks."""
    return _roller.roll(notation)['total']

def roll_detailed(notation: str) -> Dict:
    """Roll with full details (rolls, modifiers, crits, etc.)"""
    return _roller.roll(notation)

def roll_formatted(notation: str) -> str:
    """Roll and return formatted string for display."""
    result = _roller.roll(notation)
    return _roller.format_result(result)


def _get_campaign_path():
    """Get active campaign directory path."""
    from pathlib import Path
    root = next(p for p in Path(__file__).parents if (p / ".git").exists())
    active_file = root / "world-state" / "active-campaign.txt"
    if not active_file.exists():
        return None
    campaign = active_file.read_text().strip()
    return root / "world-state" / "campaigns" / campaign


def _load_character():
    """Load active character from campaign."""
    import json
    campaign_dir = _get_campaign_path()
    if not campaign_dir:
        return None
    char_file = campaign_dir / "character.json"
    if not char_file.exists():
        return None
    with open(char_file) as f:
        return json.load(f)


def _load_creature(name):
    """Load creature stats from wiki.json by ID or fuzzy name match."""
    import json
    campaign_dir = _get_campaign_path()
    if not campaign_dir:
        return None
    wiki_file = campaign_dir / "wiki.json"
    if not wiki_file.exists():
        return None
    with open(wiki_file) as f:
        wiki = json.load(f)
    name_lower = name.lower()
    if name_lower in wiki and wiki[name_lower].get("type") == "creature":
        return wiki[name_lower]
    for eid, data in wiki.items():
        if not isinstance(data, dict) or data.get("type") != "creature":
            continue
        if name_lower in eid.lower() or name_lower in data.get("name", "").lower():
            return data
    return None


def _resolve_skill(char, skill_name):
    """Get skill modifier and dc_mod from character."""
    skills = char.get('skills', {})
    for name, data in skills.items():
        if name.lower() == skill_name.lower():
            if isinstance(data, dict):
                return data.get('total', 0), data.get('dc_mod', 0), name
            return int(data), 0, name
    return None, None, None


def _resolve_save(char, save_name):
    """Auto-calculate save modifier from stats + proficiency. No saves field needed in character.json."""
    stats = char.get('stats', {})
    level = char.get('level', 1)
    proficiency = 2 if level < 5 else 3 if level < 9 else 4 if level < 13 else 5 if level < 17 else 6
    save_profs = [s.lower() for s in char.get('save_proficiencies', [])]

    stat_map = {
        'str': 'str', 'сил': 'str',
        'dex': 'dex', 'лов': 'dex',
        'con': 'con', 'вын': 'con',
        'int': 'int', 'инт': 'int',
        'wis': 'wis', 'мдр': 'wis',
        'cha': 'cha', 'хар': 'cha',
    }
    display_map = {
        'str': 'СИЛ', 'dex': 'ЛОВ', 'con': 'ВЫН',
        'int': 'ИНТ', 'wis': 'МДР', 'cha': 'ХАР',
    }

    key = save_name.lower()[:3]
    stat_key = stat_map.get(key)
    if not stat_key:
        return None, None

    stat_val = stats.get(stat_key, 10)
    mod = (stat_val - 10) // 2
    if key in save_profs or stat_key in save_profs:
        mod += proficiency

    display = display_map.get(stat_key, stat_key.upper())
    return mod, display


def _resolve_attack(char, weapon_name=None):
    """Get attack bonus and damage from equipped weapon."""
    equipment = char.get('equipment', {})
    weapons = equipment.get('weapons', [])
    stats = char.get('stats', {})
    proficiency = 2 if char.get('level', 1) < 5 else 3 if char.get('level', 1) < 9 else 4

    target_weapon = None
    if weapon_name:
        for w in weapons:
            if weapon_name.lower() in w.get('name', '').lower():
                target_weapon = w
                break
    if not target_weapon:
        for w in weapons:
            if w.get('equipped'):
                target_weapon = w
                break
    if not target_weapon and weapons:
        target_weapon = weapons[0]

    if target_weapon:
        stat_name = target_weapon.get('stat', 'str')
        stat_val = stats.get(stat_name, 10)
        stat_mod = (stat_val - 10) // 2
        prof_bonus = proficiency if target_weapon.get('proficient') else 0
        weapon_bonus = target_weapon.get('bonus', 0)
        total = stat_mod + prof_bonus + weapon_bonus
        name = target_weapon.get('name', '?')
        damage = target_weapon.get('damage', '1d4')
        ammo = target_weapon.get('ammo_type', None)
        range_normal = target_weapon.get('range_normal', None)
        range_long = target_weapon.get('range_long', None)
        return total, name, damage, ammo, range_normal, range_long

    skills = char.get('skills', {})
    melee = skills.get('ближний бой', {})
    mod = melee.get('total', 0) if isinstance(melee, dict) else int(melee) if melee else 0
    return mod, 'ближний бой', '1d4', None, None, None


def _load_spell(name):
    """Load spell/ability from wiki.json by ID or fuzzy name match."""
    import json
    campaign_dir = _get_campaign_path()
    if not campaign_dir:
        return None
    wiki_file = campaign_dir / "wiki.json"
    if not wiki_file.exists():
        return None
    with open(wiki_file) as f:
        wiki = json.load(f)
    name_lower = name.lower()
    spell_types = {"spell", "ability", "technique", "cantrip"}
    if name_lower in wiki and wiki[name_lower].get("type") in spell_types:
        return wiki[name_lower]
    for eid, data in wiki.items():
        if not isinstance(data, dict) or data.get("type") not in spell_types:
            continue
        if name_lower in eid.lower() or name_lower in data.get("name", "").lower():
            return data
    return None


def _resolve_spell_attack(char):
    """Get spellcasting attack bonus: casting stat mod + proficiency."""
    stats = char.get('stats', {})
    level = char.get('level', 1)
    proficiency = 2 if level < 5 else 3 if level < 9 else 4 if level < 13 else 5 if level < 17 else 6
    casting_stat = char.get('casting_stat', 'int')
    stat_val = stats.get(casting_stat, 10)
    stat_mod = (stat_val - 10) // 2
    return stat_mod + proficiency, stat_mod, proficiency


def main():
    """CLI interface for dice rolling"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Dice roller with labels and DC/AC checks")
    parser.add_argument("notation", nargs="?", default=None, help="Dice notation (e.g. 1d20+5, 2d20kh1+3)")
    parser.add_argument("--label", "-l", help="Roll description (e.g. 'Perception (Рекс)')")
    parser.add_argument("--dc", type=int, help="Difficulty Class to check against")
    parser.add_argument("--ac", type=int, help="Armor Class to check against")
    parser.add_argument("--skill", "-s", help="Skill name (auto-lookup modifier from character.json)")
    parser.add_argument("--save", help="Save name: str/dex/con/int/wis/cha or Russian abbrev")
    parser.add_argument("--attack", nargs="?", const="", help="Attack roll (optional: weapon/skill name)")
    parser.add_argument("--spell", help="Spell/ability name (auto-lookup from wiki: attack or save-based)")
    parser.add_argument("--target", "-t", help="Target creature (auto-lookup AC from wiki, auto-damage on hit)")
    parser.add_argument("--defend", action="store_true", help="Creature attacks player (use with --from)")
    parser.add_argument("--from", dest="from_creature", help="Creature attacking (auto-lookup attack+damage from wiki)")
    parser.add_argument("--range", type=int, help="Distance to target in feet (auto-applies disadvantage if beyond normal range)")
    parser.add_argument("--advantage", "--adv", action="store_true", help="Roll with advantage (2d20kh1)")
    parser.add_argument("--disadvantage", "--dis", action="store_true", help="Roll with disadvantage (2d20kl1)")
    args = parser.parse_args()

    char = None
    notation = args.notation
    label = args.label
    dc = args.dc
    ac = args.ac
    atk_ammo = None
    atk_range_n = None
    atk_range_l = None
    atk_name = None
    atk_damage = None

    if args.skill or args.save or args.attack is not None:
        char = _load_character()
        if not char:
            print("Error: No active character found", file=sys.stderr)
            sys.exit(1)
        char_name = char.get('name', '?')

    if args.skill:
        mod, dc_mod, skill_name = _resolve_skill(char, args.skill)
        if mod is None:
            print(f"Error: Skill '{args.skill}' not found", file=sys.stderr)
            sys.exit(1)
        notation = f"1d20+{mod}"
        if not label:
            label = f"{skill_name} ({char_name})"
        if dc and dc_mod:
            dc = dc + dc_mod

    elif args.save is not None:
        mod, save_name = _resolve_save(char, args.save)
        if mod is None:
            print(f"Error: Save '{args.save}' not found", file=sys.stderr)
            sys.exit(1)
        notation = f"1d20+{mod}" if mod >= 0 else f"1d20{mod}"
        if not label:
            label = f"{save_name.upper()} Save ({char_name})"

    elif args.attack is not None:
        mod, atk_name, atk_damage, atk_ammo, atk_range_n, atk_range_l = _resolve_attack(char, args.attack if args.attack else None)
        notation = f"1d20+{mod}" if mod >= 0 else f"1d20{mod}"
        if not label:
            label = f"Attack: {atk_name} ({char_name}) [dmg: {atk_damage}]"

    spell_data = None
    spell_save_dc = None

    if args.spell:
        spell_data = _load_spell(args.spell)
        if not spell_data:
            print(f"Error: Spell '{args.spell}' not found in wiki", file=sys.stderr)
            sys.exit(1)
        if not char:
            char = _load_character()
        if not char:
            print("Error: No active character found", file=sys.stderr)
            sys.exit(1)
        char_name = char.get('name', '?')
        spell_name = spell_data.get('name', args.spell)
        s_mechanics = spell_data.get('mechanics', {})
        spell_damage = s_mechanics.get('damage', None)
        spell_attack_type = s_mechanics.get('attack_type', s_mechanics.get('type', 'save'))
        spell_save_type = s_mechanics.get('save_type', s_mechanics.get('save', None))

        if spell_attack_type in ('ranged', 'melee', 'attack', 'spell_attack'):
            spell_mod, _, _ = _resolve_spell_attack(char)
            notation = f"1d20+{spell_mod}" if spell_mod >= 0 else f"1d20{spell_mod}"
            if not label:
                dmg_tag = f" [dmg: {spell_damage}]" if spell_damage else ""
                label = f"Spell: {spell_name} ({char_name}){dmg_tag}"
        elif spell_save_type:
            pass
        else:
            if spell_damage:
                notation = spell_damage
                if not label:
                    label = f"Spell: {spell_name} ({char_name})"

    creature_data = None
    damage_dice = None

    if args.target:
        creature_data = _load_creature(args.target)
        if not creature_data:
            print(f"Error: Creature '{args.target}' not found in wiki", file=sys.stderr)
            sys.exit(1)
        mechanics = creature_data.get('mechanics', {})
        creature_ac = int(mechanics.get('ac', mechanics.get('AC', 10)))
        creature_name = creature_data.get('name', args.target)

        if spell_data:
            s_mechanics = spell_data.get('mechanics', {})
            spell_name = spell_data.get('name', args.spell)
            spell_damage = s_mechanics.get('damage', None)
            spell_attack_type = s_mechanics.get('attack_type', s_mechanics.get('type', 'save'))
            spell_save_type = s_mechanics.get('save_type', s_mechanics.get('save', None))

            if spell_attack_type in ('ranged', 'melee', 'attack', 'spell_attack'):
                ac = creature_ac
                if not label:
                    dmg_tag = f" [dmg: {spell_damage}]" if spell_damage else ""
                    label = f"Spell: {spell_name} → {creature_name} ({char_name}){dmg_tag}"
                damage_dice = spell_damage
            elif spell_save_type:
                if not char:
                    char = _load_character()
                if char:
                    spell_mod, stat_mod, prof = _resolve_spell_attack(char)
                    spell_save_dc = 8 + spell_mod
                save_abbr = spell_save_type.lower()[:3]
                creature_saves = mechanics.get('saves', {})
                if isinstance(creature_saves, str):
                    import json as _json
                    try:
                        creature_saves = _json.loads(creature_saves)
                    except Exception:
                        creature_saves = {}
                creature_save_mod = 0
                for k, v in creature_saves.items():
                    if k.lower()[:3] == save_abbr:
                        creature_save_mod = int(v)
                        break
                notation = f"1d20+{creature_save_mod}" if creature_save_mod >= 0 else f"1d20{creature_save_mod}"
                dc = spell_save_dc
                if not label:
                    dmg_tag = f" [dmg: {spell_damage}]" if spell_damage else ""
                    label = f"{creature_name} {spell_save_type.upper()} Save vs {spell_name}{dmg_tag}"
                damage_dice = spell_damage
            else:
                if spell_damage:
                    notation = spell_damage
                    if not label:
                        label = f"Spell: {spell_name} → {creature_name} ({char_name})"
                    damage_dice = None
        elif args.attack is not None:
            ac = creature_ac
            if not label:
                label = f"Attack: {atk_name} → {creature_name} ({char_name})"
            damage_dice = atk_damage
        elif args.skill:
            pass
        else:
            ac = creature_ac
            if not char:
                char = _load_character()
            if char:
                char_name = char.get('name', '?')
                mod, atk_name, atk_damage, atk_ammo, atk_range_n, atk_range_l = _resolve_attack(char, None)
                notation = f"1d20+{mod}" if mod >= 0 else f"1d20{mod}"
                if not label:
                    label = f"Attack: {atk_name} → {creature_name} ({char_name})"
                damage_dice = atk_damage

    if args.defend and args.from_creature:
        creature_data = _load_creature(args.from_creature)
        if not creature_data:
            print(f"Error: Creature '{args.from_creature}' not found in wiki", file=sys.stderr)
            sys.exit(1)
        mechanics = creature_data.get('mechanics', {})
        creature_name = creature_data.get('name', args.from_creature)
        atk_bonus = int(mechanics.get('attack_bonus', mechanics.get('attack', 0)))
        creature_dmg = mechanics.get('damage', '1d6')
        notation = f"1d20+{atk_bonus}" if atk_bonus >= 0 else f"1d20{atk_bonus}"
        if not char:
            char = _load_character()
        if char:
            char_name = char.get('name', '?')
            equipment = char.get('equipment', {})
            armor = equipment.get('armor', {})
            player_ac = armor.get('base_ac', 10)
            if armor.get('dex_bonus', True):
                dex_mod = (char.get('stats', {}).get('dex', 10) - 10) // 2
                max_dex = armor.get('max_dex')
                if max_dex is not None:
                    dex_mod = min(dex_mod, max_dex)
                player_ac += dex_mod
            ac = player_ac
        if not label:
            label = f"{creature_name} attacks {char_name if char else '?'} [dmg: {creature_dmg}]"
        damage_dice = creature_dmg

    weapon_ammo = atk_ammo
    w_range_n = atk_range_n
    w_range_l = atk_range_l

    if weapon_ammo and (args.attack is not None or args.target):
        campaign_dir = _get_campaign_path()
        if campaign_dir and char:
            import subprocess
            check = subprocess.run(
                ["bash", "tools/dm-inventory.sh", "show", char.get('name', '')],
                capture_output=True, text=True,
                cwd=str(campaign_dir.parent.parent.parent)
            )
            if weapon_ammo not in check.stdout:
                RS = "\033[0m"
                BR = "\033[1;31m"
                print(f"  {BR}\u26a0\ufe0f No {weapon_ammo}! Cannot fire.{RS}")
                sys.exit(0)

    if args.range and w_range_n:
        max_range = int(w_range_l) if w_range_l else int(w_range_n) * 4
        if args.range > max_range:
            print(f"  \u26a0\ufe0f Target beyond maximum range ({max_range}ft)!")
            sys.exit(0)
        elif args.range > int(w_range_n):
            print(f"  {Colors.DIM}\U0001f4cf Long range ({args.range}ft > {w_range_n}ft) \u2192 disadvantage{Colors.RESET}")
            if not args.advantage:
                args.disadvantage = True

    if args.advantage and notation and 'd20' in notation:
        notation = notation.replace('1d20', '2d20kh1')
    elif args.disadvantage and notation and 'd20' in notation:
        notation = notation.replace('1d20', '2d20kl1')

    if not notation:
        parser.print_help()
        sys.exit(1)

    roller = DiceRoller()
    try:
        result = roller.roll(notation)
        line = format_enhanced(result, label=label, dc=dc, ac=ac)
        print(line)

        is_hit = False
        is_save_fail = False
        if ac:
            is_hit = result['total'] >= ac or result.get('natural_20', False)
        if dc and spell_data and spell_data.get('mechanics', {}).get('save_type', spell_data.get('mechanics', {}).get('save')):
            is_save_fail = result['total'] < dc and not result.get('natural_20', False)
        is_crit = result.get('natural_20', False)
        is_fumble = result.get('natural_1', False)

        should_damage = (is_hit or is_save_fail) and not is_fumble
        if damage_dice and should_damage:
            if is_crit:
                parts = damage_dice.split('+')
                dice_part = parts[0]
                m = re.match(r'(\d+)d(\d+)', dice_part)
                if m:
                    crit_dice = f"{int(m.group(1)) * 2}d{m.group(2)}"
                    if len(parts) > 1:
                        crit_dice += '+' + parts[1]
                    dmg_result = roller.roll(crit_dice)
                    dmg_line = format_enhanced(dmg_result, label="CRIT Damage")
                else:
                    dmg_result = roller.roll(damage_dice)
                    dmg_line = format_enhanced(dmg_result, label="Damage")
            else:
                dmg_result = roller.roll(damage_dice)
                dmg_line = format_enhanced(dmg_result, label="Damage")
            print(dmg_line)
        elif damage_dice and not is_hit:
            pass

        if weapon_ammo and (args.attack is not None or args.target):
            import subprocess
            campaign_dir = _get_campaign_path()
            if campaign_dir:
                char_name_ammo = char.get('name', 'Unknown') if char else 'Unknown'
                ammo_result = subprocess.run(
                    ["bash", "tools/dm-inventory.sh", "remove", char_name_ammo, weapon_ammo, "--qty", "1"],
                    capture_output=True, text=True,
                    cwd=str(campaign_dir.parent.parent.parent)
                )
                if ammo_result.returncode == 0 and ammo_result.stdout.strip():
                    print(ammo_result.stdout.strip())
                elif "not found" in (ammo_result.stderr or ""):
                    RS = "\033[0m"
                    BR = "\033[1;31m"
                    print(f"  {BR}\u26a0\ufe0f No {weapon_ammo} left!{RS}")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()