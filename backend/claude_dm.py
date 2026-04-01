"""DM Agent - System prompt builder and tool calling loop."""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from backend.tools_registry import get_tool_schemas
from backend.providers.factory import create_provider


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

    # Step 3: Load campaign-specific rules
    campaign_rules = ""
    if active_campaign_file.exists():
        campaign_name = active_campaign_file.read_text().strip()
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


async def process_message(
    user_message: str,
    conversation_history: List[Dict[str, Any]],
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    model_name: str = "claude-3-5-sonnet-20241022",
    system_prompt: Optional[str] = None,
    project_root: Optional[Path] = None
) -> AsyncGenerator[str, None]:
    """
    Process user message through DM agent with tool calling loop.

    Использует фабрику провайдеров для автоматического выбора между:
    - Anthropic API (если есть ANTHROPIC_API_KEY)
    - Claude SDK (если есть подписка, не требует API ключ)

    Args:
        user_message: Player's input message
        conversation_history: List of conversation messages (modified in-place)
        provider_type: Тип провайдера ("auto", "api", "sdk")
        api_key: Anthropic API key (опционально, берется из env для "auto")
        model_name: Claude model name to use
        system_prompt: System prompt (loaded from load_system_prompt if None)
        project_root: Project root directory (нужен для SDK провайдера)

    Yields:
        Text chunks from Claude's streaming response
    """
    # Load system prompt if not provided
    if system_prompt is None:
        system_prompt = load_system_prompt()

    # Получаем project_root если не передан
    if project_root is None:
        project_root = Path(__file__).parent.parent

    # Создаем провайдер через фабрику
    provider = create_provider(
        provider_type=provider_type,
        api_key=api_key,
        project_root=project_root
    )

    # Получаем tool schemas
    tools = get_tool_schemas()

    # Делегируем обработку сообщения провайдеру
    async for text_chunk in provider.process_message(
        user_message=user_message,
        conversation_history=conversation_history,
        system_prompt=system_prompt,
        model_name=model_name,
        tools=tools
    ):
        yield text_chunk
