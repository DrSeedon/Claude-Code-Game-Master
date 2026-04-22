"""DM system prompt loader.

Provider lifecycle moved to server.py — this module is now purely prompt
assembly. Tools for the API provider are resolved at request time via
tools_registry.get_tool_schemas().
"""

import json
import subprocess
from pathlib import Path


def load_system_prompt() -> str:
    """Assemble DM system prompt: rules + narrator style + campaign rules.

    Sources (in order):
      1. /tmp/dm-rules.md — pre-compiled by UserPromptSubmit hook
         (falls back to running the compiler script if absent)
      2. active campaign's narrator_style from campaign-overview.json
         (falls back to narrator-styles/epic-heroic.md)
      3. active campaign's campaign-rules.md if present

    Returns:
        Combined system prompt. Falls back to a minimal prompt if all
        sources are empty.
    """
    project_root = Path(__file__).parent.parent

    dm_rules_path = Path("/tmp/dm-rules.md")
    if dm_rules_path.exists():
        dm_rules = dm_rules_path.read_text()
    else:
        compiler = project_root / ".claude" / "additional" / "infrastructure" / "dm-active-modules-rules.sh"
        if compiler.exists():
            try:
                dm_rules = subprocess.check_output(
                    ["bash", str(compiler)],
                    cwd=str(project_root),
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                dm_rules = ""
        else:
            dm_rules = ""

    narrator_style = ""
    campaign_rules = ""
    active_campaign_file = project_root / "world-state" / "active-campaign.txt"
    if active_campaign_file.exists():
        campaign_name = active_campaign_file.read_text().strip()
        if campaign_name:
            campaign_dir = project_root / "world-state" / "campaigns" / campaign_name
            overview_path = campaign_dir / "campaign-overview.json"
            if overview_path.exists():
                try:
                    with open(overview_path) as f:
                        overview = json.load(f)
                    narrator = overview.get("narrator_style", {})
                    if narrator:
                        style_rules = narrator.get("rules_raw", "")
                        style_name = narrator.get("name", "")
                        style_desc = narrator.get("description", "")
                        narrator_style = (
                            f"\n---\n# Narrator Style: {style_name}\n\n"
                            f"{style_desc}\n\n{style_rules}\n"
                        )
                except (json.JSONDecodeError, IOError):
                    pass

            rules_path = campaign_dir / "campaign-rules.md"
            if rules_path.exists():
                campaign_rules = f"\n---\n# Campaign Rules\n\n{rules_path.read_text()}\n"

    if not narrator_style:
        default_style = project_root / ".claude" / "additional" / "narrator-styles" / "epic-heroic.md"
        if default_style.exists():
            narrator_style = f"\n---\n{default_style.read_text()}\n"

    prompt = f"{dm_rules}\n{narrator_style}\n{campaign_rules}"
    if len(prompt.strip()) < 100:
        prompt = (
            "# DM System - AI Dungeon Master\n\n"
            "You are an AI Dungeon Master for D&D 5e campaigns. Guide "
            "players, narrate scenes, manage combat, and call tools to "
            "track state. Use tools for dice, inventory, HP/XP, NPCs, "
            "locations, plot threads, and game time. Be descriptive, "
            "engaging, and fair.\n"
        )
    return prompt
