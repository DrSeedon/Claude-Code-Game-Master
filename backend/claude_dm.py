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
    # path separators / traversal / leading dot so a bad value can't escape the
    # campaigns dir. (The WS handler already validates; this guards other callers.)
    if campaign_name and (
        "/" in campaign_name or "\\" in campaign_name
        or ".." in campaign_name or campaign_name.startswith(".")
    ):
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
    # `narrator_style` in overview.json can be a STRING id (wizard/API — the common
    # case) or an embedded object; handle both, never crash on the string form.
    narrator_style = ""
    styles_dir = project_root / ".claude" / "additional" / "narrator-styles"
    if campaign_name:
        overview_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-overview.json"
        if overview_path.exists():
            try:
                with open(overview_path) as f:
                    overview = json.load(f)
                narrator_data = overview.get("narrator_style", "")
                if isinstance(narrator_data, str) and narrator_data.strip():
                    style_file = styles_dir / f"{narrator_data.strip()}.md"
                    if style_file.exists():
                        narrator_style = f"\n---\n{style_file.read_text()}\n"
                elif isinstance(narrator_data, dict) and narrator_data:
                    style_rules = narrator_data.get("rules_raw", "")
                    style_name = narrator_data.get("name", "")
                    style_desc = narrator_data.get("description", "")
                    narrator_style = f"\n---\n# Narrator Style: {style_name}\n\n{style_desc}\n\n{style_rules}\n"
            except (json.JSONDecodeError, IOError):
                pass

    if not narrator_style:
        default_style_path = styles_dir / "epic-heroic.md"
        if default_style_path.exists():
            narrator_style = f"\n---\n{default_style_path.read_text()}\n"

    # Step 3: Campaign-specific rules.
    campaign_rules = ""
    if campaign_name:
        rules_path = project_root / "world-state" / "campaigns" / campaign_name / "campaign-rules.md"
        if rules_path.exists():
            campaign_rules = f"\n---\n# Campaign Rules\n\n{rules_path.read_text()}\n"

    # Step 4: Active-campaign context — so the DM knows it is ALREADY inside this
    # campaign and should just run the session (narrate + offer actions), NOT show a
    # campaign menu / list. Without this the DM treats every turn as a fresh boot.
    campaign_context = _campaign_context(project_root, campaign_name) if campaign_name else ""

    # Step 5: Provider-neutral cinematic contract. Codex has native image
    # generation; Claude receives the equivalent in-process MCP tool.
    cinematic_context = (
        _cinematic_context(project_root, campaign_name)
        if campaign_name
        else ""
    )

    # Combine prompts
    system_prompt = (
        f"{dm_rules}\n{narrator_style}\n{campaign_rules}\n"
        f"{campaign_context}\n{cinematic_context}"
    )

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


def _campaign_context(project_root: Path, campaign_name: str) -> str:
    """A short 'you are inside this campaign' block: setting + character + location.

    Tells the DM to resume/run THIS session rather than boot a menu. Best-effort —
    a missing overview or character just yields a thinner block, never an error.
    """
    campaign_dir = project_root / "world-state" / "campaigns" / campaign_name
    lines = [f'# Current Campaign: "{campaign_name}"', ""]

    overview_path = campaign_dir / "campaign-overview.json"
    if overview_path.exists():
        try:
            ov = json.loads(overview_path.read_text(encoding="utf-8"))
            for label, key in (("Genre", "genre"), ("Tone", "tone"), ("Setting", "description")):
                val = ov.get(key)
                if isinstance(val, str) and val.strip():
                    lines.append(f"- {label}: {val.strip()}")
        except (json.JSONDecodeError, IOError):
            pass

    # Character (best-effort — game_state reads world.json via WorldGraph).
    try:
        from backend.game_state import get_character_status
        status = get_character_status(campaign_dir=campaign_dir, force_refresh=True)
        if not status.get("error"):
            name = status.get("name") or "the player character"
            loc = status.get("location")
            lines.append(f"- Character: {name} (HP {status.get('hp')}/{status.get('max_hp')}, XP {status.get('xp')})")
            if loc:
                lines.append(f"- Location: {loc}")
    except Exception:
        pass

    lines += [
        "",
        "You are ALREADY running this campaign. When the player says \"Начать игру\" or sends "
        "their first message, immediately narrate the current scene and offer concrete actions — "
        "do NOT list campaigns, do NOT ask which campaign to play, do NOT run any campaign-selection flow.",
    ]
    return "\n---\n" + "\n".join(lines) + "\n"


def _cinematic_context(project_root: Path, campaign_name: str) -> str:
    """Return the shared scene-art skill plus this campaign's visual policy."""

    skill_path = project_root / "codex-skills" / "cinematic-scene" / "SKILL.md"
    if not skill_path.exists():
        return ""

    config: dict = {}
    overview_path = (
        project_root
        / "world-state"
        / "campaigns"
        / campaign_name
        / "campaign-overview.json"
    )
    try:
        overview = json.loads(overview_path.read_text(encoding="utf-8"))
        raw_config = overview.get("cinematic_visuals")
        if isinstance(raw_config, dict):
            config = raw_config
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    enabled = config.get("enabled") is True
    frequency = str(config.get("frequency") or "explicit-only")
    aspect_ratio = str(config.get("aspect_ratio") or "16:9")
    presentation = str(config.get("presentation") or "game-loading-screen")
    automatic_policy = (
        "Automatic major-beat images are enabled."
        if enabled
        else "Automatic images are disabled; generate only when the player explicitly asks."
    )
    runtime_contract = f"""---
# Cinematic Scene Runtime

- {automatic_policy}
- Frequency: {frequency}
- Aspect ratio: {aspect_ratio}
- Presentation: {presentation}
- In Claude Agent SDK, call `mcp__cinematic__render_scene`.
- In Codex app-server, use native image generation.
- Invoke image generation as the final action of the turn.

"""
    try:
        skill = skill_path.read_text(encoding="utf-8")
    except OSError:
        return runtime_contract
    return runtime_contract + skill + "\n"
