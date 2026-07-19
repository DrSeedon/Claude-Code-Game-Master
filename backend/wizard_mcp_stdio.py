"""Stdio MCP transport for provider-neutral campaign wizard tools."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from backend.wizard_mcp import WizardEvents, encode_wizard_event, run_wizard_tool

mcp = FastMCP("wizard", log_level="ERROR")


class WizardOption(BaseModel):
    id: str
    title: str
    description: str = ""
    color: Literal["green", "yellow", "red"]
    comment: str = ""


class WizardControl(BaseModel):
    type: Literal["radio", "checkbox", "text_input"]
    id: str
    label: str
    options: list[WizardOption] = Field(default_factory=list)
    placeholder: str = ""
    required: bool = False


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
    controls: list[WizardControl],
) -> str:
    """Display interactive campaign choices in the web sidebar."""
    return _result(
        "show_choices",
        {
            "step": step,
            "title": title,
            "submit_label": submit_label,
            "controls": [
                control.model_dump(exclude_none=True)
                for control in controls
            ],
        },
    )


@mcp.tool()
def clear_choices() -> str:
    """Hide the interactive campaign choices."""
    return _result("clear_choices", {})


@mcp.tool()
def save_campaign_template(
    id: str,
    name: str,
    description: str = "",
    genres: list[str] | None = None,
    genre: str = "",
    tone: str = "",
    recommended_for: str = "",
    modules: list[str] | None = None,
    narrator_style: str = "",
    rules: str = "",
    character_name: str = "",
    character_class: str = "",
    character_background: str = "",
) -> str:
    """Persist the current setup as a reusable campaign template."""
    return _result(
        "save_campaign_template",
        {
            "id": id,
            "name": name,
            "description": description,
            "genres": genres,
            "genre": genre,
            "tone": tone,
            "recommended_for": recommended_for,
            "modules": modules,
            "narrator_style": narrator_style,
            "rules": rules,
            "character_name": character_name,
            "character_class": character_class,
            "character_background": character_background,
        },
    )


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
    template_id: str = "",
    character_class: str = "",
    character_race: str = "",
    character_background: str = "",
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
            "template_id": template_id,
            "character_class": character_class,
            "character_race": character_race,
            "character_background": character_background,
        },
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
