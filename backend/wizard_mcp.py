#!/usr/bin/env python3
"""MCP server for campaign creation wizard.

Provides show_choices and create_campaign tools that the DM calls
through Claude Code SDK's native MCP integration.

Results are written to a shared file that the WebSocket handler reads.
"""

import json
import sys
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("wizard")

# Shared output file — wizard WS handler reads this
OUTPUT_FILE = os.environ.get("WIZARD_OUTPUT_FILE", "/tmp/wizard-tool-output.jsonl")


def _append_output(data: dict):
    with open(OUTPUT_FILE, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


@mcp.tool()
def show_choices(
    step: str,
    title: str,
    submit_label: str,
    controls: list[dict],
) -> str:
    """Display interactive choices in the sidebar panel for the player.

    Each control can be:
    - type "radio" with options (single select)
    - type "checkbox" with options (multi select)
    - type "text_input" with placeholder

    Each option has: id, title, description, color (green/yellow/red), comment.
    Colors: green=recommended, yellow=situational, red=not ideal.

    Args:
        step: Current wizard step (concept, settings, character, confirm)
        title: Panel title
        submit_label: Submit button text
        controls: List of UI controls
    """
    _append_output({
        "tool": "show_choices",
        "data": {
            "step": step,
            "title": title,
            "submit_label": submit_label,
            "controls": controls,
        }
    })
    return "Choices displayed to user. Wait for their response."


@mcp.tool()
def clear_choices() -> str:
    """Hide the sidebar choices panel. Call when the player has made their choice via chat or when moving to a new conversation topic without choices."""
    _append_output({"tool": "clear_choices"})
    return "Choices panel hidden."


@mcp.tool()
def create_campaign(
    name: str,
    character_name: str,
    genre: str = "",
    tone: str = "",
    description: str = "",
    modules: list[str] | None = None,
    narrator_style: str = "",
    rules: str = "",
    character_class: str = "",
    character_race: str = "",
) -> str:
    """Create campaign with collected settings. Call only after player confirms.

    Args:
        name: Campaign name in kebab-case (e.g. 'zombie-apocalypse')
        character_name: Player character name
        genre: Campaign genre
        tone: Campaign tone
        description: Brief description
        modules: List of module IDs to activate
        narrator_style: Narrator style ID
        rules: Rules template ID
        character_class: Character class (optional)
        character_race: Character race (optional)
    """
    # Import here to avoid circular deps when running as MCP server
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backend.campaign_api import create_campaign as _create

    result = _create(
        name=name,
        genre=genre,
        tone=tone,
        description=description,
        modules=modules,
        narrator_style=narrator_style,
        rules=rules,
        character={
            "name": character_name,
            "class": character_class,
            "race": character_race,
        } if character_name else None,
    )

    if result.get("success"):
        _append_output({"tool": "create_campaign", "campaign_name": name, "success": True})
        return f"Campaign '{name}' created successfully!"
    else:
        error = result.get("error", "unknown error")
        _append_output({"tool": "create_campaign", "error": error, "success": False})
        return f"Error creating campaign: {error}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
