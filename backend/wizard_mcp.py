"""In-process MCP for the campaign-creation wizard.

The DM calls these tools through the SDK's native in-process MCP
(`create_sdk_mcp_server`) — no subprocess, no file polling. Each tool pushes a
structured event onto `WizardEvents`, which the /ws/wizard handler drains after
the turn and forwards to the browser (show_choices / clear_choices /
wizard_complete). `create_campaign` also does the actual campaign creation.
"""

from typing import Any, Dict, List

from claude_agent_sdk import create_sdk_mcp_server, tool


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
        events.push({
            "type": "show_choices",
            "data": {
                "step": args.get("step", ""),
                "title": args.get("title", ""),
                "submit_label": args.get("submit_label", "Выбрать"),
                "controls": args.get("controls", []),
            },
        })
        return _ok("Choices displayed to user. Wait for their response.")

    @tool(
        "clear_choices",
        "Hide the sidebar choices panel. Call when the player answered via chat "
        "or when moving to a topic without choices.",
        {},
    )
    async def clear_choices(args: Dict[str, Any]) -> dict:
        events.push({"type": "clear_choices"})
        return _ok("Choices panel hidden.")

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
        from backend.campaign_api import create_campaign as _create

        name = args.get("name", "")
        character_name = args.get("character_name", "")
        result = _create(
            name=name,
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
            events.push({"type": "create_campaign", "campaign_name": name, "success": True})
            return _ok(f"Campaign '{name}' created successfully!")
        error = result.get("error", "unknown error")
        events.push({"type": "create_campaign", "error": error, "success": False})
        return _ok(f"Error creating campaign: {error}")

    return create_sdk_mcp_server("wizard", tools=[show_choices, clear_choices, create_campaign])
