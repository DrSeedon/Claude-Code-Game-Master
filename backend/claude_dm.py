"""DM Agent - System prompt builder."""

import json
import os
import subprocess
from pathlib import Path


def load_system_prompt(campaign_name: str | None = None) -> str:
    """Build the DM system prompt for a specific campaign.

    Combines the compiled DM rules (dm-slots + the campaign's enabled modules),
    the campaign's narrator style, and its campaign-rules.md. When `campaign_name`
    is given (the web sockets are campaign-addressed), everything is scoped to that
    campaign — NOT the global active-campaign.txt, which would be wrong or empty and
    would race across concurrent sessions.

    Args:
        campaign_name: Campaign to build the prompt for. None → fall back to the
            global active campaign (legacy / CLI use).

    Returns:
        str: DM rules + narrator style + campaign rules.
    """
    project_root = Path(__file__).parent.parent

    # Resolve which campaign to scope to.
    if not campaign_name:
        active_campaign_file = project_root / "world-state" / "active-campaign.txt"
        if active_campaign_file.exists():
            campaign_name = active_campaign_file.read_text().strip() or None

    # Defense-in-depth: campaign_name feeds a dir path + a bash env var. Reject any
    # path separators / traversal so a bad value can't escape the campaigns dir.
    if campaign_name and ("/" in campaign_name or "\\" in campaign_name or ".." in campaign_name):
        campaign_name = None

    # Step 1: Compile DM rules for this campaign (dm-slots + its modules).
    # The /tmp cache is campaign-blind, so only use it when no campaign is scoped.
    dm_rules = ""
    dm_rules_cache = Path("/tmp/dm-rules.md")
    if not campaign_name and dm_rules_cache.exists():
        dm_rules = dm_rules_cache.read_text()
    else:
        rules_compiler = project_root / ".claude" / "additional" / "infrastructure" / "dm-active-modules-rules.sh"
        if rules_compiler.exists():
            env = dict(os.environ)
            if campaign_name:
                env["DM_ACTIVE_CAMPAIGN"] = campaign_name  # per-call override, race-free
            try:
                dm_rules = subprocess.check_output(
                    ["bash", str(rules_compiler)],
                    cwd=str(project_root), text=True,
                    stderr=subprocess.DEVNULL, env=env,
                )
            except subprocess.CalledProcessError:
                dm_rules = ""

    # Step 2: Narrator style from the campaign's overview, else default.
    narrator_style = ""
    if campaign_name:
        overview_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-overview.json"
        if overview_path.exists():
            try:
                with open(overview_path) as f:
                    overview = json.load(f)
                narrator_data = overview.get("narrator_style", {})
                if narrator_data:
                    style_rules = narrator_data.get("rules_raw", "")
                    style_name = narrator_data.get("name", "")
                    style_desc = narrator_data.get("description", "")
                    narrator_style = f"\n---\n# Narrator Style: {style_name}\n\n{style_desc}\n\n{style_rules}\n"
            except (json.JSONDecodeError, IOError):
                pass

    if not narrator_style:
        default_style_path = project_root / ".claude" / "additional" / "narrator-styles" / "epic-heroic.md"
        if default_style_path.exists():
            narrator_style = f"\n---\n{default_style_path.read_text()}\n"

    # Step 3: Campaign-specific rules.
    campaign_rules = ""
    if campaign_name:
        rules_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-rules.md"
        if rules_path.exists():
            campaign_rules = f"\n---\n# Campaign Rules\n\n{rules_path.read_text()}\n"

    # Combine prompts
    system_prompt = f"{dm_rules}\n{narrator_style}\n{campaign_rules}"

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
