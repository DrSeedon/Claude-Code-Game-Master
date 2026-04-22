"""Claude Agent SDK provider via persistent ClaudeSDKClient (subscription auth).

The SDK spawns the `claude` CLI as a subprocess and inherits its credentials
(OAuth token from `claude auth login`, or ANTHROPIC_API_KEY env var). No API
key handling here — that's what the CLI is for.

Sessions persist as `~/.claude/projects/<sanitized-cwd>/<uuid>.jsonl` managed
by the CLI. We only track the UUID in storage/sessions/<session_key> and pass
it as options.resume on reconnect.
"""

import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Any, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

from backend.providers.base import BaseProvider

logger = logging.getLogger(__name__)


SESSION_DIR = Path(__file__).parent.parent.parent / "storage" / "sessions"


class ClaudeSDKProvider(BaseProvider):
    """Persistent ClaudeSDKClient with per-session resume.

    One instance binds to one session_key. Call load_session before first
    process_message; the client reconnects transparently.

    Ephemeral mode (ephemeral=True) skips disk persistence — useful for
    single-shot wizard flows where no resume is needed.
    """

    def __init__(
        self,
        project_root: Path,
        model_name: str = "claude-sonnet-4-6",
        ephemeral: bool = False,
    ):
        self.project_root = project_root
        self.model_name = model_name
        self.ephemeral = ephemeral

        self._session_key: Optional[str] = None
        self._session_id: Optional[str] = None
        self._session_file: Optional[Path] = None
        self._client: Optional["ClaudeSDKClient"] = None
        self._connected = False
        self._system_prompt: str = ""
        self._mcp_servers: Optional[Dict] = None
        self._expected_results = 0

    # ── lifecycle ───────────────────────────────────────────────────────

    async def load_session(self, session_key: str) -> None:
        self._session_key = session_key
        if not self.ephemeral:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            self._session_file = SESSION_DIR / session_key
            if self._session_file.exists():
                sid = self._session_file.read_text().strip()
                if sid:
                    self._session_id = sid
                    logger.info(
                        "Resuming SDK session %s (key=%s)",
                        sid[:8], session_key,
                    )
        if not self._session_id:
            logger.info("New SDK session (key=%s)", session_key)

    def _save_session_id(self) -> None:
        if self.ephemeral or not self._session_file or not self._session_id:
            return
        self._session_file.write_text(self._session_id)

    def _build_options(
        self,
        system_prompt: str,
        model_name: str,
        mcp_servers: Optional[Dict],
    ) -> "ClaudeAgentOptions":
        opts = ClaudeAgentOptions(
            model=model_name or self.model_name,
            cwd=str(self.project_root.resolve()),
            max_turns=25,
            permission_mode="bypassPermissions",
            include_partial_messages=False,
        )
        if system_prompt:
            opts.system_prompt = system_prompt
        if mcp_servers:
            opts.mcp_servers = mcp_servers
        if self._session_id:
            opts.resume = self._session_id
        return opts

    async def _ensure_connected(
        self,
        system_prompt: str,
        model_name: str,
        mcp_servers: Optional[Dict],
    ) -> None:
        # Rebuild client if system_prompt/mcp config changed materially,
        # otherwise just reuse the live subprocess.
        config_changed = (
            self._system_prompt != system_prompt
            or self._mcp_servers != mcp_servers
        )
        if self._client and self._connected and not config_changed:
            return

        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False

        self._system_prompt = system_prompt
        self._mcp_servers = mcp_servers
        opts = self._build_options(system_prompt, model_name, mcp_servers)
        self._client = ClaudeSDKClient(options=opts)
        await self._client.connect()
        self._connected = True

    # ── main API ────────────────────────────────────────────────────────

    async def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]],
        mcp_servers: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        if self._session_key is None:
            raise RuntimeError(
                "ClaudeSDKProvider.process_message called before load_session"
            )

        try:
            await self._ensure_connected(system_prompt, model_name, mcp_servers)
            assert self._client is not None  # _ensure_connected guarantees this
            await self._client.query(user_message)
            self._expected_results = 1

            async for msg in self._client.receive_messages():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            yield json.dumps(
                                {"type": "text", "content": block.text},
                                ensure_ascii=False,
                            )
                        elif isinstance(block, ToolUseBlock):
                            yield json.dumps(
                                {
                                    "type": "activity",
                                    "content": f"🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:200]})",
                                },
                                ensure_ascii=False,
                            )
                        elif isinstance(block, ToolResultBlock):
                            content = (
                                block.content
                                if isinstance(block.content, str)
                                else str(block.content)
                            )
                            prefix = "❌" if block.is_error else "✅"
                            yield json.dumps(
                                {
                                    "type": "activity",
                                    "content": f"{prefix} {content[:300]}",
                                },
                                ensure_ascii=False,
                            )
                elif isinstance(msg, ResultMessage):
                    sid = getattr(msg, "session_id", None)
                    if sid and sid != self._session_id:
                        self._session_id = sid
                        self._save_session_id()
                        logger.info("SDK session id saved: %s", sid[:8])
                    if msg.is_error and msg.result:
                        yield json.dumps(
                            {"type": "error", "content": str(msg.result)},
                            ensure_ascii=False,
                        )
                    self._expected_results -= 1
                    if self._expected_results <= 0:
                        break
                elif isinstance(msg, SystemMessage):
                    logger.debug("SDK system: %s", getattr(msg, "subtype", "?"))

        except Exception as e:
            logger.error("SDK error: %s", e, exc_info=True)
            self._connected = False
            self._client = None
            yield json.dumps(
                {"type": "error", "content": str(e)},
                ensure_ascii=False,
            )

    async def interrupt(self) -> None:
        if self._client and self._connected:
            try:
                await self._client.interrupt()
                logger.info("SDK interrupt sent")
            except Exception as e:
                logger.error("interrupt error: %s", e)

    async def get_context_usage(self) -> Optional[Dict[str, Any]]:
        if self._client and self._connected:
            try:
                return await self._client.get_context_usage()
            except Exception as e:
                logger.debug("get_context_usage error: %s", e)
        return None

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False

    def get_provider_name(self) -> str:
        mode = "ephemeral" if self.ephemeral else "persistent"
        return f"Claude Agent SDK ({mode})"
