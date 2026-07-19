"""Provider via Claude Agent SDK (subscription, no API key required)."""

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from typing import AsyncGenerator, Dict, Optional
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    StreamEvent,
    UserMessage,
)
from claude_agent_sdk.types import ToolResultBlock

from backend.runtime.events import AgentEvent, ContextUsage
from backend.cinematic_mcp import (
    decode_cinematic_events,
    strip_cinematic_events,
)

logger = logging.getLogger(__name__)


def _proxy_env() -> dict:
    env = {}
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
        if os.environ.get(key):
            env[key] = os.environ[key]
            env[key.lower()] = os.environ[key]
    return env


def _rate_limit_info(err: Exception) -> Optional[dict]:
    """If `err` is a rate/session/usage limit, return {message, retry_after?} else None.

    The SDK surfaces these as plain exceptions (no typed class), so match on the
    message text and pull a seconds value from 'retry-after'/'try again in Ns' if present.
    """
    import re
    msg = str(err).lower()
    signals = ("rate limit", "rate_limit", "429", "too many requests",
               "usage limit", "session limit", "overloaded")
    if not any(s in msg for s in signals):
        return None
    retry_after = None
    m = re.search(r"(?:retry[- ]after|try again in|wait)\D{0,12}(\d+)", msg)
    if m:
        retry_after = int(m.group(1))
    out: dict = {"content": str(err)}
    if retry_after is not None:
        out["retry_after"] = retry_after
    return out


def _is_stale_resume_error(err: Exception) -> bool:
    """Return whether Claude rejected a persisted conversation identifier."""

    message = str(err).lower()
    missing = ("not found", "does not exist", "unknown", "invalid", "expired")
    return (
        ("session id" in message or "resume" in message or "conversation" in message)
        and any(signal in message for signal in missing)
    )


def _extract_tool_result(block: ToolResultBlock) -> str:
    raw = getattr(block, "content", "")
    if isinstance(raw, list):
        return "\n".join(item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in raw)
    if isinstance(raw, dict):
        return raw.get("text", str(raw))
    return str(raw)


def _tool_result_events(block: ToolResultBlock) -> list[AgentEvent]:
    raw = _extract_tool_result(block)
    clean = strip_cinematic_events(raw)
    metadata = {
        "tool_use_id": str(getattr(block, "tool_use_id", "") or ""),
        "is_error": bool(block.is_error),
    }
    events = [
        AgentEvent(
            "tool_result",
            clean or "Cinematic image generated and published.",
            metadata,
        )
    ]
    for image in decode_cinematic_events(raw):
        if image.get("type") != "image" or not image.get("source_path"):
            continue
        events.append(
            AgentEvent(
                "image",
                "",
                {
                    "tool_use_id": metadata["tool_use_id"],
                    "source_path": str(image["source_path"]),
                    "alt": str(image.get("alt") or "Cinematic campaign scene"),
                },
            )
        )

    content = block.content if isinstance(block.content, list) else []
    for item in content:
        if not isinstance(item, Mapping) or item.get("type") != "image":
            continue
        source = item.get("source") or {}
        if not isinstance(source, Mapping):
            continue
        if source.get("type") == "base64" and source.get("data"):
            media_type = str(source.get("media_type") or "image/png")
            events.append(
                AgentEvent(
                    "image",
                    "",
                    {
                        "tool_use_id": metadata["tool_use_id"],
                        "data_url": f"data:{media_type};base64,{source['data']}",
                        "alt": "Cinematic campaign scene",
                    },
                )
            )
    return events


def _context_usage_from_sdk(raw: Mapping[str, object]) -> ContextUsage:
    """Preserve Claude Code's exact `/context` category breakdown."""
    breakdown: dict[str, int] = {}
    categories = raw.get("categories")
    if isinstance(categories, list):
        for category in categories:
            if not isinstance(category, Mapping):
                continue
            name = str(category.get("name") or "").strip()
            try:
                tokens = max(0, int(category.get("tokens") or 0))
            except (TypeError, ValueError):
                tokens = 0
            if name and tokens:
                breakdown[name] = breakdown.get(name, 0) + tokens

    try:
        used = max(0, int(raw.get("totalTokens") or 0))
    except (TypeError, ValueError):
        used = 0
    try:
        total = max(0, int(raw.get("maxTokens") or raw.get("rawMaxTokens") or 0))
    except (TypeError, ValueError):
        total = 0
    return ContextUsage(
        used_tokens=used,
        total_tokens=total or ClaudeSDKProvider.CONTEXT_WINDOW,
        breakdown=breakdown,
    )


