"""DM Agent - System prompt builder and tool calling loop."""

import json
import subprocess
from pathlib import Path
from typing import Optional


def load_system_prompt() -> str:
    """Load DM rules and narrator styles from .claude/additional/.

    Loads pre-compiled DM rules from /tmp/dm-rules.md (if exists) or compiles
    them from .claude/additional/dm-slots/. Appends narrator style from active
    campaign's campaign-overview.json or falls back to default style.

    Returns:
        str: Complete system prompt combining DM rules and narrator style
    """
    project_root = Path(__file__).parent.parent

    # Step 1: Load DM rules
    dm_rules_path = Path("/tmp/dm-rules.md")

    if dm_rules_path.exists():
        # Pre-compiled rules exist (created by infrastructure hooks)
        dm_rules = dm_rules_path.read_text()
    else:
        # Fallback: compile rules from slots
        rules_compiler = project_root / ".claude" / "additional" / "infrastructure" / "dm-active-modules-rules.sh"

        if rules_compiler.exists():
            try:
                dm_rules = subprocess.check_output(
                    ["bash", str(rules_compiler)],
                    cwd=str(project_root),
                    text=True,
                    stderr=subprocess.DEVNULL
                )
            except subprocess.CalledProcessError:
                dm_rules = ""
        else:
            dm_rules = ""

    # Step 2: Load narrator style from campaign-overview.json or use default
    narrator_style = ""

    # Try to load from active campaign
    active_campaign_file = project_root / "world-state" / "active-campaign.txt"
    if active_campaign_file.exists():
        campaign_name = active_campaign_file.read_text().strip()
        if campaign_name:
            overview_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-overview.json"
            if overview_path.exists():
                try:
                    with open(overview_path) as f:
                        overview = json.load(f)

                    # Extract narrator style rules from overview
                    narrator_data = overview.get("narrator_style", {})
                    if narrator_data:
                        style_rules = narrator_data.get("rules_raw", "")
                        style_name = narrator_data.get("name", "")
                        style_desc = narrator_data.get("description", "")

                        narrator_style = f"\n---\n# Narrator Style: {style_name}\n\n{style_desc}\n\n{style_rules}\n"
                except (json.JSONDecodeError, IOError):
                    pass

    # Fallback to default narrator style if none found
    if not narrator_style:
        default_style_path = project_root / ".claude" / "additional" / "narrator-styles" / "epic-heroic.md"
        if default_style_path.exists():
            narrator_style = f"\n---\n{default_style_path.read_text()}\n"

    # Combine prompts
    system_prompt = f"{dm_rules}\n{narrator_style}"

    # Ensure we return something meaningful
    if len(system_prompt.strip()) < 100:
        # Fallback minimal prompt
        system_prompt = """# DM System - AI Dungeon Master

You are an AI Dungeon Master for D&D 5e campaigns. Guide players through their adventure, narrate scenes, manage combat, and call appropriate tools to track game state.

Use the available tools to:
- Roll dice for checks, saves, and attacks
- Manage inventory, HP, XP, and gold
- Track NPCs, locations, and plot threads
- Advance game time

Be descriptive, engaging, and fair. Follow D&D 5e rules. Make the game fun!
"""

    return system_prompt
