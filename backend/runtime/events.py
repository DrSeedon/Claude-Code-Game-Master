"""Provider-neutral events and usage information."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentEvent:
    """One normalized event emitted by an AI provider."""

    type: str
    content: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "content": self.content,
        }
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


@dataclass(frozen=True)
class ContextUsage:
    """Current occupied context, when the provider exposes it."""

    used_tokens: int
    total_tokens: int
    cached_input_tokens: int = 0

    @property
    def percent(self) -> int:
        if self.total_tokens <= 0:
            return 0
        return min(100, round(self.used_tokens * 100 / self.total_tokens))

    def to_dict(self) -> dict[str, int]:
        return {
            "percent": self.percent,
            "used_tokens": self.used_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
        }
