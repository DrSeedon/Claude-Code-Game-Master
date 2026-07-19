"""Compile CORE slots and active module rules into one resolved DM profile."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from lib.module_runtime import ModuleRuntime, ModuleRuntimeError


def _resolved_profile(runtime: ModuleRuntime) -> str:
    active = runtime.enabled_module_ids()
    firearm_route = runtime.action_route("combat.attack.firearm")
    mass_route = runtime.action_route("combat.mass")
    damage_profile = runtime.has_provider("combat.damage")

    lines = [
        "# Resolved Gameplay Profile",
        "",
        "This section is authoritative for the current campaign. Follow these "
        "routes directly; do not choose between inactive alternatives.",
        "",
        f"- Active modules: {', '.join(active) if active else 'none'}",
        "- Initiative: `bash tools/dm-roll.sh --initiative "
        "\"<combatant>\" \"<combatant>\" ...`",
        "- Individual ordinary attacks and defenses: use CORE "
        "`tools/dm-roll.sh` auto-combat commands.",
    ]

    if firearm_route:
        lines.append(
            f"- Individual firearm attacks: `{firearm_route} "
            "--attacker \"<name>\" --weapon \"<weapon>\" "
            "--fire-mode <mode> --target \"<target>\"`."
        )
    else:
        lines.append(
            "- Individual ranged attacks: use CORE D&D resolution; automatic "
            "fire, ammunition salvos, penetration, and protection scaling are inactive."
        )

    if mass_route:
        lines.append(
            f"- Group and zone combat: use `{mass_route}` for the entire action."
        )
        if damage_profile:
            lines.append(
                "- Group damage: the active damage-profile provider is applied "
                "inside the group resolver. Do not launch individual weapon "
                "resolver processes for group members."
            )
        else:
            lines.append(
                "- Group damage: use ordinary D&D damage inside the group "
                "resolver; provider-owned weapon and armor fields are inactive."
            )
    else:
        lines.append(
            "- Group combat: no group resolver is active; resolve combatants "
            "individually through the routes above."
        )

    return "\n".join(lines) + "\n"


def compile_rules(
    project_root: Path,
    overview_path: Optional[Path],
    mode: str = "full",
) -> str:
    runtime = ModuleRuntime(
        project_root=project_root,
        overview_path=overview_path,
    )
    active_modules = runtime.active_manifests()

    replacements: dict[str, tuple[str, str]] = {}
    addons: list[tuple[str, str]] = []
    for module_id, manifest, module_dir in active_modules:
        rules_path = module_dir / "rules.md"
        if not rules_path.exists():
            continue
        rules = rules_path.read_text(encoding="utf-8")
        replaces = manifest.get("replaces", [])
        if not isinstance(replaces, list):
            raise ModuleRuntimeError(
                f"Module '{module_id}' has non-list 'replaces'."
            )
        if replaces:
            for slot in replaces:
                if slot in replacements:
                    previous = replacements[slot][0]
                    raise ModuleRuntimeError(
                        f"Modules '{previous}' and '{module_id}' both replace "
                        f"slot '{slot}'."
                    )
                replacements[str(slot)] = (module_id, rules)
        else:
            addons.append((module_id, rules))

    chunks: list[str] = []
    if mode != "core":
        chunks.append(_resolved_profile(runtime))

    if mode == "modules":
        for slot, (module_id, rules) in replacements.items():
            chunks.append(
                f"---\n# MODULE RULES [{slot}]: {module_id}\n\n{rules}"
            )
        for module_id, rules in addons:
            chunks.append(f"---\n# MODULE RULES: {module_id}\n\n{rules}")
        return "\n".join(chunks)

    slots_dir = project_root / ".claude" / "additional" / "dm-slots"
    if not slots_dir.is_dir():
        return "\n".join(chunks)

    preamble = slots_dir / "_preamble.md"
    if preamble.exists():
        chunks.insert(0, preamble.read_text(encoding="utf-8"))

    slot_files = sorted(
        path
        for path in slots_dir.glob("*.md")
        if path.name != "_preamble.md"
    )
    for slot_path in slot_files:
        slot_id = slot_path.stem
        if slot_id in replacements:
            if mode == "core":
                continue
            module_id, rules = replacements[slot_id]
            chunks.append(
                f"---\n# MODULE RULES [{slot_id}]: {module_id}\n\n{rules}"
            )
        else:
            chunks.append(slot_path.read_text(encoding="utf-8"))

    if mode != "core":
        for module_id, rules in addons:
            chunks.append(f"---\n# MODULE RULES: {module_id}\n\n{rules}")
    return "\n".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("overview", nargs="?", type=Path)
    parser.add_argument(
        "--mode",
        choices=("full", "modules", "core"),
        default="full",
    )
    args = parser.parse_args()
    print(compile_rules(args.project_root, args.overview, args.mode))


if __name__ == "__main__":
    main()