class ClaudeSDKProvider:

    # Claude context window (Sonnet/Opus). Used to turn token counts into a %.
    CONTEXT_WINDOW = 200_000

    def __init__(
        self,
        project_root: Path,
        model_name: str = "claude-sonnet-5",
        campaign_name: str | None = None,
        resume_session_id: str | None = None,
        environment: dict[str, str] | None = None,
    ):
        self.project_root = project_root
        self.model_name = model_name
        self.campaign_name = campaign_name
        self._client: Optional[ClaudeSDKClient] = None
        self._session_id: Optional[str] = resume_session_id
        self._environment = dict(environment or {})
        self._last_usage: Optional[dict] = None  # token counts from the latest ResultMessage
        self._last_context_usage: ContextUsage | None = None

    def _make_options(self, model_name: str, system_prompt: str, mcp_servers: Optional[Dict]) -> ClaudeAgentOptions:
        process_env = {**_proxy_env(), **self._environment}
        process_env["NO_COLOR"] = "1"
        process_env["TERM"] = "dumb"
        if self.campaign_name:
            process_env["DM_ACTIVE_CAMPAIGN"] = self.campaign_name
        options = ClaudeAgentOptions(
            model=model_name or self.model_name,
            cwd=str(self.project_root.resolve()),
            max_turns=100,
            permission_mode="bypassPermissions",
            max_buffer_size=50 * 1024 * 1024,
            include_partial_messages=True,
            env=process_env,
        )
        if self._session_id:
            options.resume = self._session_id
        else:
            options.system_prompt = system_prompt

        if mcp_servers:
            options.mcp_servers = mcp_servers
            mcp_tool_names = []
            for server_name in mcp_servers:
                if server_name == "wizard":
                    mcp_tool_names.extend([
                        f"mcp__{server_name}__show_choices",
                        f"mcp__{server_name}__clear_choices",
                        f"mcp__{server_name}__create_campaign",
                    ])
                elif server_name == "cinematic":
                    mcp_tool_names.append("mcp__cinematic__render_scene")
            options.allowed_tools = mcp_tool_names
        return options

    async def _connect(self, model_name: str, system_prompt: str, mcp_servers: Optional[Dict]) -> ClaudeSDKClient:
        options = self._make_options(model_name, system_prompt, mcp_servers)
        client = ClaudeSDKClient(options=options)
        await asyncio.wait_for(client.connect(), timeout=60)
        return client

    async def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Optional[Dict] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Send a message and stream structured events back.

        Reuses the connected client across turns (resumes via session_id) so the
        CLI subprocess keeps conversation history — callers no longer pass
        conversation_history manually.

        Yields:
            dict events: {"type": "text"|"activity"|"error", "content": str}
        """
        consecutive_failures = 0
        max_failures = 3

        while True:
            resume_attempt = self._client is None and bool(self._session_id)
            try:
                if self._client is None:
                    self._client = await self._connect(model_name, system_prompt, mcp_servers)
                await self._client.query(user_message)
                async for event in self._stream_events():
                    yield event
                return
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"SDK turn failed (attempt {consecutive_failures}/{max_failures}): {e}", exc_info=True)
                await self._disconnect()
                if resume_attempt and _is_stale_resume_error(e):
                    logger.warning(
                        "Claude session %s could not be resumed; starting with transcript handoff",
                        self._session_id,
                    )
                    self._session_id = None
                    consecutive_failures = 0
                    continue
                rl = _rate_limit_info(e)
                if rl is not None:
                    # Rate / session limit — retrying won't help within the window.
                    # Surface it to the UI and stop (don't burn the retry budget).
                    content = str(rl.pop("content", ""))
                    yield AgentEvent("rate_limit", content, rl)
                    return
                if consecutive_failures >= max_failures:
                    yield AgentEvent("error", str(e))
                    yield AgentEvent("turn_end", "Turn failed", {"ok": False})
                    return
                await asyncio.sleep(2)

    async def _stream_events(self) -> AsyncGenerator[AgentEvent, None]:
        pending_images: list[AgentEvent] = []
        async for msg in self._client.receive_messages():
            if isinstance(msg, StreamEvent):
                ev = msg.event or {}
                if ev.get("type") != "content_block_delta":
                    continue
                delta = ev.get("delta") or {}
                if delta.get("type") != "text_delta":
                    continue
                text = delta.get("text") or ""
                if text:
                    yield AgentEvent("text_delta", text)
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock) and block.text:
                        yield AgentEvent("text", block.text)
                    elif isinstance(block, ToolUseBlock):
                        try:
                            inp = json.dumps(block.input, ensure_ascii=False)
                        except Exception:
                            inp = str(block.input)
                        yield AgentEvent(
                            "tool_use",
                            f"{block.name}: {inp}",
                            {
                                "tool_name": block.name,
                                "short_name": block.name.rsplit("__", 1)[-1],
                                "tool_use_id": str(getattr(block, "id", "") or ""),
                            },
                        )
                    elif isinstance(block, ToolResultBlock):
                        for event in _tool_result_events(block):
                            if event.type == "image":
                                pending_images.append(event)
                            else:
                                yield event
            elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        for event in _tool_result_events(block):
                            if event.type == "image":
                                pending_images.append(event)
                            else:
                                yield event
            elif isinstance(msg, ResultMessage):
                if msg.session_id:
                    self._session_id = msg.session_id
                usage = getattr(msg, "usage", None)
                if isinstance(usage, dict):
                    self._last_usage = usage
                client = self._client
                if client is not None:
                    try:
                        raw_context = await asyncio.wait_for(
                            client.get_context_usage(),
                            timeout=5,
                        )
                        if isinstance(raw_context, Mapping):
                            self._last_context_usage = _context_usage_from_sdk(
                                raw_context
                            )
                    except Exception as exc:
                        logger.debug("Claude context breakdown unavailable: %s", exc)
                if msg.is_error and msg.result:
                    yield AgentEvent("error", msg.result)
                # Claude often adds a final acknowledgement after an MCP tool
                # result. Publish cinematic frames only after that text so the
                # image remains the final visible story beat.
                for image in pending_images:
                    yield image
                pending_images.clear()
                yield AgentEvent(
                    "turn_end",
                    "Turn completed" if not msg.is_error else "Turn failed",
                    {"ok": not msg.is_error, "stop_reason": "end_turn"},
                )
                return

    async def _disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def get_context_usage(self) -> Optional[ContextUsage]:
        """Context footprint of the last turn, or None if no turn ran yet.

        Context = all input-side tokens (fresh input + cache read + cache create)
        of the latest ResultMessage, as a fraction of the model's window. Mirrors
        Orchestra's ctx% calc. Output tokens don't count — they aren't in context.
        """
        if self._last_context_usage is not None:
            return self._last_context_usage
        u = self._last_usage
        if not u:
            return None
        used = (
            (u.get("input_tokens") or 0)
            + (u.get("cache_read_input_tokens") or 0)
            + (u.get("cache_creation_input_tokens") or 0)
        )
        total = self.CONTEXT_WINDOW
        return ContextUsage(used_tokens=used, total_tokens=total)

    async def compact(self) -> bool:
        """Claude Agent SDK exposes auto-compaction but no manual control call.

        Returning False asks GameSession to use the provider-neutral
        WorldGraph + recent-transcript handoff compaction path.
        """
        return False

    async def interrupt(self) -> bool:
        client = self._client
        if client is None:
            return False
        interrupt = getattr(client, "interrupt", None)
        if interrupt is None:
            await self._disconnect()
            return True
        await interrupt()
        return True

    async def close(self) -> None:
        """Drop the CLI subprocess (e.g. on idle hibernate). Next process_message()
        call reconnects and resumes via the cached session_id — history survives."""
        await self._disconnect()

    async def reset(self) -> None:
        """Start a FRESH conversation: drop the subprocess AND forget the session_id
        so the next turn does not resume the old context. The on-disk event log is
        untouched — only Claude's working memory is cleared."""
        await self._disconnect()
        self._session_id = None
        self._last_usage = None
        self._last_context_usage = None

    async def reconnect(self, system_prompt: str, mcp_servers: Optional[Dict] = None) -> None:
        await self._disconnect()
        self._client = await self._connect(self.model_name, system_prompt, mcp_servers)

    def get_provider_name(self) -> str:
        return "Claude Agent SDK (subscription)"
