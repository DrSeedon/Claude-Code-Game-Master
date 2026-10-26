import json

from backend.runtime.session_store import (
    clear_runtime_session,
    load_runtime_session,
    runtime_session_path,
    save_runtime_session,
)


def test_runtime_session_round_trip_and_clear(tmp_path):
    campaign_dir = tmp_path / "campaign"

    stored = save_runtime_session(
        campaign_dir,
        runtime_id="codex",
        model_name="gpt-5.6-luna",
        session_id="thread-42",
    )

    assert load_runtime_session(campaign_dir) == stored
    assert runtime_session_path(campaign_dir).stat().st_mode & 0o777 == 0o600

    clear_runtime_session(campaign_dir)
    assert load_runtime_session(campaign_dir) is None


def test_corrupt_or_incomplete_runtime_session_is_ignored(tmp_path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    path = runtime_session_path(campaign_dir)
    path.write_text("{broken", encoding="utf-8")
    assert load_runtime_session(campaign_dir) is None

    path.write_text(json.dumps({"version": 1, "session_id": "only-id"}))
    assert load_runtime_session(campaign_dir) is None


def test_named_session_file_lives_beside_the_web_one(tmp_path):
    screen_dir = tmp_path / "campaign" / "screen"
    save_runtime_session(screen_dir, runtime_id="claude", model_name="claude-sonnet-5-5", session_id="gm-1",
                         filename="gm-session.json")

    assert (screen_dir / "gm-session.json").stat().st_mode & 0o777 == 0o600
    assert not (screen_dir / ".runtime-session.json").exists()
    assert load_runtime_session(screen_dir) is None
    assert load_runtime_session(screen_dir, "gm-session.json").session_id == "gm-1"

    clear_runtime_session(screen_dir, "gm-session.json")
    assert load_runtime_session(screen_dir, "gm-session.json") is None
