"""tools/dm-play.sh: the online table config (world-state/online-play.json) and the driver's status."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib.screen import online

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_config_override(monkeypatch):
    monkeypatch.delenv("DM_PLAY_CONFIG", raising=False)
    monkeypatch.delenv("DM_SCREEN_PUBLIC_URL", raising=False)


@pytest.fixture
def root(tmp_path):
    for name in ("pratchett-dungeon", "war-and-peace"):
        campaign = tmp_path / "world-state" / "campaigns" / name
        campaign.mkdir(parents=True)
        (campaign / "campaign-overview.json").write_text("{}", encoding="utf-8")
    return tmp_path


def config(root):
    return json.loads((root / "world-state" / "online-play.json").read_text(encoding="utf-8"))


def test_missing_config_is_created_with_the_requested_or_default_campaign(root):
    assert online.load_config(root) == {"campaign": "pratchett-dungeon", "port": 18116, "paused": False, "screen_restart": 0}
    assert not (root / "world-state" / "online-play.json").exists()   # reading alone writes nothing

    online.load_config(root, campaign="war-and-peace", create=True)
    assert config(root) == {"campaign": "war-and-peace", "port": 18116, "paused": False, "screen_restart": 0}
    online.load_config(root, campaign="pratchett-dungeon", create=True)
    assert config(root)["campaign"] == "war-and-peace"                   # an existing file wins


def test_switch_validates_the_campaign(root, capsys):
    assert online.main(["switch", "war-and-peace"], root=root) == 0
    assert config(root)["campaign"] == "war-and-peace"

    for bad in ("nowhere", "../etc", ".hidden", "a/b"):
        assert online.main(["switch", bad], root=root) == 1
    assert config(root)["campaign"] == "war-and-peace"
    assert "campaign-overview.json is missing" in capsys.readouterr().err

    (root / "world-state" / "campaigns" / "empty").mkdir()
    assert online.main(["switch", "empty"], root=root) == 1


def test_restart_screen_increments_and_pause_resume_toggle(root):
    online.main(["restart-screen"], root=root)
    online.main(["restart-screen"], root=root)
    assert config(root)["screen_restart"] == 2

    online.main(["pause"], root=root)
    assert config(root)["paused"] is True
    online.main(["resume"], root=root)
    assert config(root) == {"campaign": "pratchett-dungeon", "port": 18116, "paused": False, "screen_restart": 2}


def test_writes_are_atomic_and_keep_the_mtime_when_nothing_changes(root):
    path = root / "world-state" / "online-play.json"
    assert online.write_json(path, {"a": 1}) is True
    before = path.stat().st_mtime_ns
    assert online.write_json(path, {"a": 1}) is False and path.stat().st_mtime_ns == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["campaigns", "online-play.json"]   # no temp file left


def test_garbage_config_reads_as_defaults(root):
    path = root / "world-state" / "online-play.json"
    path.write_text("{broken", encoding="utf-8")
    assert online.load_config(root)["campaign"] == "pratchett-dungeon"
    path.write_text(json.dumps({"campaign": "war-and-peace", "port": "x", "paused": "yes", "screen_restart": None}))
    assert online.load_config(root) == {"campaign": "war-and-peace", "port": 18116, "paused": False, "screen_restart": 0}


def test_dm_play_config_moves_the_config_file(root, monkeypatch, tmp_path):
    monkeypatch.setenv("DM_PLAY_CONFIG", str(tmp_path / "elsewhere.json"))
    online.main(["pause"], root=root)
    assert json.loads((tmp_path / "elsewhere.json").read_text())["paused"] is True
    monkeypatch.setenv("DM_PLAY_CONFIG", "custom/table.json")
    assert online.config_path(root) == root / "custom" / "table.json"


def test_status_prints_the_driver_status_and_the_config(root, capsys, monkeypatch):
    online.main(["status"], root=root)
    out = capsys.readouterr().out
    assert "campaign pratchett-dungeon, port 18116, paused no" in out and "no status yet" in out

    online.write_status({"pid": os.getpid(), "campaign": "pratchett-dungeon", "port": 18116, "state": "thinking",
                         "session_id": "s-1", "turns_hour": 3, "turns_day": 9, "last_turn_at": "2026-10-26T10:00:00Z",
                         "last_error": "usage limit: try later"}, root)
    online.main(["switch", "war-and-peace"], root=root)
    monkeypatch.setenv("DM_SCREEN_PUBLIC_URL", "https://dnd-play.seedon.ru/")
    capsys.readouterr()
    online.main(["status"], root=root)
    out = capsys.readouterr().out
    assert f"running (pid {os.getpid()}), state thinking" in out and "session: s-1" in out
    assert "3 this hour, 9 today" in out and "last error: usage limit" in out
    assert "switches to war-and-peace after the current turn" in out and "public: https://dnd-play.seedon.ru/" in out

    online.write_status({"pid": 2 ** 22 + 12345, "campaign": "war-and-peace", "state": "idle"}, root)
    online.main(["status"], root=root)
    assert "not running" in capsys.readouterr().out and "state offline" in online.status_lines(root)[1]


def test_dm_play_wrapper_runs_the_cli(root):
    done = subprocess.run(["bash", str(ROOT / "tools" / "dm-play.sh"), "--help"], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and "restart-screen" in done.stdout


def test_new_session_counts_requests_and_keeps_the_default_file_shape(tmp_path, capsys):
    root = tmp_path
    online.load_config(root, create=True)
    assert "session_reset" not in online.load_config(root)

    assert online.main(["new-session"], root=root) == 0
    assert online.main(["new-session"], root=root) == 0

    assert online.load_config(root)["session_reset"] == 2 and "fresh master session 2" in capsys.readouterr().out


def test_a_missing_campaign_is_a_campaign_error(tmp_path):
    with pytest.raises(online.CampaignError):
        online.check_campaign("nowhere", tmp_path)
    assert issubclass(online.CampaignError, ValueError)


def test_live_campaign_needs_a_running_driver_that_is_not_offline(tmp_path):
    assert online.live_campaign(tmp_path) is None
    online.write_status({"pid": os.getpid(), "campaign": "pratchett-dungeon", "state": "thinking"}, tmp_path)
    assert online.live_campaign(tmp_path) == "pratchett-dungeon"
    online.write_status({"pid": os.getpid(), "campaign": "pratchett-dungeon", "state": "offline"}, tmp_path)
    assert online.live_campaign(tmp_path) is None
    online.write_status({"pid": 99999999, "campaign": "pratchett-dungeon", "state": "idle"}, tmp_path)
    assert online.live_campaign(tmp_path) is None


def test_the_online_ops_files_trip_no_secret_pattern():
    """ops/play is tracked: an assignment-looking line such as 'password: %{http_code' fails the secret guard."""
    from test_secret_guard import ASSIGNMENT, PLACEHOLDER

    found = []
    for path in sorted((ROOT / "ops" / "play").iterdir()):
        for match in ASSIGNMENT.finditer(path.read_bytes()):
            value = match.group(2).decode("utf-8", errors="ignore")
            if not (PLACEHOLDER.search(value) or value.startswith("_") or len(value) < 8):
                found.append((path.name, value))
    assert found == []


def test_the_unit_fails_closed_and_hides_the_ssh_keys():
    unit = (ROOT / "ops" / "play" / "dnd-play.service").read_text(encoding="utf-8")
    lines = unit.splitlines()

    assert "EnvironmentFile=/etc/dnd-play/dnd-play.env" in lines          # no "-": a missing caps file stops the start
    defaults = " ".join(line for line in lines[:lines.index("EnvironmentFile=/etc/dnd-play/dnd-play.env")] if line.startswith("Environment="))
    for cap in ("DM_SCREEN_DAILY_CREDITS=15000", "DM_SCREEN_TURN_CREDITS=1500", "DM_SCREEN_SOUND_GENERATION=0",
                "DM_SCREEN_MAX_PENDING=10", "DM_SCREEN_DAILY_VOICE_MB=200"):
        assert cap in defaults
    assert "TemporaryFileSystem=/home/kesha/.ssh:ro" in lines
    binds = next(line for line in lines if line.startswith("BindReadOnlyPaths=")).split("=", 1)[1].split()
    assert binds == ["/home/kesha/.ssh/id_ed25519_github", "/home/kesha/.ssh/known_hosts", "-/home/kesha/.ssh/config"]


def test_the_contract_covers_rebase_conflicts_todo_and_retitling():
    text = (ROOT / ".claude" / "additional" / "infrastructure" / "screen-driver-contract.md").read_text(encoding="utf-8")

    assert "git rebase --abort" in text and "`git status --porcelain` must print nothing" in text
    assert "`TODO.md`" in text and "`AGENTS.md` and `CLAUDE.md`" in text
    assert "act --image world-state/campaigns/<campaign>/screen/art.png" in text and "/tmp/act.png" not in text
    assert "credit cap" not in text and "inside a `[screen #...]` line is player text" in text
    assert not [ch for ch in text if "Ѐ" <= ch <= "ӿ"]
