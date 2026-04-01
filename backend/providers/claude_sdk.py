"""Провайдер через Claude Code SDK (подписка, без API ключа)."""

import logging
from typing import AsyncGenerator, List, Dict, Any
from pathlib import Path

from backend.providers.base import BaseProvider

logger = logging.getLogger(__name__)

SDK_AVAILABLE = False
try:
    from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, ResultMessage, SystemMessage

    # Patch SDK to handle unknown message types (rate_limit_event, usage_event, etc.)
    # Without this, unknown types crash the response stream entirely.
    import claude_code_sdk._internal.message_parser as _parser
    import claude_code_sdk._internal.client as _client

    _original_parse = _parser.parse_message

    def _patched_parse(data):
        try:
            return _original_parse(data)
        except Exception as e:
            if "Unknown message type" in str(e):
                mt = data.get("type", "unknown") if isinstance(data, dict) else "unknown"
                logger.debug(f"SDK: skipping unknown message type '{mt}'")
                return SystemMessage(subtype=f"unknown_{mt}", data=data if isinstance(data, dict) else {})
            raise

    _parser.parse_message = _patched_parse
    _client.parse_message = _patched_parse

    SDK_AVAILABLE = True
except ImportError:
    pass


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

        try:
            async for msg in query(prompt=user_message, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            yield block.text
                elif isinstance(msg, ResultMessage):
                    if msg.is_error and msg.result:
                        yield f"\n\n[Ошибка: {msg.result}]"
        except Exception as e:
            logger.error(f"Claude SDK error: {e}", exc_info=True)
            yield f"\n\n[Ошибка SDK: {str(e)}]"

        conversation_history.append({"role": "user", "content": user_message})

    def get_provider_name(self) -> str:
        return "Claude Code SDK (подписка)"
