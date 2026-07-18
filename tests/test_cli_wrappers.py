import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
TOOLS = PROJECT_ROOT / "tools"


def _campaign_env() -> dict[str, str]:
    campaigns = sorted(
        path.name
        for path in (PROJECT_ROOT / "world-state" / "campaigns").iterdir()
        if path.is_dir()
    )
    assert campaigns, "CLI contract tests require one repository campaign"
    return {**os.environ, "DM_ACTIVE_CAMPAIGN": campaigns[0], "TERM": "dumb"}


def _run(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(TOOLS / tool), *args],
        cwd=PROJECT_ROOT,
        env=_campaign_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_player_status_is_a_read_only_show_alias():
    result = _run("dm-player.sh", "status")

    assert result.returncode == 0
    assert "Usage: dm-player.sh" not in result.stdout
    assert "\x1b[" not in result.stdout


def test_player_unknown_action_is_an_error():
    result = _run("dm-player.sh", "invented-action")

    assert result.returncode == 1
    assert "Unknown action: invented-action" in result.stderr


def test_campaign_status_is_an_info_alias():
    result = _run("dm-campaign.sh", "status")

    assert result.returncode == 0
    assert "Unknown action" not in result.stdout


def test_session_help_is_supported():
    result = _run("dm-session.sh", "--help")

    assert result.returncode == 0
    assert "Session Actions:" in result.stdout
