"""Provider via Claude Agent SDK (subscription, no API key required)."""

import asyncio
import json
import logging
import os
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
)
from claude_agent_sdk.types import ToolResultBlock

from backend.providers.base import BaseProvider

logger = logging.getLogger(__name__)


def _proxy_env() -> dict:
    env = {}
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
        if os.environ.get(key):
            env[key] = os.environ[key]
            env[key.lower()] = os.environ[key]
    return env


def _extract_tool_result(block: ToolResultBlock) -> str:
    raw = getattr(block, "content", "")
    if isinstance(raw, list):
        return "\n".join(item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in raw)
    if isinstance(raw, dict):
        return raw.get("text", str(raw))
    return str(raw)


class ClaudeSDKProvider(BaseProvider):

    # Claude context window (Sonnet/Opus). Used to turn token counts into a %.
    CONTEXT_WINDOW = 200_000

    def __init__(self, project_root: Path, model_name: str = "claude-sonnet-4-6"):
        self.project_root = project_root
        self.model_name = model_name
        self._client: Optional[ClaudeSDKClient] = None
        self._session_id: Optional[str] = None
        self._last_usage: Optional[dict] = None  # token counts from the latest ResultMessage

    def _make_options(self, model_name: str, system_prompt: str, mcp_servers: Optional[Dict]) -> ClaudeAgentOptions:
        options = ClaudeAgentOptions(
            model=model_name or self.model_name,
            cwd=str(self.project_root.resolve()),
            max_turns=100,
            permission_mode="bypassPermissions",
            max_buffer_size=50 * 1024 * 1024,
            include_partial_messages=True,
            env=_proxy_env(),
        )
        if self._session_id:
            options.resume = self._session_id
        else:
            options.system_prompt = system_prompt

        if mcp_servers:
            options.mcp_servers = mcp_servers
            mcp_tool_names = []
            for server_name in mcp_servers:
                mcp_tool_names.extend([
                    f"mcp__{server_name}__show_choices",
                    f"mcp__{server_name}__clear_choices",
                    f"mcp__{server_name}__create_campaign",
                ])
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
    ) -> AsyncGenerator[dict, None]:
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
                if consecutive_failures >= max_failures:
                    yield {"type": "error", "content": str(e)}
                    return
                await asyncio.sleep(2)

    async def _stream_events(self) -> AsyncGenerator[dict, None]:
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
                    yield {"type": "text_delta", "content": text}
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock) and block.text:
                        yield {"type": "text", "content": block.text}
                    elif isinstance(block, ToolUseBlock):
                        try:
                            inp = json.dumps(block.input, ensure_ascii=False)
                        except Exception:
                            inp = str(block.input)
                        yield {"type": "activity", "content": f"🔧 {block.name}({inp})"}
                    elif isinstance(block, ToolResultBlock):
                        prefix = "❌" if block.is_error else "✅"
                        yield {"type": "activity", "content": f"{prefix} {_extract_tool_result(block)}"}
            elif isinstance(msg, ResultMessage):
                if msg.session_id:
                    self._session_id = msg.session_id
                usage = getattr(msg, "usage", None)
                if isinstance(usage, dict):
                    self._last_usage = usage
                if msg.is_error and msg.result:
                    yield {"type": "error", "content": msg.result}
                return

    async def _disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def get_context_usage(self) -> Optional[dict]:
        """Context footprint of the last turn, or None if no turn ran yet.

        Context = all input-side tokens (fresh input + cache read + cache create)
        of the latest ResultMessage, as a fraction of the model's window. Mirrors
        Orchestra's ctx% calc. Output tokens don't count — they aren't in context.
        """
        u = self._last_usage
        if not u:
            return None
        used = (
            (u.get("input_tokens") or 0)
            + (u.get("cache_read_input_tokens") or 0)
            + (u.get("cache_creation_input_tokens") or 0)
        )
        total = self.CONTEXT_WINDOW
        percent = min(100, round(used * 100 / total)) if total else 0
        return {"percent": percent, "used_tokens": used, "total_tokens": total}

    async def close(self) -> None:
        """Drop the CLI subprocess (e.g. on idle hibernate). Next process_message()
        call reconnects and resumes via the cached session_id — history survives."""
        await self._disconnect()

    async def reconnect(self, system_prompt: str, mcp_servers: Optional[Dict] = None) -> None:
        await self._disconnect()
        self._client = await self._connect(self.model_name, system_prompt, mcp_servers)

    def get_provider_name(self) -> str:
        return "Claude Agent SDK (subscription)"
