"""Campaign wizard UI tools shared by in-process and stdio MCP transports.

The wizard builds the campaign with ordinary bash tools (dm-campaign.sh,
dm-location.sh, dm-npc.sh, ...). These MCP tools only drive the browser UI:
`show_choices`/`clear_choices` control the sidebar, and `wizard_complete`
signals the frontend that the campaign is ready to play. Each call pushes a
structured event onto `WizardEvents`, which the /ws/wizard handler drains after
the turn and forwards to the browser.
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
    """Execute one wizard UI operation independently of MCP transport."""
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

    if name == "wizard_complete":
        campaign_id = str(args.get("campaign_id") or "").strip()
        if not campaign_id:
            return "Error: wizard_complete requires a campaign_id."
        display_name = str(args.get("display_name") or campaign_id)
        events.push({
            "type": "wizard_complete",
            "campaign_id": campaign_id,
            "display_name": display_name,
        })
        return (
            f"Campaign '{display_name}' is ready. The player can start playing."
        )

    raise ValueError(f"unknown wizard tool: {name}")


def build_wizard_mcp(events: "WizardEvents"):
    """Build an in-process MCP server config bound to `events`.

    Returns a McpSdkServerConfig to pass as mcp_servers={"wizard": <config>}.
    Tool names become mcp__wizard__{show_choices,clear_choices,wizard_complete}.
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
        "wizard_complete",
        "Signal the frontend that the campaign is fully built and ready to play. "
        "Call this once, after creating the campaign with bash tools and the "
        "player confirms. campaign_id is the storage ID used with "
        "dm-campaign.sh create; display_name is the human-readable title.",
        {"campaign_id": str, "display_name": str},
    )
    async def wizard_complete(args: Dict[str, Any]) -> dict:
        return _ok(run_wizard_tool(events, "wizard_complete", args))

    return create_sdk_mcp_server(
        "wizard",
        tools=[
            show_choices,
            clear_choices,
            wizard_complete,
        ],
    )
