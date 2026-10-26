"""The online screen master: a full Claude Code session in the repository (owner decision 2026-10-26).

Bash, file edits and the project's .claude/settings.json hooks (the PostToolUse hook feeds the screen's live feed),
bypassPermissions; its limits live in the contract prompt. The DM prompt is ~110 KB and one argv string is capped at
128 KiB, so it goes to the CLI as --append-system-prompt-file on top of Claude Code's own prompt, on every connect.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections import deque
from pathlib import Path
from typing import Callable, Dict, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, SystemMessage

from backend.providers.claude_sdk import (ClaudeSDKProvider, _installed_cli_path, _is_stale_resume_error, _proxy_env,
                                          _rate_limit_info)
from backend.runtime.events import AgentEvent

logger = logging.getLogger(__name__)

# Any of these would move the master off the subscription (API billing, another endpoint or cloud).
API_ROUTE_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")
MAX_TURNS = 60
STALE_RESUME = "no conversation found"   # CLI 2.1.3xx: "No conversation found with session ID: <id>"


class _ObservedClient:
    """The SDK client, with the system messages (init: tools, MCP servers, key source) shown to the provider."""

    def __init__(self, client, on_system: Callable[[SystemMessage], None]):
        self._client = client
        self._on_system = on_system

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def receive_messages(self):
        async for message in self._client.receive_messages():
            if isinstance(message, SystemMessage):
                try:
                    self._on_system(message)
                except Exception:
                    logger.debug("system message observer failed", exc_info=True)
            yield message


class ScreenGMProvider(ClaudeSDKProvider):

    def __init__(
        self,
        project_root: Path,
        model_name: str,
        campaign_name: str,
        *,
        prompt_file: Path,
        screen_dir: Path,
        effort: str | None = None,
        resume_session_id: str | None = None,
        environment: dict[str, str] | None = None,
        client_factory=ClaudeSDKClient,
    ):
        super().__init__(project_root, model_name=model_name, campaign_name=campaign_name,
                         resume_session_id=resume_session_id, environment=environment, context_window=1_000_000)
        self.prompt_file = Path(prompt_file)
        self.screen_dir = Path(screen_dir)
        self.effort = effort or None
        self._client_factory = client_factory
        self.stderr_tail: deque[str] = deque(maxlen=20)
        self.init_info: dict | None = None

    def _make_options(self, model_name: str, system_prompt: str, mcp_servers: Optional[Dict]) -> ClaudeAgentOptions:
        # `system_prompt` (the base class's inline prompt) and `mcp_servers` are ignored: the prompt is the file.
        env = {k: v for k, v in {**_proxy_env(), **self._environment}.items() if k not in API_ROUTE_ENV}
        env.update({
            "NO_COLOR": "1", "TERM": "dumb",
            "DM_ACTIVE_CAMPAIGN": self.campaign_name, "DM_SCREEN_DIR": str(self.screen_dir),
            # The driver owns the screen server: turn/act must never start one or open a browser.
            "DM_SCREEN_AUTOSTART": "0",
            # The account's claude.ai connectors (Drive, Gmail...) would join the session otherwise.
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
            "DISABLE_AUTOUPDATER": "1",
        })
        options = ClaudeAgentOptions(
            model=model_name or self.model_name,
            cwd=str(self.project_root.resolve()),
            max_turns=MAX_TURNS,
            permission_mode="bypassPermissions",
            max_buffer_size=50 * 1024 * 1024,
            include_partial_messages=True,
            env=env,
            # The preset without "append" adds no flag (None would send an empty --system-prompt, a str the whole
            # prompt as one argv string): Claude Code keeps its own prompt and the file is appended to it.
            system_prompt={"type": "preset", "preset": "claude_code"},
            # Project settings only: their hooks feed the screen; the user's settings, plugins and MCP stay out.
            setting_sources=["project"],
            extra_args={"strict-mcp-config": None, "append-system-prompt-file": str(self.prompt_file.resolve())},
        )
        if self.effort:
            options.effort = self.effort
        if cli_path := _installed_cli_path():
            options.cli_path = cli_path
        if self._session_id:
            options.resume = self._session_id
        options.stderr = self._stderr_line
        return options

    def _stderr_line(self, line: str) -> None:
        line = line.rstrip()
        if line:
            self.stderr_tail.append(line)
            logger.info("claude stderr: %s", line[:400])

    def _on_system(self, message: SystemMessage) -> None:
        if message.subtype != "init" or self.init_info is not None:
            return
        data = message.data or {}
        self.init_info = data
        servers = [f"{s.get('name')}:{s.get('status')}" for s in data.get("mcp_servers") or [] if isinstance(s, dict)]
        logger.info("master session %s: model %s, cli %s, key source %s, permission %s, %d tools [%s], mcp servers [%s]",
                    data.get("session_id"), data.get("model"), data.get("claude_code_version"), data.get("apiKeySource"),
                    data.get("permissionMode"), len(data.get("tools") or []), ", ".join(data.get("tools") or []), ", ".join(servers))

    async def _connect(self, model_name: str, system_prompt: str, mcp_servers: Optional[Dict]):
        if removed := scrub_api_route_env():   # the CLI inherits os.environ; options.env cannot remove keys
            logger.warning("removed %s from the environment before starting the CLI", ", ".join(removed))
        options = self._make_options(model_name, system_prompt, mcp_servers)
        self.init_info = None
        self.stderr_tail.clear()
        client = self._client_factory(options=options)
        try:
            await asyncio.wait_for(client.connect(), timeout=60)
        except Exception as exc:
            with contextlib.suppress(Exception):   # a CLI that hung in the handshake must not stay behind
                await asyncio.wait_for(client.disconnect(), 10)
            text = f"{exc} {' '.join(self.stderr_tail)}".lower()
            if options.resume and STALE_RESUME in text:
                # The base class starts fresh on a stale resume, but only knows the older "not found" wording.
                raise RuntimeError(f"resume session id not found: {options.resume}") from exc
            raise
        return _ObservedClient(client, self._on_system)

    async def process_message(self, user_message, system_prompt, model_name, mcp_servers=None):
        """The base turn loop (a stale resume starts fresh, a limit becomes a rate_limit event, up to 3 attempts),
        except that a message is never sent twice once the master started working: its tools may already have
        changed the world, so a CLI lost mid-turn ends the turn with an error and the driver's follow-up resumes."""
        self._last_usage = None
        self._last_context_usage = None
        failures = 0
        while True:
            resume_attempt = self._client is None and bool(self._session_id)
            streamed = False
            try:
                if self._client is None:
                    self._client = await self._connect(model_name, system_prompt, mcp_servers)
                await self._client.query(user_message)
                async for event in self._stream_events():
                    streamed = True
                    yield event
                return
            except Exception as exc:
                failures += 1
                logger.error("master turn failed (attempt %d/3%s): %s", failures, ", mid-turn" if streamed else "", exc, exc_info=True)
                await self._disconnect()
                if resume_attempt and not streamed and _is_stale_resume_error(exc):
                    logger.warning("master session %s could not be resumed; starting fresh", self._session_id)
                    self._session_id, failures = None, 0
                    continue
                if (limit := _rate_limit_info(exc)) is not None:
                    yield AgentEvent("rate_limit", str(limit.pop("content", "")), limit)
                    return
                if streamed or failures >= 3:
                    yield AgentEvent("error", f"{exc}" + (" (the CLI stopped mid-turn; the message was not sent again)" if streamed else ""))
                    yield AgentEvent("turn_end", "Turn failed", {"ok": False})
                    return
                await asyncio.sleep(2)

    def get_provider_name(self) -> str:
        return "Claude Code (online screen master)"


def scrub_api_route_env(environ=os.environ) -> list[str]:
    """Drop the API-route variables from this process (the SDK child inherits os.environ); returns what was removed."""
    removed = [key for key in API_ROUTE_ENV if key in environ]
    for key in removed:
        environ.pop(key, None)
    return removed
