"""Anthropic API provider with session-based history persistence.

Stores history as Anthropic-native message list (with tool_use/tool_result
blocks intact) in storage/sessions/<session_key>_history.json so that tool
context survives restarts.
"""

import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Any, Optional

from anthropic import AsyncAnthropic

from backend.providers.base import BaseProvider
from backend.tools_registry import execute_tool

logger = logging.getLogger(__name__)

SESSION_DIR = Path(__file__).parent.parent.parent / "storage" / "sessions"
MAX_TOOL_ITERATIONS = 10


class AnthropicAPIProvider(BaseProvider):
    """Direct Anthropic API with in-memory + on-disk history."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = AsyncAnthropic(api_key=api_key)
        self._session_key: Optional[str] = None
        self._history_file: Optional[Path] = None
        self._history: List[Dict[str, Any]] = []
        self._interrupt_flag = False

    # ── lifecycle ───────────────────────────────────────────────────────

    async def load_session(self, session_key: str) -> None:
        self._session_key = session_key
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self._history_file = SESSION_DIR / f"{session_key}_history.json"
        if self._history_file.exists():
            try:
                self._history = json.loads(self._history_file.read_text())
                logger.info(
                    "Loaded API session %s (%d messages)",
                    session_key, len(self._history),
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Couldn't load history %s: %s", session_key, e)
                self._history = []
        else:
            self._history = []
            logger.info("New API session %s", session_key)

    def _save_history(self) -> None:
        if not self._history_file:
            return
        try:
            self._history_file.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2)
            )
        except OSError as e:
            logger.error("Couldn't save history: %s", e)

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
                "AnthropicAPIProvider.process_message called before load_session"
            )

        self._interrupt_flag = False
        self._history.append({"role": "user", "content": user_message})

        iteration = 0
        while iteration < MAX_TOOL_ITERATIONS:
            if self._interrupt_flag:
                logger.info("API interrupt — breaking tool loop")
                break
            iteration += 1

            try:
                async with self.client.messages.stream(
                    model=model_name,
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=self._history,
                    tools=tools,
                ) as stream:
                    async for text in stream.text_stream:
                        if self._interrupt_flag:
                            break
                        yield json.dumps(
                            {"type": "text", "content": text},
                            ensure_ascii=False,
                        )

                    final = await stream.get_final_message()
                    # Content blocks must be kept as-is (SDK objects) when
                    # feeding back into the next call. Convert via dicts.
                    self._history.append(
                        {
                            "role": "assistant",
                            "content": [b.model_dump() for b in final.content],
                        }
                    )

                    if final.stop_reason == "tool_use":
                        tool_results = []
                        for block in final.content:
                            if block.type != "tool_use":
                                continue
                            yield json.dumps(
                                {
                                    "type": "activity",
                                    "content": f"🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:200]})",
                                },
                                ensure_ascii=False,
                            )
                            try:
                                result = execute_tool(block.name, block.input)
                                if isinstance(result, dict) and "error" in result:
                                    content_str = result["error"]
                                    is_error = True
                                elif isinstance(result, dict):
                                    inner = result.get("result", "")
                                    content_str = (
                                        json.dumps(inner)
                                        if isinstance(inner, dict)
                                        else str(inner)
                                    )
                                    is_error = False
                                else:
                                    content_str = str(result)
                                    is_error = False
                                prefix = "❌" if is_error else "✅"
                                yield json.dumps(
                                    {
                                        "type": "activity",
                                        "content": f"{prefix} {content_str[:300]}",
                                    },
                                    ensure_ascii=False,
                                )
                                tool_results.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": content_str,
                                        **({"is_error": True} if is_error else {}),
                                    }
                                )
                            except Exception as e:
                                tool_results.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": f"Tool error: {e}",
                                        "is_error": True,
                                    }
                                )
                        self._history.append(
                            {"role": "user", "content": tool_results}
                        )
                        # loop continues — Claude will read results
                    else:
                        break
            except Exception as e:
                logger.error("API error: %s", e, exc_info=True)
                yield json.dumps(
                    {"type": "error", "content": str(e)},
                    ensure_ascii=False,
                )
                break

        if iteration >= MAX_TOOL_ITERATIONS:
            yield json.dumps(
                {
                    "type": "error",
                    "content": "Tool-calling loop limit reached",
                },
                ensure_ascii=False,
            )

        self._save_history()

    async def interrupt(self) -> None:
        self._interrupt_flag = True
        logger.info("API interrupt flag set")

    def get_provider_name(self) -> str:
        return "Anthropic API"
