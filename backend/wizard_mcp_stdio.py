"""Stdio MCP transport for provider-neutral campaign wizard UI tools."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from backend.wizard_mcp import WizardEvents, encode_wizard_event, run_wizard_tool

mcp = FastMCP("wizard", log_level="ERROR")
_events = WizardEvents()


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
    message = run_wizard_tool(_events, name, arguments)
    encoded = "\n".join(
        encode_wizard_event(event) for event in _events.drain()
    )
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
def wizard_complete(campaign_id: str, display_name: str = "") -> str:
    """Signal the frontend that the campaign is built and ready to play."""
    return _result(
        "wizard_complete",
        {"campaign_id": campaign_id, "display_name": display_name},
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
