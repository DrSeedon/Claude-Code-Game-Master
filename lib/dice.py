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
            RESET = ""
            RED = ""
            GREEN = ""
            YELLOW = ""
            CYAN = ""
            BOLD = ""
            BOLD_RED = ""
            BOLD_GREEN = ""
            BOLD_YELLOW = ""
            BOLD_CYAN = ""
            DIM = ""

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
    RS = "\033[0m"
    C = "\033[36m"
    G = "\033[32m"
    BG = "\033[1;32m"
    R = "\033[31m"
    BR = "\033[1;31m"
    BY = "\033[1;33m"
    DM = "\033[2m"

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
    """Get save modifier from character."""
    saves = char.get('saves', {})
    for name, val in saves.items():
        if name.lower() == save_name.lower():
            return int(val), name
    stats = char.get('stats', {})
    stat_mods = {
        'str': (stats.get('str', 10) - 10) // 2,
        'dex': (stats.get('dex', 10) - 10) // 2,
        'con': (stats.get('con', 10) - 10) // 2,
        'int': (stats.get('int', 10) - 10) // 2,
        'wis': (stats.get('wis', 10) - 10) // 2,
        'cha': (stats.get('cha', 10) - 10) // 2,
    }
    for abbr, mod in stat_mods.items():
        if abbr == save_name.lower()[:3]:
            return mod, abbr
    return None, None


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
        return total, name, damage

    skills = char.get('skills', {})
    melee = skills.get('ближний бой', {})
    mod = melee.get('total', 0) if isinstance(melee, dict) else int(melee) if melee else 0
    return mod, 'ближний бой', '1d4'


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
    parser.add_argument("--target", "-t", help="Target creature (auto-lookup AC from wiki, auto-damage on hit)")
    parser.add_argument("--defend", action="store_true", help="Creature attacks player (use with --from)")
    parser.add_argument("--from", dest="from_creature", help="Creature attacking (auto-lookup attack+damage from wiki)")
    parser.add_argument("--advantage", "--adv", action="store_true", help="Roll with advantage (2d20kh1)")
    parser.add_argument("--disadvantage", "--dis", action="store_true", help="Roll with disadvantage (2d20kl1)")
    args = parser.parse_args()

    char = None
    notation = args.notation
    label = args.label
    dc = args.dc
    ac = args.ac

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
        mod, atk_name, atk_damage = _resolve_attack(char, args.attack if args.attack else None)
        notation = f"1d20+{mod}" if mod >= 0 else f"1d20{mod}"
        if not label:
            label = f"Attack: {atk_name} ({char_name}) [dmg: {atk_damage}]"

    creature_data = None
    damage_dice = None

    if args.target:
        creature_data = _load_creature(args.target)
        if not creature_data:
            print(f"Error: Creature '{args.target}' not found in wiki", file=sys.stderr)
            sys.exit(1)
        mechanics = creature_data.get('mechanics', {})
        creature_ac = int(mechanics.get('ac', mechanics.get('AC', 10)))
        ac = creature_ac
        creature_name = creature_data.get('name', args.target)
        if args.attack is not None:
            if not label:
                label = f"Attack: {atk_name} → {creature_name} ({char_name})"
            damage_dice = atk_damage
        elif args.skill:
            pass
        else:
            if not char:
                char = _load_character()
            if char:
                char_name = char.get('name', '?')
                mod, atk_name, atk_damage = _resolve_attack(char, None)
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
        if ac:
            is_hit = result['total'] >= ac or result.get('natural_20', False)
        is_crit = result.get('natural_20', False)
        is_fumble = result.get('natural_1', False)

        if damage_dice and is_hit and not is_fumble:
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

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()