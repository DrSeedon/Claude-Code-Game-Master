#!/usr/bin/env python3
"""Enhanced dice roller with labels, DC/AC checks, and transparent output."""

import sys
from pathlib import Path

project_root = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(project_root))

from lib.dice import DiceRoller


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced dice roller")
    parser.add_argument("notation", help="Dice notation (e.g. 1d20+5)")
    parser.add_argument("--label", "-l", help="Roll description (e.g. 'Perception (Рекс)')")
    parser.add_argument("--dc", type=int, help="Difficulty Class to check against")
    parser.add_argument("--ac", type=int, help="Armor Class to check against (attack roll)")
    args = parser.parse_args()

    roller = DiceRoller()
    result = roller.roll(args.notation)

    output = format_enhanced(result, label=args.label, dc=args.dc, ac=args.ac)
    print(output)


def format_enhanced(result, label=None, dc=None, ac=None):
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

    if result["type"] == "advantage":
        discarded_str = "+".join(str(r) for r in result["discarded"])
        roll_str += f" (dropped {discarded_str})"
    elif result["type"] == "disadvantage":
        discarded_str = "+".join(str(r) for r in result["discarded"])
        roll_str += f" (dropped {discarded_str})"

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


if __name__ == "__main__":
    main()
