"""Tests for load_system_prompt — the DM system prompt must contain the DnD rules
for the campaign being played (regression: it used to return only a narrator style)."""

from backend.claude_dm import load_system_prompt


def test_prompt_contains_dnd_rules_for_campaign():
    """With a campaign, the prompt includes the compiled dm-slots (tools + combat),
    not just a narrator style. This is the bug: the DM got no rules → 'несёт бред'."""
    prompt = load_system_prompt("dragon-quest")
    assert len(prompt) > 10_000, f"prompt too short ({len(prompt)}) — rules likely missing"
    assert "dm-roll" in prompt          # the dice/attack tool the DM must call
    assert "combat" in prompt.lower()
    assert "Narrator Style" in prompt    # narrator layered on top


def test_prompt_without_campaign_still_has_core_rules():
    """No campaign scoped → CORE dm-slots still emit (fallback), never an empty prompt."""
    prompt = load_system_prompt(None)
    assert "dm-roll" in prompt
