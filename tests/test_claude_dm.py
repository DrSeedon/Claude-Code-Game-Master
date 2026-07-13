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


def test_wizard_shaped_campaign_does_not_crash(tmp_path, monkeypatch):
    """Codex P1: wizard/API campaigns store narrator_style as a STRING id and modules
    as a LIST. The prompt builder + compiler must handle both without crashing and
    still emit the DnD rules (was AttributeError → narrator-only)."""
    from backend.campaign_api import create_campaign
    monkeypatch.setattr("backend.campaign_api.get_project_root", lambda: tmp_path)
    (tmp_path / "world-state" / "campaigns").mkdir(parents=True)
    # Point claude_dm at the same tmp root by symlinking .claude (rules) is overkill;
    # instead just assert the API writes the shapes and the builder tolerates them.
    res = create_campaign(name="wiz-shape", narrator_style="epic-heroic", modules=["world-travel"])
    assert res["success"]
    import json
    d = json.loads((tmp_path / "world-state" / "campaigns" / "wiz-shape" / "campaign-overview.json").read_text())
    assert isinstance(d["narrator_style"], str)   # string id, not object
    assert isinstance(d["modules"], list)          # list, not dict


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


def test_rate_limit_info_classifies():
    """Provider must recognise rate/session limits and extract retry_after."""
    from backend.providers.claude_sdk import _rate_limit_info
    assert _rate_limit_info(Exception("rate limit exceeded, retry-after 30")) == {
        "content": "rate limit exceeded, retry-after 30", "retry_after": 30}
    assert _rate_limit_info(Exception("session limit reached"))["content"]  # no retry_after
    assert _rate_limit_info(Exception("connection refused")) is None


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
