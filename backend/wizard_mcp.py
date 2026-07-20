"""Campaign wizard tools shared by in-process and stdio MCP transports.

The DM calls these tools through the SDK's native in-process MCP
(`create_sdk_mcp_server`) — no subprocess, no file polling. Each tool pushes a
structured event onto `WizardEvents`, which the /ws/wizard handler drains after
the turn and forwards to the browser (show_choices / clear_choices /
template_saved / wizard_complete). Mutating tools also perform the requested
filesystem operation.
"""

import json
from copy import deepcopy
from typing import Any, Dict, List

from claude_agent_sdk import create_sdk_mcp_server, tool
from backend.campaign_setup import (
    CAMPAIGN_SETUP_SCHEMA,
    CampaignSetupError,
    load_creation_context,
)

WIZARD_EVENT_PREFIX = "__DM_WIZARD_EVENT__"


class WizardEvents:
    """Collects tool-emitted events for one wizard turn.

    Tools run in-process and append here synchronously; the WS handler reads
    `drain()` after the turn to emit show_choices/clear_choices/wizard_complete.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._creation_context: tuple[frozenset[str], str] | None = None

    def push(self, event: Dict[str, Any]) -> None:
        self._events.append(event)

    def drain(self) -> List[Dict[str, Any]]:
        """Return the events collected so far and clear the buffer."""
        out = self._events
        self._events = []
        return out

    def mark_creation_context(
        self,
        modules: list[str],
        template_id: str,
    ) -> None:
        """Remember the exact rules bundle loaded for this wizard session."""
        self._creation_context = (
            frozenset(str(module_id) for module_id in modules),
            str(template_id or ""),
        )

    def creation_context_matches(
        self,
        modules: list[str],
        template_id: str,
    ) -> bool:
        """Return whether creation uses the same inputs as the loaded rules."""
        return self._creation_context == (
            frozenset(str(module_id) for module_id in modules),
            str(template_id or ""),
        )


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def encode_wizard_event(event: dict[str, Any]) -> str:
    """Encode an event into an MCP result that any provider can relay."""
    return WIZARD_EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def decode_wizard_events(content: str) -> list[dict[str, Any]]:
    """Extract wizard events from a provider-neutral tool result."""
    events: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        marker = content.find(WIZARD_EVENT_PREFIX, cursor)
        if marker < 0:
            return events
        start = marker + len(WIZARD_EVENT_PREFIX)
        try:
            event, consumed = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            cursor = start
            continue
        if isinstance(event, dict) and isinstance(event.get("type"), str):
            events.append(event)
        cursor = start + consumed


def run_wizard_tool(events: WizardEvents, name: str, args: Dict[str, Any]) -> str:
    """Execute one wizard operation independently of MCP transport."""
    if name == "show_choices":
        events.push({
            "type": "show_choices",
            "data": {
                "step": args.get("step", ""),
                "title": args.get("title", ""),
                "submit_label": args.get("submit_label", "Выбрать"),
                "controls": args.get("controls", []),
            },
        })
        return "Choices displayed to user. Wait for their response."

    if name == "clear_choices":
        events.push({"type": "clear_choices"})
        return "Choices panel hidden."

    if name == "save_campaign_template":
        from backend.campaign_templates import save_campaign_template

        result = save_campaign_template(args)
        if result.get("success"):
            template = result["template"]
            events.push({
                "type": "template_saved",
                "template": {
                    key: value
                    for key, value in template.items()
                    if key != "rules"
                },
                "success": True,
            })
            return (
                f"Campaign template '{template['name']}' saved successfully."
            )
        error = result.get("error", "unknown error")
        events.push({
            "type": "template_saved",
            "error": error,
            "success": False,
        })
        return f"Error saving campaign template: {error}"

    if name == "load_creation_rules":
        try:
            modules = args.get("modules") or []
            template_id = args.get("template_id", "")
            context = load_creation_context(
                modules,
                template_id,
            )
            events.mark_creation_context(modules, template_id)
            return context
        except CampaignSetupError as exc:
            return f"Error loading campaign creation rules: {exc}"

    if name != "create_campaign":
        raise ValueError(f"unknown wizard tool: {name}")

    from backend.campaign_api import create_campaign as _create

    campaign_id = args.get("campaign_id", "")
    display_name = args.get("display_name", "")
    character_name = args.get("character_name", "")
    modules = args.get("modules") or []
    template_id = args.get("template_id", "")
    if not events.creation_context_matches(modules, template_id):
        error = (
            "Creation rules must be loaded for the exact selected template and "
            "module set before campaign creation"
        )
        events.push({"type": "create_campaign", "error": error, "success": False})
        return f"Error creating campaign: {error}"
    result = _create(
        name=campaign_id,
        display_name=display_name,
        genre=args.get("genre", ""),
        tone=args.get("tone", ""),
        description=args.get("description", ""),
        modules=modules,
        narrator_style=args.get("narrator_style", ""),
        rules=args.get("rules", ""),
        template_id=template_id,
        character={
            "name": character_name,
            "class": args.get("character_class", ""),
            "race": args.get("character_race", ""),
            "background": args.get("character_background", ""),
        } if character_name else None,
        setup=args.get("setup"),
        require_ready=True,
    )
    if result.get("success"):
        events.push({
            "type": "create_campaign",
            "campaign_id": result["id"],
            "display_name": result.get("display_name", display_name),
            "success": True,
        })
        return (
            f"Campaign '{result.get('display_name', display_name)}' created "
            f"successfully with id '{result['id']}'."
        )
    error = result.get("error", "unknown error")
    events.push({"type": "create_campaign", "error": error, "success": False})
    return f"Error creating campaign: {error}"


def build_wizard_mcp(events: "WizardEvents"):
    """Build an in-process MCP server config bound to `events`.

    Returns a McpSdkServerConfig to pass as mcp_servers={"wizard": <config>}.
    Tool names become mcp__wizard__{show_choices,clear_choices,
    load_creation_rules,save_campaign_template,create_campaign}.
    """

    @tool(
        "show_choices",
        "Display interactive choices in the sidebar panel. controls: list of "
        "{type: radio|checkbox|text_input, id, label, options?, placeholder?}. "
        "Each option: {id, title, description, color (green/yellow/red), comment}.",
        {"step": str, "title": str, "submit_label": str, "controls": list},
    )
    async def show_choices(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "show_choices", args))

    @tool(
        "clear_choices",
        "Hide the sidebar choices panel. Call when the player answered via chat "
        "or when moving to a topic without choices.",
        {},
    )
    async def clear_choices(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "clear_choices", args))

    @tool(
        "load_creation_rules",
        "Load authoritative CORE campaign/character creation rules plus only "
        "the selected modules' creation rules. This is mandatory before "
        "building the campaign blueprint.",
        {
            "type": "object",
            "properties": {
                "modules": {"type": "array", "items": {"type": "string"}},
                "template_id": {"type": "string"},
            },
            "required": ["modules"],
        },
    )
    async def load_rules(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "load_creation_rules", args))

    @tool(
        "save_campaign_template",
        "Persist the current wizard configuration as a reusable user template "
        "without creating a campaign.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "genres": {"type": "array", "items": {"type": "string"}},
                "genre": {"type": "string"},
                "tone": {"type": "string"},
                "recommended_for": {"type": "string"},
                "modules": {"type": "array", "items": {"type": "string"}},
                "narrator_style": {"type": "string"},
                "rules": {"type": "string"},
                "character_name": {"type": "string"},
                "character_class": {"type": "string"},
                "character_background": {"type": "string"},
            },
            "required": ["id", "name"],
        },
    )
    async def save_template(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "save_campaign_template", args))

    @tool(
        "create_campaign",
        "Validate and create a ready-to-play campaign after player confirmation. "
        "campaign_id is a lowercase kebab-case storage ID; display_name is the "
        "human title. A complete setup blueprint is mandatory.",
        {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string"},
                "display_name": {"type": "string"},
                "character_name": {"type": "string"},
                "genre": {"type": "string"},
                "tone": {"type": "string"},
                "description": {"type": "string"},
                "modules": {"type": "array", "items": {"type": "string"}},
                "narrator_style": {"type": "string"},
                "rules": {"type": "string"},
                "template_id": {"type": "string"},
                "character_class": {"type": "string"},
                "character_race": {"type": "string"},
                "character_background": {"type": "string"},
                "setup": deepcopy(CAMPAIGN_SETUP_SCHEMA),
            },
            "required": [
                "campaign_id",
                "display_name",
                "character_name",
                "modules",
                "setup",
            ],
        },
    )
    async def create_campaign(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "create_campaign", args))

    return create_sdk_mcp_server(
        "wizard",
        tools=[
            show_choices,
            clear_choices,
            load_rules,
            save_template,
            create_campaign,
        ],
    )
