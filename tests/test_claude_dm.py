"""Tests for load_system_prompt — the DM system prompt must contain the DnD rules
for the campaign being played (regression: it used to return only a narrator style)."""

from backend.claude_dm import _cinematic_context, load_system_prompt


def test_prompt_contains_dnd_rules_for_campaign():
    """With a campaign, the prompt includes the compiled dm-slots (tools + combat),
    not just a narrator style. This is the bug: the DM got no rules → 'несёт бред'."""
    prompt = load_system_prompt("dragon-quest")
    assert len(prompt) > 10_000, f"prompt too short ({len(prompt)}) — rules likely missing"
    assert "dm-roll" in prompt          # the dice/attack tool the DM must call
    assert "combat" in prompt.lower()
    assert "Narrator Style" in prompt    # narrator layered on top


def test_prompt_has_canonical_startup_tool_contract():
    prompt = load_system_prompt("dragon-quest")

    assert "Run exactly one `bash tools/dm-session.sh context`" in prompt
    assert "`bash tools/dm-player.sh show`" in prompt
    assert "`bash tools/dm-campaign.sh info`" in prompt
    assert "Never guess tool actions" in prompt


def test_prompt_without_campaign_still_has_core_rules():
    """No campaign scoped → CORE dm-slots still emit (fallback), never an empty prompt."""
    prompt = load_system_prompt(None)
    assert "dm-roll" in prompt


def test_wizard_shaped_campaign_does_not_crash(tmp_path, monkeypatch):
    """Wizard/API campaigns use the canonical module map and a narrator id."""
    from backend.campaign_api import create_campaign
    monkeypatch.setattr("backend.campaign_api.get_project_root", lambda: tmp_path)
    (tmp_path / "world-state" / "campaigns").mkdir(parents=True)
    # Point claude_dm at the same tmp root by symlinking .claude (rules) is overkill;
    # instead just assert the API writes the shapes and the builder tolerates them.
    res = create_campaign(name="wiz-shape", narrator_style="epic-heroic", modules=["mass-combat"])
    assert res["success"]
    import json
    d = json.loads((tmp_path / "world-state" / "campaigns" / "wiz-shape" / "campaign-overview.json").read_text())
    assert isinstance(d["narrator_style"], str)   # string id, not object
    assert d["modules"] == {"mass-combat": True}


def test_prompt_has_current_campaign_context(tmp_path):
    """The prompt must tell the DM it is ALREADY inside this campaign (setting +
    'do not list campaigns'), so 'Начать игру' runs the session, not a menu.
    _campaign_context takes project_root directly, so point it at a tmp tree."""
    import json
    from backend.claude_dm import _campaign_context
    camp = tmp_path / "world-state" / "campaigns" / "ctx-camp"
    camp.mkdir(parents=True)
    (camp / "campaign-overview.json").write_text(
        json.dumps({"genre": "sci-fi", "tone": "gritty", "description": "Dead colony"}),
        encoding="utf-8")
    ctx = _campaign_context(tmp_path, "ctx-camp")
    assert "Current Campaign" in ctx
    assert "sci-fi" in ctx
    assert "do NOT list campaigns" in ctx


def test_cinematic_context_exposes_provider_neutral_tool_contract(tmp_path):
    import json

    skill = tmp_path / "codex-skills" / "cinematic-scene" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Cinematic Scene\n\nGenerate a widescreen image.", encoding="utf-8")
    campaign = tmp_path / "world-state" / "campaigns" / "space"
    campaign.mkdir(parents=True)
    (campaign / "campaign-overview.json").write_text(
        json.dumps(
            {
                "cinematic_visuals": {
                    "enabled": True,
                    "frequency": "occasional",
                    "aspect_ratio": "16:9",
                    "presentation": "game-loading-screen",
                }
            }
        ),
        encoding="utf-8",
    )

    context = _cinematic_context(tmp_path, "space")

    assert "Automatic major-beat images are enabled" in context
    assert "`mcp__cinematic__render_scene`" in context
    assert "native image generation" in context
    assert "# Cinematic Scene" in context


def test_claude_cinematic_tool_result_emits_clean_result_and_image(tmp_path):
    from claude_agent_sdk.types import ToolResultBlock

    from backend.cinematic_mcp import encode_cinematic_event
    from backend.providers.claude_sdk import _tool_result_events

    image = tmp_path / "frame.png"
    marker = encode_cinematic_event(
        {
            "type": "image",
            "source_path": str(image),
            "alt": "Hangar reveal",
        }
    )
    block = ToolResultBlock(
        tool_use_id="tool-9",
        content=marker + "\nCinematic image generated and published.",
        is_error=False,
    )

    events = _tool_result_events(block)

    assert [event.type for event in events] == ["tool_result", "image"]
    assert "__DM_CINEMATIC_EVENT__" not in events[0].content
    assert events[1].metadata["source_path"] == str(image)
    assert events[1].metadata["alt"] == "Hangar reveal"


