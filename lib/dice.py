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


def format_enhanced(result, label=None, dc=None, ac=None):
    """Format roll result with label, DC/AC check, and verdict. Used by dm-roll.sh."""
    rolls = result.get("kept", result["rolls"])
    rolls_str = "+".join(str(r) for r in rolls)

    mod = result.get("modifier", 0)
    total = result["total"]
    nat20 = result.get("natural_20", False)
    nat1 = result.get("natural_1", False)

    header = "🎲"
    if label:
        header += f" {label}"
    if dc:
        header += f" vs DC {dc}:"
    elif ac:
        header += f" vs AC {ac}:"
    else:
        header += ":"

    roll_str = f"[{rolls_str}]"

    if result["type"] in ("advantage", "disadvantage"):
        discarded_str = "+".join(str(r) for r in result["discarded"])
        roll_str += f" ~({discarded_str})~"

    if mod != 0:
        roll_str += f" {mod:+d}"
    roll_str += f" = {total}"

    if nat20:
        verdict = "⚔ CRITICAL!"
    elif nat1:
        verdict = "💀 FUMBLE!"
    elif dc:
        verdict = "✓ SUCCESS" if total >= dc else "✗ FAIL"
    elif ac:
        verdict = "✓ HIT!" if total >= ac else "✗ MISS"
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


def main():
    """CLI interface for dice rolling"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Dice roller with labels and DC/AC checks")
    parser.add_argument("notation", help="Dice notation (e.g. 1d20+5, 2d20kh1+3)")
    parser.add_argument("--label", "-l", help="Roll description (e.g. 'Perception (Рекс)')")
    parser.add_argument("--dc", type=int, help="Difficulty Class to check against")
    parser.add_argument("--ac", type=int, help="Armor Class to check against")
    args = parser.parse_args()

    roller = DiceRoller()
    try:
        result = roller.roll(args.notation)
        if args.label or args.dc or args.ac:
            print(format_enhanced(result, label=args.label, dc=args.dc, ac=args.ac))
        else:
            print(format_enhanced(result))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()