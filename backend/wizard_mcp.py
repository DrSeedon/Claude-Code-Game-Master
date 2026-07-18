"""Campaign wizard tools shared by in-process and stdio MCP transports.

The DM calls these tools through the SDK's native in-process MCP
(`create_sdk_mcp_server`) — no subprocess, no file polling. Each tool pushes a
structured event onto `WizardEvents`, which the /ws/wizard handler drains after
the turn and forwards to the browser (show_choices / clear_choices /
wizard_complete). `create_campaign` also does the actual campaign creation.
"""

import json
from typing import Any, Dict, List

from claude_agent_sdk import create_sdk_mcp_server, tool

WIZARD_EVENT_PREFIX = "__DM_WIZARD_EVENT__"


class WizardEvents:
    """Collects tool-emitted events for one wizard turn.

    Tools run in-process and append here synchronously; the WS handler reads
    `drain()` after the turn to emit show_choices/clear_choices/wizard_complete.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def push(self, event: Dict[str, Any]) -> None:
        self._events.append(event)

    def drain(self) -> List[Dict[str, Any]]:
        """Return the events collected so far and clear the buffer."""
        out = self._events
        self._events = []
        return out


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

    if name != "create_campaign":
        raise ValueError(f"unknown wizard tool: {name}")

    from backend.campaign_api import create_campaign as _create

    campaign_name = args.get("name", "")
    character_name = args.get("character_name", "")
    result = _create(
        name=campaign_name,
        genre=args.get("genre", ""),
        tone=args.get("tone", ""),
        description=args.get("description", ""),
        modules=args.get("modules") or None,
        narrator_style=args.get("narrator_style", ""),
        rules=args.get("rules", ""),
        character={
            "name": character_name,
            "class": args.get("character_class", ""),
            "race": args.get("character_race", ""),
        } if character_name else None,
    )
    if result.get("success"):
        events.push({
            "type": "create_campaign",
            "campaign_name": campaign_name,
            "success": True,
        })
        return f"Campaign '{campaign_name}' created successfully!"
    error = result.get("error", "unknown error")
    events.push({"type": "create_campaign", "error": error, "success": False})
    return f"Error creating campaign: {error}"


def build_wizard_mcp(events: "WizardEvents"):
    """Build an in-process MCP server config bound to `events`.

    Returns a McpSdkServerConfig to pass as mcp_servers={"wizard": <config>}.
    Tool names become mcp__wizard__{show_choices,clear_choices,create_campaign}.
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
        "create_campaign",
        "Create the campaign with collected settings. Call only after the player "
        "confirms. name must be kebab-case (e.g. 'zombie-apocalypse').",
        # Full JSON Schema: only name + character_name are required. The dict-shorthand
        # ({field: type}) would mark EVERY field required and reject normal calls.
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "character_name": {"type": "string"},
                "genre": {"type": "string"},
                "tone": {"type": "string"},
                "description": {"type": "string"},
                "modules": {"type": "array", "items": {"type": "string"}},
                "narrator_style": {"type": "string"},
                "rules": {"type": "string"},
                "character_class": {"type": "string"},
                "character_race": {"type": "string"},
            },
            "required": ["name", "character_name"],
        },
    )
    async def create_campaign(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "create_campaign", args))

    return create_sdk_mcp_server("wizard", tools=[show_choices, clear_choices, create_campaign])
