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


def test_panels_update_keeps_the_turn_id(sdir):
    cli.set_turn(sdir, {"blocks": ["<p>x</p>"], "question": "?", "options": ["a"], "panels": [{"title": "A", "chips": ["1"]}]})

    cli.set_panels(sdir, [{"title": "A", "chips": ["{money}", "2"]}])

    turn = json.loads((sdir / "turn.json").read_text())
    assert turn["id"] == 1 and turn["panels"][0]["chips"] == ["{money}", "2"]


def test_panels_update_needs_a_turn_and_valid_panels(sdir):
    with pytest.raises(ValueError):
        cli.set_panels(sdir, [{"title": "A"}])
    cli.set_turn(sdir, {"blocks": ["<p>x</p>"], "question": "?", "options": []})
    with pytest.raises(ValueError):
        cli.set_panels(sdir, [{"title": "<b>A</b>", "chips": ["x"]}])


def test_turn_is_logged_in_full_with_a_snapshot_of_the_game_values(sdir):
    from lib.screen import eventlog

    campaign = sdir.parent
    campaign.mkdir(parents=True, exist_ok=True)
    (campaign / "campaign-overview.json").write_text(json.dumps({"current_date": "10 июля, 1805 г.", "precise_time": "20:21", "player_position": {"current_location": "Двор"}}))
    (campaign / "world.json").write_text(json.dumps({"nodes": {"player:active": {"type": "player", "name": "Максим", "data": {"hp": {"current": 9, "max": 9}, "money": 21500}}}}))

    cli.set_turn(sdir, {"blocks": ["<p>Полный текст хода</p>"], "question": "Что делаете?", "options": ["А", "Б"], "panels": [{"title": "ОБОЗ", "chips": ["x"]}]})

    event = eventlog.read(sdir, kinds={"turn"})[0]
    assert event["id"] == 1 and event["blocks"] == ["<p>Полный текст хода</p>"] and event["options"] == ["А", "Б"] and event["panels"][0]["title"] == "ОБОЗ"
    assert event["snapshot"]["time"] == "20:21" and event["snapshot"]["player"]["money"] == 21500


def test_act_and_panels_are_logged(sdir, art):
    from lib.screen import eventlog

    cli.set_act(sdir, art, "Акт 1", place="Петербург", style="severe", lang="ru")
    cli.set_turn(sdir, {"blocks": ["<p>x</p>"], "question": "?", "options": []})
    cli.set_panels(sdir, [{"title": "A", "chips": ["1"]}])

    act = eventlog.read(sdir, kinds={"act"})[0]
    assert act["title"] == "Акт 1" and act["style"] == "severe" and act["theme"]["accent"].startswith("#")
    assert eventlog.read(sdir, kinds={"panels"})[0]["panels"][0]["chips"] == ["1"]


def test_hook_logs_the_full_command_and_what_was_shown(sdir, monkeypatch):
    import os

    from lib.screen import eventlog

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 1, "token": "t"}))
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))
    (sdir / "act.json").write_text(json.dumps({"lang": "ru"}))
    payload = {"tool_name": "Bash", "tool_input": {"command": 'bash tools/dm-npc.sh create "Поручик Лабазов" "тайный шпион" neutral'},
               "tool_response": {"stdout": "✓ NPC created: Поручик Лабазов"}}

    cli.run_hook(json.dumps(payload))

    tool = eventlog.read(sdir, kinds={"tool"})[0]
    assert "Поручик Лабазов" in tool["command"] and "NPC created" in tool["output"] and tool["shown"] == ["Появился новый персонаж"]
    assert eventlog.read(sdir, kinds={"activity"})[0]["text"] == "Появился новый персонаж"


def test_log_viewer_filters_and_summarises(sdir, capsys):
    from lib.screen import eventlog

    eventlog.log(sdir, "tts", credits=30, chars=61, cached=False, text="привет")
    eventlog.log(sdir, "error", message="boom")

    cli.show_log(sdir, tail=10, kinds={"tts"})
    out = capsys.readouterr().out
    assert "tts" in out and "привет" in out and "boom" not in out

    cli.show_log(sdir, summary=True)
    assert "tts_credits" in capsys.readouterr().out


def test_a_service_refusal_is_one_readable_line_and_is_logged(sdir, monkeypatch, capsys):
    from lib.screen import eventlog, speech

    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))

    def refuse(*args, **kwargs):
        raise speech.SpeechError("ElevenLabs: Creating a voice through the API is only available on a paid plan.", 402)

    monkeypatch.setattr(cli, "voice_command", refuse)

    code = cli.run(["voice", "show"])

    assert code == 1 and "only available on a paid plan" in capsys.readouterr().err
    assert "paid plan" in eventlog.read(sdir, kinds={"error"})[0]["message"]


def test_a_voice_in_use_is_not_deleted_without_force(tmp_path, monkeypatch, capsys):
    import json as _json

    from lib.screen import cli as screen_cli

    camp = tmp_path / "world-state" / "campaigns" / "war"
    (camp / "screen").mkdir(parents=True)
    (camp / "screen" / "speech.json").write_text(_json.dumps({"narrator": {"voice_id": "SLAV"}, "cast": {"female": {"voice_id": "VIC"}}}))
    (camp / "world.json").write_text(_json.dumps({"nodes": {"npc:a": {"name": "Анна", "data": {"voice": {"voice_id": "VIC"}}}}}))
    (camp.parent / ".gitkeep").write_text("")
    monkeypatch.setattr(screen_cli, "PROJECT_ROOT", tmp_path)

    class Api:
        deleted = []

        def voices(self):
            return [{"voice_id": "SLAV", "name": "Slavic Man", "category": "generated"}, {"voice_id": "ADAM", "name": "Adam", "category": "premade"}]

        def delete_voice(self, voice_id):
            self.deleted.append(voice_id)

    api = Api()
    assert screen_cli.voice_users("VIC") == ["war: cast female", "war: Анна"]
    with pytest.raises(SystemExit, match="still used by: war: narrator"):
        screen_cli.delete_voice(api, "Slavic")
    with pytest.raises(SystemExit, match="premade"):
        screen_cli.delete_voice(api, "Adam")
    assert api.deleted == []

    screen_cli.delete_voice(api, "Slavic", force=True)

    assert api.deleted == ["SLAV"] and "still referenced by: war: narrator" in capsys.readouterr().out
