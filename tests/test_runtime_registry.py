import pytest

from backend.runtime import (
    AgentEvent,
    ContextUsage,
    ModelDefinition,
    ProviderBuildContext,
    RuntimeCapabilities,
    RuntimeDefinition,
    RuntimeRegistry,
    create_default_registry,
)


class FakeProvider:
    session_id = None

    async def process_message(self, user_message, system_prompt, model_name, mcp_servers=None):
        yield AgentEvent("text", user_message)

    async def interrupt(self):
        return False

    async def reset(self):
        return None

    async def close(self):
        return None

    def get_context_usage(self):
        return None

    def get_provider_name(self):
        return "fake"


def _runtime(factory=lambda context: FakeProvider()):
    return RuntimeDefinition(
        id="fake",
        display_name="Fake",
        capabilities=RuntimeCapabilities(
            event_stream="per_turn",
            resume=True,
            interrupt=True,
            hibernate=True,
            context_usage=False,
            mcp=False,
        ),
        factory=factory,
    )


def test_registry_builds_provider_for_registered_model(tmp_path):
    registry = RuntimeRegistry()
    registry.register_runtime(_runtime())
    registry.register_model(ModelDefinition("fake-1", "Fake 1", "fake", 1000))

    provider = registry.build(
        ProviderBuildContext(tmp_path, "campaign", "fake-1")
    )

    assert provider.get_provider_name() == "fake"
    assert registry.get_model("fake-1").context_window == 1000


def test_registry_applies_model_effort_unless_caller_overrides_it(tmp_path):
    captured = []
    registry = RuntimeRegistry()
    registry.register_runtime(_runtime(factory=lambda context: captured.append(context) or FakeProvider()))
    registry.register_model(
        ModelDefinition(
            "fake-1",
            "Fake 1",
            "fake",
            selected_reasoning_effort="medium",
        )
    )

    registry.build(ProviderBuildContext(tmp_path, "campaign", "fake-1"))
    registry.build(
        ProviderBuildContext(
            tmp_path,
            "campaign",
            "fake-1",
            reasoning_effort="high",
        )
    )

    assert [context.reasoning_effort for context in captured] == ["medium", "high"]


def test_registry_rejects_duplicate_and_unknown_entries():
    registry = RuntimeRegistry()
    registry.register_runtime(_runtime())
    with pytest.raises(ValueError, match="already registered"):
        registry.register_runtime(_runtime())
    with pytest.raises(ValueError, match="unknown runtime"):
        registry.register_model(ModelDefinition("missing", "Missing", "other"))
    with pytest.raises(ValueError, match="unknown model"):
        registry.get_model("missing")


def test_registry_rejects_incompatible_factory(tmp_path):
    registry = RuntimeRegistry()
    registry.register_runtime(_runtime(factory=lambda context: object()))
    registry.register_model(ModelDefinition("fake-1", "Fake 1", "fake"))

    with pytest.raises(TypeError, match="incompatible provider"):
        registry.build(ProviderBuildContext(tmp_path, None, "fake-1"))


def test_event_and_context_usage_serialize():
    event = AgentEvent("tool_use", "Bash: pwd", {"tool_name": "Bash"})
    usage = ContextUsage(50, 200, 40)

    assert event.to_dict() == {
        "type": "tool_use",
        "content": "Bash: pwd",
        "metadata": {"tool_name": "Bash"},
    }
    assert usage.to_dict() == {
        "percent": 25,
        "used_tokens": 50,
        "total_tokens": 200,
        "cached_input_tokens": 40,
    }


def test_default_registry_exposes_supported_model_catalog():
    registry = create_default_registry()

    codex_runtime = registry.get_runtime("codex")
    assert codex_runtime.display_name == "Codex app-server"
    assert codex_runtime.capabilities.event_stream == "persistent"
    assert codex_runtime.capabilities.interrupt is True
    assert [model.id for model in registry.list_models("claude")] == [
        "claude-opus-4-8",
        "claude-sonnet-5",
    ]
    assert [model.id for model in registry.list_models("codex")] == [
        "gpt-5.3-codex-spark",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    ]
    spark = registry.get_model("gpt-5.3-codex-spark")
    assert spark.context_window == 128_000
    assert spark.reasoning_efforts == ()
    assert spark.selected_reasoning_effort == "native"
    assert spark.usage_limits == {
        "scope": "spark_separate",
        "plan": "pro",
    }

    expected_codex = {
        "gpt-5.6-sol": ("high", [75, 450], [300, 1800]),
        "gpt-5.6-terra": ("medium", [100, 550], [400, 2200]),
        "gpt-5.6-luna": ("low", [250, 1400], [1000, 5600]),
    }
    for model_id, (effort, pro_5x, pro_20x) in expected_codex.items():
        model = registry.get_model(model_id)
        assert model.selected_reasoning_effort == effort
        assert model.usage_limits == {
            "scope": "codex_shared",
            "window_hours": 5,
            "pro_5x": pro_5x,
            "pro_20x": pro_20x,
        }

    claude = registry.get_model("claude-sonnet-5")
    assert claude.selected_reasoning_effort == "provider_default"
    assert claude.usage_limits == {"scope": "provider_subscription"}