def test_claude_stale_resume_retries_fresh_with_same_handoff_prompt(tmp_path):
    import asyncio

    from backend.providers.claude_sdk import ClaudeSDKProvider

    class FakeClient:
        async def query(self, _message):
            return None

        async def receive_messages(self):
            if False:
                yield None

        async def disconnect(self):
            return None

    provider = ClaudeSDKProvider(
        tmp_path,
        resume_session_id="session-stale",
    )
    attempts = []

    async def fake_connect(_model, system_prompt, _mcp):
        attempts.append((provider.session_id, system_prompt))
        if len(attempts) == 1:
            raise RuntimeError("session id not found")
        return FakeClient()

    provider._connect = fake_connect

    async def scenario():
        return [
            event
            async for event in provider.process_message(
                "continue",
                "SYSTEM\n<provider_handoff>recent scene</provider_handoff>",
                "claude-sonnet-5",
            )
        ]

    assert asyncio.run(scenario()) == []
    assert attempts == [
        (
            "session-stale",
            "SYSTEM\n<provider_handoff>recent scene</provider_handoff>",
        ),
        (
            None,
            "SYSTEM\n<provider_handoff>recent scene</provider_handoff>",
        ),
    ]


def test_claude_stream_publishes_cinematic_image_after_final_text(tmp_path):
    import asyncio

    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        UserMessage,
    )
    from claude_agent_sdk.types import ToolResultBlock

    from backend.cinematic_mcp import encode_cinematic_event
    from backend.providers.claude_sdk import ClaudeSDKProvider

    marker = encode_cinematic_event(
        {
            "type": "image",
            "source_path": str(tmp_path / "frame.png"),
        }
    )

    class FakeClient:
        async def receive_messages(self):
            yield UserMessage(
                content=[
                    ToolResultBlock(
                        tool_use_id="tool-1",
                        content=marker + "\nImage ready.",
                        is_error=False,
                    )
                ]
            )
            yield AssistantMessage(
                content=[TextBlock("Final acknowledgement.")],
                model="claude-sonnet-5",
            )
            yield ResultMessage(
                subtype="success",
                duration_ms=10,
                duration_api_ms=5,
                is_error=False,
                num_turns=1,
                session_id="session-1",
            )

        async def get_context_usage(self):
            return {}

    provider = ClaudeSDKProvider(tmp_path)
    provider._client = FakeClient()

    async def scenario():
        return [event async for event in provider._stream_events()]

    events = asyncio.run(scenario())

    assert [event.type for event in events] == [
        "tool_result",
        "text",
        "image",
        "turn_end",
    ]


def test_rate_limit_info_classifies():
    """Provider must recognise rate/session limits and extract retry_after."""
    from backend.providers.claude_sdk import _rate_limit_info
    assert _rate_limit_info(Exception("rate limit exceeded, retry-after 30")) == {
        "content": "rate limit exceeded, retry-after 30", "retry_after": 30}
    assert _rate_limit_info(Exception("session limit reached"))["content"]  # no retry_after
    assert _rate_limit_info(Exception("connection refused")) is None


def test_claude_context_usage_keeps_provider_breakdown():
    from backend.providers.claude_sdk import _context_usage_from_sdk

    usage = _context_usage_from_sdk(
        {
            "totalTokens": 118_000,
            "maxTokens": 200_000,
            "categories": [
                {"name": "System prompt", "tokens": 24_000, "color": "blue"},
                {"name": "Messages", "tokens": 94_000, "color": "green"},
            ],
        }
    )

    assert usage.used_tokens == 118_000
    assert usage.total_tokens == 200_000
    assert usage.percent == 59
    assert usage.breakdown == {
        "System prompt": 24_000,
        "Messages": 94_000,
    }


def test_campaign_name_validation_matches_creation():
    """Codex P2: the WS validator must accept every legally-created campaign name
    (spaces/dots/Unicode/long allowed by create_campaign) while blocking traversal."""
    from backend.server import _valid_campaign_name
    assert _valid_campaign_name("My Campaign")     # space — legal
    assert _valid_campaign_name("Приключение")      # Unicode — legal
    assert _valid_campaign_name("epic.saga")        # dot in middle — legal
    assert _valid_campaign_name("a" * 80)           # long — legal (no length cap in create)
    assert not _valid_campaign_name("../evil")      # traversal
    assert not _valid_campaign_name("a/b")          # separator
    assert not _valid_campaign_name(".hidden")      # leading dot
    assert not _valid_campaign_name("")             # empty
