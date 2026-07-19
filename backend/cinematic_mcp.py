"""Provider-neutral cinematic image tool for Claude Agent SDK sessions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from claude_agent_sdk import create_sdk_mcp_server, tool

from backend.media import store_generated_image

CINEMATIC_EVENT_PREFIX = "__DM_CINEMATIC_EVENT__"
DEFAULT_CINEMATIC_MODEL = "gpt-5.6-luna"

_RENDERER_PROMPT = """You are a dedicated cinematic image renderer.
Use the native image generation tool exactly once for the user's supplied scene prompt.
Do not research, edit campaign state, run shell commands, or add story facts.
The generated artifact must be a raster image. End immediately after image generation.
"""


def encode_cinematic_event(event: Mapping[str, Any]) -> str:
    return CINEMATIC_EVENT_PREFIX + json.dumps(
        dict(event),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_cinematic_events(content: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        marker = content.find(CINEMATIC_EVENT_PREFIX, cursor)
        if marker < 0:
            return events
        start = marker + len(CINEMATIC_EVENT_PREFIX)
        try:
            event, consumed = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            cursor = start
            continue
        if isinstance(event, dict):
            events.append(event)
        cursor = start + consumed


def strip_cinematic_events(content: str) -> str:
    decoder = json.JSONDecoder()
    parts: list[str] = []
    cursor = 0
    while True:
        marker = content.find(CINEMATIC_EVENT_PREFIX, cursor)
        if marker < 0:
            parts.append(content[cursor:])
            return "".join(parts).strip()
        parts.append(content[cursor:marker])
        start = marker + len(CINEMATIC_EVENT_PREFIX)
        try:
            _, consumed = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            parts.append(content[marker:start])
            cursor = start
            continue
        cursor = start + consumed


async def render_cinematic_scene(
    *,
    project_root: Path,
    campaign_name: str,
    prompt: str,
) -> dict[str, Any]:
    """Generate one image through Codex and publish it into campaign media."""

    # Import lazily: importing backend.providers.codex_cli initializes the
    # providers package, which also exports ClaudeSDKProvider. Claude imports
    # this module for marker decoding, so a module-level import would cycle.
    from backend.providers.codex_cli import CodexCLIProvider

    model = os.environ.get("DND_CINEMATIC_MODEL") or DEFAULT_CINEMATIC_MODEL
    provider = CodexCLIProvider(
        project_root,
        model_name=model,
        campaign_name=campaign_name,
        reasoning_effort="low",
    )
    image_event = None
    errors: list[str] = []
    try:
        async for event in provider.process_message(
            user_message=(
                "Generate the requested image now with the native image generation tool.\n\n"
                + prompt.strip()
            ),
            system_prompt=_RENDERER_PROMPT,
            model_name=model,
        ):
            if event.type == "image":
                image_event = event
            elif event.type == "error" and event.content:
                errors.append(event.content)
    finally:
        await provider.close()
    if image_event is None:
        detail = errors[-1] if errors else "Codex returned no generated image"
        raise RuntimeError(detail)
    published = store_generated_image(
        project_root / "world-state" / "campaigns" / campaign_name,
        source_path=image_event.metadata.get("source_path"),
        data_url=image_event.metadata.get("data_url"),
    )
    return {
        "type": "image",
        "source_path": str(
            project_root
            / "world-state"
            / "campaigns"
            / campaign_name
            / "media"
            / published.filename
        ),
        "alt": "Cinematic campaign scene",
    }


def build_cinematic_mcp(project_root: Path, campaign_name: str):
    """Build the in-process Claude MCP server for one campaign."""

    @tool(
        "render_scene",
        "Generate one widescreen cinematic campaign scene and publish it to the "
        "player's web chat. The prompt must contain only player-visible canonical "
        "facts and must follow the cinematic-scene skill.",
        {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
            },
            "required": ["prompt"],
        },
    )
    async def render_scene(args: dict[str, Any]) -> dict:
        event = await render_cinematic_scene(
            project_root=project_root,
            campaign_name=campaign_name,
            prompt=str(args.get("prompt") or ""),
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        encode_cinematic_event(event)
                        + "\nCinematic image generated and published."
                    ),
                }
            ]
        }

    return create_sdk_mcp_server("cinematic", tools=[render_scene])
