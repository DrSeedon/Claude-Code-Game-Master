"""Runtime capabilities, model metadata, and provider construction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from backend.runtime.protocol import AgentProvider

EventStreamMode = Literal["persistent", "per_turn"]


@dataclass(frozen=True)
class RuntimeCapabilities:
    event_stream: EventStreamMode
    resume: bool
    interrupt: bool
    hibernate: bool
    context_usage: bool
    mcp: bool
    mid_turn_inject: bool = False

    def to_dict(self) -> dict[str, bool | str]:
        return {
            "event_stream": self.event_stream,
            "resume": self.resume,
            "interrupt": self.interrupt,
            "hibernate": self.hibernate,
            "context_usage": self.context_usage,
            "mcp": self.mcp,
            "mid_turn_inject": self.mid_turn_inject,
        }


@dataclass(frozen=True)
class ProviderBuildContext:
    project_root: Path
    campaign_name: str | None
    model_name: str
    resume_session_id: str | None = None
    reasoning_effort: str | None = None
    environment: Mapping[str, str] | None = None


ProviderFactory = Callable[[ProviderBuildContext], AgentProvider]


@dataclass(frozen=True)
class RuntimeDefinition:
    id: str
    display_name: str
    capabilities: RuntimeCapabilities
    factory: ProviderFactory


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    display_name: str
    runtime_id: str
    context_window: int | None = None
    reasoning_efforts: tuple[str, ...] = ()
    selected_reasoning_effort: str | None = None
    usage_limits: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "runtime": self.runtime_id,
            "context_window": self.context_window,
            "reasoning_efforts": list(self.reasoning_efforts),
            "selected_reasoning_effort": self.selected_reasoning_effort,
            "usage_limits": dict(self.usage_limits or {}),
        }


class RuntimeRegistry:
    """Explicit registry with no import-time global mutations."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RuntimeDefinition] = {}
        self._models: dict[str, ModelDefinition] = {}

    def register_runtime(self, definition: RuntimeDefinition, *, replace: bool = False) -> None:
        if not definition.id:
            raise ValueError("runtime id must not be empty")
        if definition.id in self._runtimes and not replace:
            raise ValueError(f"runtime '{definition.id}' is already registered")
        self._runtimes[definition.id] = definition

    def register_model(self, definition: ModelDefinition, *, replace: bool = False) -> None:
        if definition.runtime_id not in self._runtimes:
            raise ValueError(f"unknown runtime '{definition.runtime_id}'")
        if definition.id in self._models and not replace:
            raise ValueError(f"model '{definition.id}' is already registered")
        self._models[definition.id] = definition

    def get_runtime(self, runtime_id: str) -> RuntimeDefinition:
        try:
            return self._runtimes[runtime_id]
        except KeyError as exc:
            raise ValueError(f"unknown runtime '{runtime_id}'") from exc

    def get_model(self, model_id: str) -> ModelDefinition:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise ValueError(f"unknown model '{model_id}'") from exc

    def list_models(self, runtime_id: str | None = None) -> list[ModelDefinition]:
        models = self._models.values()
        if runtime_id is not None:
            self.get_runtime(runtime_id)
            models = (model for model in models if model.runtime_id == runtime_id)
        return sorted(models, key=lambda model: model.id)

    def build(self, context: ProviderBuildContext) -> AgentProvider:
        model = self.get_model(context.model_name)
        runtime = self.get_runtime(model.runtime_id)
        effort = context.reasoning_effort or model.selected_reasoning_effort or "high"
        provider = runtime.factory(replace(context, reasoning_effort=effort))
        if not isinstance(provider, AgentProvider):
            raise TypeError(f"runtime '{runtime.id}' returned an incompatible provider")
        return provider


CODEX_REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")
CODEX_MODEL_DEFAULTS = {
    "gpt-5.3-codex-spark": {
        "effort": "native",
        "usage_limits": {"scope": "spark_separate", "plan": "pro"},
    },
    "gpt-5.6-sol": {
        "effort": "high",
        "usage_limits": {
            "scope": "codex_shared",
            "window_hours": 5,
            "pro_5x": [75, 450],
            "pro_20x": [300, 1800],
        },
    },
    "gpt-5.6-terra": {
        "effort": "medium",
        "usage_limits": {
            "scope": "codex_shared",
            "window_hours": 5,
            "pro_5x": [100, 550],
            "pro_20x": [400, 2200],
        },
    },
    "gpt-5.6-luna": {
        "effort": "low",
        "usage_limits": {
            "scope": "codex_shared",
            "window_hours": 5,
            "pro_5x": [250, 1400],
            "pro_20x": [1000, 5600],
        },
    },
}


def create_default_registry() -> RuntimeRegistry:
    """Create the built-in registry without requiring Codex at import time."""

    from backend.providers.claude_sdk import ClaudeSDKProvider
    from backend.providers.codex_cli import CODEX_CONTEXT_LIMITS, CodexCLIProvider

    registry = RuntimeRegistry()
    registry.register_runtime(
        RuntimeDefinition(
            id="claude",
            display_name="Claude Agent SDK",
            capabilities=RuntimeCapabilities(
                event_stream="persistent",
                resume=True,
                interrupt=True,
                hibernate=True,
                context_usage=True,
                mcp=True,
            ),
            factory=lambda context: ClaudeSDKProvider(
                project_root=context.project_root,
                model_name=context.model_name,
                campaign_name=context.campaign_name,
                resume_session_id=context.resume_session_id,
                environment=dict(context.environment or {}),
            ),
        )
    )
    for model_id, label in (
        ("claude-sonnet-5", "Claude Sonnet 5"),
        ("claude-opus-4-8", "Claude Opus 4.8"),
    ):
        registry.register_model(
            ModelDefinition(
                id=model_id,
                display_name=label,
                runtime_id="claude",
                context_window=ClaudeSDKProvider.CONTEXT_WINDOW,
                selected_reasoning_effort="provider_default",
                usage_limits={"scope": "provider_subscription"},
            )
        )
    registry.register_runtime(
        RuntimeDefinition(
            id="codex",
            display_name="Codex app-server",
            capabilities=RuntimeCapabilities(
                event_stream="persistent",
                resume=True,
                interrupt=True,
                hibernate=True,
                context_usage=True,
                mcp=True,
            ),
            factory=lambda context: CodexCLIProvider(
                project_root=context.project_root,
                model_name=context.model_name,
                campaign_name=context.campaign_name,
                resume_thread_id=context.resume_session_id,
                reasoning_effort=context.reasoning_effort,
                environment=context.environment,
            ),
        )
    )
    for model_id, label in (
        ("gpt-5.3-codex-spark", "GPT-5.3 Codex Spark"),
        ("gpt-5.6-sol", "GPT-5.6 Sol"),
        ("gpt-5.6-terra", "GPT-5.6 Terra"),
        ("gpt-5.6-luna", "GPT-5.6 Luna"),
    ):
        defaults = CODEX_MODEL_DEFAULTS[model_id]
        registry.register_model(
            ModelDefinition(
                id=model_id,
                display_name=label,
                runtime_id="codex",
                context_window=CODEX_CONTEXT_LIMITS.get(model_id),
                reasoning_efforts=(
                    () if model_id == "gpt-5.3-codex-spark"
                    else CODEX_REASONING_EFFORTS
                ),
                selected_reasoning_effort=defaults["effort"],
                usage_limits=defaults["usage_limits"],
            )
        )
    return registry
