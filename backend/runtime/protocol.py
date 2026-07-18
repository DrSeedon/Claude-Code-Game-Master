"""Structural contract shared by campaign AI providers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol, runtime_checkable

from backend.runtime.events import AgentEvent, ContextUsage


@runtime_checkable
class AgentProvider(Protocol):
    """Provider used by one campaign session.

    Providers own their conversation identifier and must reject or serialize
    concurrent turns internally.
    """

    @property
    def session_id(self) -> str | None: ...

    def process_message(
        self,
        user_message: str,
        system_prompt: str,
        model_name: str,
        mcp_servers: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]: ...

    async def interrupt(self) -> bool: ...

    async def compact(self) -> bool: ...

    async def reset(self) -> None: ...

    async def close(self) -> None: ...

    def get_context_usage(self) -> ContextUsage | None: ...

    def get_provider_name(self) -> str: ...
