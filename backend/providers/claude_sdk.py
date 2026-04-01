"""Провайдер через Claude Code SDK (подписка, без API ключа)."""

import asyncio
import json
import logging
import threading
from typing import AsyncGenerator, List, Dict, Any
from pathlib import Path

from backend.providers.base import BaseProvider

logger = logging.getLogger(__name__)

SDK_AVAILABLE = False
try:
    from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, ToolUseBlock, ToolResultBlock, ResultMessage, SystemMessage

    # Patch SDK to handle unknown message types (rate_limit_event etc.)
    import claude_code_sdk._internal.message_parser as _parser
    import claude_code_sdk._internal.client as _client

    _original_parse = _parser.parse_message

    def _patched_parse(data):
        try:
            return _original_parse(data)
        except Exception as e:
            if "Unknown message type" in str(e):
                mt = data.get("type", "unknown") if isinstance(data, dict) else "unknown"
                return SystemMessage(subtype=f"unknown_{mt}", data=data if isinstance(data, dict) else {})
            raise

    _parser.parse_message = _patched_parse
    _client.parse_message = _patched_parse

    SDK_AVAILABLE = True
except ImportError:
    pass


SENTINEL = object()


def _run_sdk_query(prompt: str, options, queue: "asyncio.Queue", loop):
    """Run SDK query in a separate thread, push chunks to queue."""

    async def _inner():
        try:
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            loop.call_soon_threadsafe(queue.put_nowait, {"type": "text", "content": block.text})
                        elif isinstance(block, ToolUseBlock):
                            loop.call_soon_threadsafe(queue.put_nowait, {
                                "type": "tool_call",
                                "name": block.name,
                                "input": block.input
                            })
                        elif isinstance(block, ToolResultBlock):
                            content = block.content if isinstance(block.content, str) else str(block.content)
                            loop.call_soon_threadsafe(queue.put_nowait, {
                                "type": "tool_result",
                                "content": content[:500],
                                "is_error": block.is_error
                            })
                elif isinstance(msg, ResultMessage):
                    if msg.is_error and msg.result:
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "content": msg.result})
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "content": str(e)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    asyncio.run(_inner())


class ClaudeSDKProvider(BaseProvider):

    def __init__(self, project_root: Path, model_name: str = "claude-sonnet-4-6"):
        if not SDK_AVAILABLE:
            raise ImportError("claude-code-sdk не установлен: pip install claude-code-sdk")
        self.project_root = project_root
        self.model_name = model_name

    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        options = ClaudeCodeOptions(
            model=model_name or self.model_name,
            system_prompt=system_prompt,
            cwd=str(self.project_root.resolve()),
            max_turns=10,
            permission_mode="bypassPermissions",
        )

        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        # Run SDK in separate thread to avoid anyio/uvicorn conflict
        thread = threading.Thread(target=_run_sdk_query, args=(user_message, options, queue, loop), daemon=True)
        thread.start()

        try:
            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                if item["type"] == "text":
                    yield item["content"]
                elif item["type"] == "tool_call":
                    yield f"\n🔧 `{item['name']}({json.dumps(item['input'], ensure_ascii=False)[:200]})`\n"
                elif item["type"] == "tool_result":
                    prefix = "❌" if item.get("is_error") else "✅"
                    yield f"\n{prefix} {item['content'][:300]}\n"
                elif item["type"] == "error":
                    yield f"\n\n[Ошибка: {item['content']}]"
        except Exception as e:
            logger.error(f"SDK streaming error: {e}", exc_info=True)
            yield f"\n\n[Ошибка: {str(e)}]"

        thread.join(timeout=5)
        conversation_history.append({"role": "user", "content": user_message})

    def get_provider_name(self) -> str:
        return "Claude Code SDK (подписка)"
