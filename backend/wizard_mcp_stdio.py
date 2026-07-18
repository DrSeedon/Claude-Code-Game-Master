"""Stdio MCP transport for provider-neutral campaign wizard tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from backend.wizard_mcp import WizardEvents, encode_wizard_event, run_wizard_tool

mcp = FastMCP("wizard", log_level="ERROR")


def _result(name: str, arguments: dict[str, Any]) -> str:
    events = WizardEvents()
    message = run_wizard_tool(events, name, arguments)
    encoded = "\n".join(encode_wizard_event(event) for event in events.drain())
    return f"{encoded}\n{message}" if encoded else message


@mcp.tool()
def show_choices(
    step: str,
    title: str,
    submit_label: str,
    controls: list[dict[str, Any]],
) -> str:
    """Display interactive campaign choices in the web sidebar."""
    return _result(
        "show_choices",
        {
            "step": step,
            "title": title,
            "submit_label": submit_label,
            "controls": controls,
        },
    )


@mcp.tool()
def clear_choices() -> str:
    """Hide the interactive campaign choices."""
    return _result("clear_choices", {})


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
    """Create a campaign after the player confirms its settings."""
    return _result(
        "create_campaign",
        {
            "name": name,
            "character_name": character_name,
            "genre": genre,
            "tone": tone,
            "description": description,
            "modules": modules,
            "narrator_style": narrator_style,
            "rules": rules,
            "character_class": character_class,
            "character_race": character_race,
        },
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
