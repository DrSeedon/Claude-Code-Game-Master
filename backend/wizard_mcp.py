"""In-process MCP tools for the campaign creation wizard.

Each tool is awaited directly by the SDK — no subprocess, no shared file.
Results are pushed onto an asyncio.Queue that the /ws/wizard handler drains
between turns.

Usage:
    events = WizardEvents()
    server = build_wizard_mcp(events)  # -> McpSdkServerConfig
    # pass server into ClaudeSDKProvider via mcp_servers={"wizard": server}
    # read events via: event = await events.queue.get()
"""

import asyncio
from typing import Any, Dict

from claude_agent_sdk import tool, create_sdk_mcp_server


class WizardEvents:
    """Queue-based bridge between MCP tools and the WebSocket handler."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    def emit(self, data: Dict[str, Any]) -> None:
        self.queue.put_nowait(data)


def build_wizard_mcp(events: WizardEvents):
    """Build an SDK-native MCP server scoped to one wizard session."""

    @tool(
        "show_choices",
        "Display interactive choices in the sidebar panel for the player. "
        "Each control can be: type 'radio' (single select) with options, "
        "'checkbox' (multi select) with options, or 'text_input' with a "
        "placeholder. Each option has id, title, description, color "
        "(green=recommended / yellow=situational / red=not ideal), comment.",
        {
            "step": str,
            "title": str,
            "submit_label": str,
            "controls": list,
        },
    )
    async def show_choices(args: Dict[str, Any]) -> Dict[str, Any]:
        events.emit({
            "tool": "show_choices",
            "data": {
                "step": args.get("step", ""),
                "title": args.get("title", ""),
                "submit_label": args.get("submit_label", ""),
                "controls": args.get("controls", []),
            },
        })
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Choices displayed to user. Wait for their response.",
                }
            ]
        }

    @tool(
        "clear_choices",
        "Hide the sidebar choices panel. Call when the player has made "
        "their choice via chat or when moving to a new topic without choices.",
        {},
    )
    async def clear_choices(args: Dict[str, Any]) -> Dict[str, Any]:
        events.emit({"tool": "clear_choices"})
        return {"content": [{"type": "text", "text": "Choices panel hidden."}]}

    @tool(
        "create_campaign",
        "Create a campaign with collected settings. Call only after the "
        "player confirms all choices.",
        {
            "name": str,
            "character_name": str,
            "genre": str,
            "tone": str,
            "description": str,
            "modules": list,
            "narrator_style": str,
            "rules": str,
            "character_class": str,
            "character_race": str,
        },
    )
    async def create_campaign(args: Dict[str, Any]) -> Dict[str, Any]:
        # Local import keeps module importable without project setup
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
            events.emit({
                "tool": "create_campaign",
                "campaign_name": name,
                "success": True,
            })
            return {
                "content": [
                    {"type": "text", "text": f"Campaign '{name}' created successfully!"}
                ]
            }

        error = result.get("error", "unknown error")
        events.emit({
            "tool": "create_campaign",
            "error": error,
            "success": False,
        })
        return {
            "content": [
                {"type": "text", "text": f"Error creating campaign: {error}"}
            ],
            "isError": True,
        }

    return create_sdk_mcp_server(
        name="wizard",
        version="2.0.0",
        tools=[show_choices, clear_choices, create_campaign],
    )
