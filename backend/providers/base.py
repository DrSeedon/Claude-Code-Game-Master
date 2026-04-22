"""Base interface for AI providers."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Any, Optional


class BaseProvider(ABC):
    """Abstract base class for all AI providers.

    Defines unified interface for working with different AI backends
    (Anthropic API, Claude SDK, etc.).
    """

    @abstractmethod
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]],
        mcp_servers: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """Process user message and return streaming response.

        Args:
            user_message: Message from player
            conversation_history: Conversation history (modified in-place)
            system_prompt: System prompt with DM rules
            model_name: Claude model name
            tools: List of tool schemas in Anthropic format

        Yields:
            Text chunks from Claude streaming response
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name for logging."""
        pass
