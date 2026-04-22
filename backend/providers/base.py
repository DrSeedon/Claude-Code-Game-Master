"""Base interface for AI providers with session-based state management."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Any, Optional


class BaseProvider(ABC):
    """Abstract base for AI providers.

    Providers own conversation state. Caller identifies a conversation by
    session_key (typically campaign name, or a random UUID for ephemeral
    wizard-style flows). Provider loads/persists history itself — no
    conversation_history argument is passed on every call.

    Lifecycle:
        provider = SomeProvider(...)
        await provider.load_session(session_key)
        async for event in provider.process_message(user_msg, ...):
            ...
        # optional: await provider.interrupt()
    """

    @abstractmethod
    async def load_session(self, session_key: str) -> None:
        """Bind provider to a session. Loads prior history if it exists.

        Args:
            session_key: Logical conversation id (e.g. campaign name, or
                "wizard-<uuid>" for ephemeral flows).
        """
        ...

    @abstractmethod
    def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        tools: List[Dict[str, Any]],
        mcp_servers: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Send one user message, stream structured events back.

        Events are JSON-encoded strings with a "type" field:
            - {"type": "text", "content": "..."}          partial assistant text
            - {"type": "activity", "content": "..."}      tool call / result for UI
            - {"type": "error", "content": "..."}         recoverable error

        Args:
            user_message: Player input for this turn.
            system_prompt: System prompt for this session.
            model_name: Claude model id.
            tools: Tool schemas (Anthropic format). May be ignored by providers
                that prefer MCP-style tool wiring.
            mcp_servers: MCP server configs keyed by name.

        Yields:
            JSON-encoded event strings.
        """
        ...

    @abstractmethod
    async def interrupt(self) -> None:
        """Interrupt the current generation, if any. No-op if idle."""
        ...

    async def get_context_usage(self) -> Optional[Dict[str, Any]]:
        """Return context window usage info or None if not supported.

        Default: not supported.
        """
        return None

    @abstractmethod
    def get_provider_name(self) -> str:
        """Human-readable provider label for logs/UI."""
        ...
