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
