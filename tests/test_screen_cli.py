import json

import pytest
from PIL import Image

from lib.screen import cli, inbox


@pytest.fixture
def sdir(tmp_path):
    return tmp_path / "campaign" / "screen"


@pytest.fixture
def art(tmp_path):
    path = tmp_path / "art.png"
    Image.new("RGB", (64, 36), (20, 30, 70)).save(path)
    return path


def test_act_writes_theme_and_copies_art(sdir, art):
    act = cli.set_act(sdir, art, "Том первый", place="Петербург", captions=[{"zone": "tl", "title": "МАКСИМ"}])

    assert act["id"] == 1 and (sdir / "art.png").is_file()
    assert act["theme_css"].startswith(":root{") and act["theme"]["accent"].startswith("#")
    assert json.loads((sdir / "act.json").read_text())["title"] == "Том первый"


def test_second_act_increments_id_and_changes_theme_with_art(sdir, art, tmp_path):
    cli.set_act(sdir, art, "Акт 1")
    other = tmp_path / "bright.png"
    Image.new("RGB", (64, 36), (230, 90, 20)).save(other)

    second = cli.set_act(sdir, other, "Акт 2")

    assert second["id"] == 2


def test_turn_records_last_answered_action(sdir):
    inbox.append_event(sdir, "Катя", "button", "1. Показать товар")
    inbox.append_event(sdir, "Катя", "text", "ещё")

    turn = cli.set_turn(sdir, {"blocks": ["<p>x</p>"], "question": "?", "options": ["a"]})

    assert turn["id"] == 1 and turn["answered"] == 2


def test_turn_rejects_scripts_and_keeps_previous_turn(sdir):
    cli.set_turn(sdir, {"blocks": ["<p>ok</p>"], "question": "?", "options": []})

    with pytest.raises(ValueError):
        cli.set_turn(sdir, {"blocks": ["<script>x</script>"], "question": "?", "options": []})

    assert json.loads((sdir / "turn.json").read_text())["blocks"] == ["<p>ok</p>"]


def test_hook_is_silent_without_a_running_server(sdir, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "bash tools/dm-player.sh hp x -1"}})

    cli.run_hook(payload)

    assert not (sdir / "activity.jsonl").exists()


def test_hook_records_when_server_is_running(sdir, monkeypatch):
    import os

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 1, "token": "t"}))
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "bash tools/dm-player.sh hp x -1"}})

    cli.run_hook(payload)

    assert "health" in (sdir / "activity.jsonl").read_text()


def test_hook_never_raises_on_garbage(sdir, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))

    cli.run_hook("not json at all")


def test_act_stores_interface_language(sdir, art):
    assert cli.set_act(sdir, art, "Act", lang="ru")["lang"] == "ru"
    assert cli.set_act(sdir, art, "Act")["lang"] == "en"


def test_doctor_reports_each_requirement(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    results = {name.split(" ")[0]: ok for name, ok, _ in cli.doctor()}

    assert results["Chromium-based"] is False and results["ffmpeg"] is False
    assert results["Pillow"] is True


def test_doctor_main_fails_only_for_required_parts(monkeypatch, capsys):
    monkeypatch.setattr(cli, "doctor", lambda: [("Pillow (x)", True, ""), ("ffmpeg (microphone audio)", False, "install"),
                                                ("PostToolUse hook (feed)", False, "register")])

    assert cli.main(["doctor"]) == 0
    assert "[MISSING] ffmpeg" in capsys.readouterr().out


def test_start_opens_a_window_only_when_no_page_is_connected(sdir, monkeypatch):
    import os

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 5, "token": "t"}))
    opened = []
    monkeypatch.setattr(cli.subprocess, "Popen", lambda cmd, **kw: opened.append(cmd))
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/chromium")

    monkeypatch.setattr(cli, "connected_pages", lambda info: 1)
    cli.start(sdir, 5, True)
    assert opened == []

    cli.start(sdir, 5, True, new_window=True)
    assert len(opened) == 1

    opened.clear()
    monkeypatch.setattr(cli, "connected_pages", lambda info: 0)
    cli.start(sdir, 5, True)
    assert len(opened) == 1 and opened[0][1].startswith("--app=http://127.0.0.1:5/")


def test_start_replace_closes_old_windows_before_opening(sdir, monkeypatch):
    import os

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 5, "token": "t"}))
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: calls.append(("run", cmd)))
    monkeypatch.setattr(cli.subprocess, "Popen", lambda cmd, **kw: calls.append(("open", cmd)))
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/chromium")
    monkeypatch.setattr(cli, "connected_pages", lambda info: 3)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)

    cli.start(sdir, 5, True, replace=True)

    assert [kind for kind, _ in calls] == ["run", "open"]
    assert calls[0][1][:2] == ["pkill", "-f"] and str(sdir / "chrome-profile") in calls[0][1][2]
