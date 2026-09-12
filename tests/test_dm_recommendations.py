import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
INFRASTRUCTURE = PROJECT_ROOT / ".claude" / "additional" / "infrastructure"


def _recommend(script: str, concept: str) -> str:
    result = subprocess.run(
        ["bash", str(INFRASTRUCTURE / script), "recommend", concept],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_narrator_recommendation_understands_multiword_fantasy():
    assert _recommend("dm-narrator.sh", "classic fantasy D&D") == "epic-heroic"


def test_narrator_recommendation_has_neutral_fallback():
    assert _recommend("dm-narrator.sh", "unclassified genre") == "serious-cinematic"


def test_campaign_rules_skip_plain_dnd():
    assert _recommend("dm-campaign-rules.sh", "classic fantasy D&D") == "none"


def test_campaign_rules_match_multiword_specialized_genre():
    assert (
        _recommend("dm-campaign-rules.sh", "political fantasy court intrigue")
        == "political-intrigue"
    )
