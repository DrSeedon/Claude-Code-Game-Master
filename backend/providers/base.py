"""Base interface for the AI provider."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Optional


class BaseProvider(ABC):
    """Abstract base for the Claude SDK provider.

    The provider owns a persistent SDK client (resumed across turns via
    session_id) — callers no longer pass conversation_history manually.
    """

    @abstractmethod
    def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Optional[Dict] = None,
    ) -> AsyncGenerator[dict, None]:
        """Send a message and stream structured events back.

        Args:
            user_message: Message from player
            system_prompt: System prompt with DM rules (used only on first connect)
            model_name: Claude model name
            mcp_servers: Optional MCP server config (e.g. wizard tools)

        Yields:
            dict events: {"type": "text"|"text_delta"|"activity"|"error", "content": str}
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name for logging."""
        ...
