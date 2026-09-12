from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
SLOTS_DIR = PROJECT_ROOT / ".claude" / "additional" / "dm-slots"


def test_combat_rules_do_not_store_session_logs_as_world_facts():
    rules = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SLOTS_DIR.glob("*.md"))
    )

    assert 'dm-note.sh "combat"' not in rules
    assert (
        "Include the combat result in the summary passed to `dm-session.sh end`"
        in rules
    )


def test_combat_rules_require_narration_and_automatic_xp():
    rules = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SLOTS_DIR.glob("*.md"))
    )

    assert "Narrative Combat Beat [MANDATORY]" in rules
    assert "Never add the same combat XP manually" in rules
    assert "Every quest must be created with an explicit non-negative reward" in rules
