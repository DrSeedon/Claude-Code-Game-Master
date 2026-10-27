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


def test_hook_reminds_the_master_of_the_act_after_a_scene_move(sdir, monkeypatch, capsys):
    import os

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 1, "token": "t"}))
    (sdir / "act.json").write_text(json.dumps({"id": 1, "title": "Глава вторая", "place": "Дырявый Котёл", "lang": "ru"}))
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))
    monkeypatch.setenv("DM_PLAY_TABLE", "demo")

    def run(command):
        cli.run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "tool_response": {"stdout": ""}}))
        out = capsys.readouterr().out
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else None

    nudge = run('bash tools/dm-scene.sh "Библиотека Университета"')
    assert "Дырявый Котёл" in nudge and "tools/dm-art.sh" in nudge and "dm-screen.sh act" in nudge
    assert run("bash tools/dm-session.sh move 'Болота'") is not None
    assert run('bash tools/dm-scene.sh "x" && bash tools/dm-screen.sh act --image a.png --title T') is None   # done already
    assert run("bash tools/dm-player.sh hp x -1") is None
    monkeypatch.delenv("DM_PLAY_TABLE")                                     # at the laptop: no hub picture service
    assert "dm-art.sh" not in run('bash tools/dm-scene.sh "x"')


def test_hook_never_raises_on_garbage(sdir, monkeypatch):
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))

    cli.run_hook("not json at all")


def test_act_stores_interface_language(sdir, art):
    assert cli.set_act(sdir, art, "Act")["lang"] == "en"
    assert cli.set_act(sdir, art, "Act", lang="ru")["lang"] == "ru"
    assert cli.set_act(sdir, art, "Act")["lang"] == "ru"           # left out: the current act's


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


def test_wait_returns_the_next_action_and_remembers_it(tmp_path, capsys):
    import json as _json
    import threading

    from lib.screen import cli as screen_cli, inbox

    (tmp_path / "turn.json").write_text(_json.dumps({"id": 4, "answered": 0}))
    inbox.append_event(tmp_path, "Стив", "text", "уже отвечено")
    (tmp_path / "turn.json").write_text(_json.dumps({"id": 5, "answered": 1}))
    threading.Timer(0.2, lambda: inbox.append_event(tmp_path, "Стив", "voice", "читаю бланк")).start()

    assert screen_cli.wait_for_action(tmp_path, timeout=5, settle=0.1, poll=0.05) == 0
    assert capsys.readouterr().out.strip() == "[screen #2] Стив (voice): читаю бланк"
    assert _json.loads((tmp_path / "wait-cursor.json").read_text()) == {"last": 2}

    assert screen_cli.wait_for_action(tmp_path, timeout=0.3, settle=0.1, poll=0.05) == 2    # nothing new: no repeat
    assert "no player action yet" in capsys.readouterr().out


def test_wait_delivers_actions_that_arrive_together(tmp_path, capsys):
    from lib.screen import cli as screen_cli, inbox

    inbox.append_event(tmp_path, "Стив", "button", "Подписать бланк")
    inbox.append_event(tmp_path, "Оба", "text", "и заказать пива")

    assert screen_cli.wait_for_action(tmp_path, after=0, timeout=1, settle=0.05, poll=0.05) == 0
    assert capsys.readouterr().out.count("[screen #") == 2


def test_cursor_reads_zero_until_written_and_survives_garbage(tmp_path):
    assert cli.read_cursor(tmp_path) == 0
    cli.write_cursor(tmp_path, 5)
    assert cli.read_cursor(tmp_path) == 5 and json.loads((tmp_path / "wait-cursor.json").read_text()) == {"last": 5}
    (tmp_path / "wait-cursor.json").write_text('{"last": "x"}')
    assert cli.read_cursor(tmp_path) == 0


def test_next_batch_is_oldest_first_limited_and_leaves_the_cursor_alone(tmp_path):
    for n in range(8):
        inbox.append_event(tmp_path, "Ринсвинд", "text", f"действие {n + 1}")

    batch = cli.next_batch(tmp_path, 0, settle=0, max_events=6)

    assert [e["id"] for e in batch] == [1, 2, 3, 4, 5, 6] and not (tmp_path / "wait-cursor.json").exists()
    assert [e["id"] for e in cli.next_batch(tmp_path, 6, settle=0)] == [7, 8]
    assert cli.next_batch(tmp_path, 8, settle=0, timeout=0.2, poll=0.05) == []


def test_next_batch_blocks_until_an_action_arrives_and_gathers_the_ones_right_after(tmp_path):
    import threading

    threading.Timer(0.15, lambda: inbox.append_event(tmp_path, "Ринсвинд", "voice", "бежим")).start()
    threading.Timer(0.25, lambda: inbox.append_event(tmp_path, "Двацветок", "text", "а я фотографирую")).start()

    batch = cli.next_batch(tmp_path, 0, settle=0.4, timeout=3, poll=0.05)

    assert [e["text"] for e in batch] == ["бежим", "а я фотографирую"]


def test_an_action_sent_while_the_master_writes_is_delivered_next_and_stays_waiting(tmp_path, capsys):
    from lib.screen import server

    inbox.append_event(tmp_path, "Ринсвинд", "button", "1. Бежать")
    assert cli.wait_for_action(tmp_path, timeout=2, settle=0.05, poll=0.05) == 0          # delivered to the master
    capsys.readouterr()
    inbox.append_event(tmp_path, "Двацветок", "text", "подождите, я сфотографирую")       # arrives while the turn is written

    turn = cli.set_turn(tmp_path, {"blocks": ["<p>Вы бежите.</p>"], "question": "?", "options": []})

    state = server.build_state(tmp_path, dict)
    assert turn["answered"] == 1 and state["inbox_last"] == 2 and state["inbox_last"] > state["turn"]["answered"]   # the page still waits
    assert cli.wait_for_action(tmp_path, timeout=2, settle=0.05, poll=0.05) == 0
    assert capsys.readouterr().out.strip() == "[screen #2] Двацветок (text): подождите, я сфотографирую"


def test_wait_trusts_the_cursor_over_the_shown_turn(tmp_path, capsys):
    inbox.append_event(tmp_path, "Ринсвинд", "text", "первое")
    inbox.append_event(tmp_path, "Ринсвинд", "text", "второе, пришло во время записи хода")
    cli.write_cursor(tmp_path, 1)
    (tmp_path / "turn.json").write_text(json.dumps({"id": 3, "answered": 2}))      # stamped with the newest action

    assert cli.wait_for_action(tmp_path, timeout=1, settle=0.05, poll=0.05) == 0
    assert "[screen #2]" in capsys.readouterr().out


def test_set_turn_takes_an_explicit_answered_id(tmp_path):
    inbox.append_event(tmp_path, "Ринсвинд", "text", "x")
    cli.write_cursor(tmp_path, 1)

    assert cli.set_turn(tmp_path, {"blocks": ["<p>x</p>"]}, answered=0)["answered"] == 0
    assert cli.set_turn(tmp_path, {"blocks": ["<p>x</p>"]})["answered"] == 1


def test_listen_moves_the_cursor_as_it_prints(tmp_path, monkeypatch, capsys):
    inbox.append_event(tmp_path, "Ринсвинд", "text", "старое")
    naps = []

    class Done(Exception):
        pass

    def nap(seconds):
        naps.append(seconds)
        if len(naps) == 1:
            assert cli.read_cursor(tmp_path) == 1          # old actions count as delivered
            inbox.append_event(tmp_path, "Двацветок", "voice", "новое")
        else:
            raise Done

    monkeypatch.setattr(cli.time, "sleep", nap)
    with pytest.raises(Done):
        cli.listen(tmp_path, from_start=False)

    assert capsys.readouterr().out.strip() == "[screen #2] Двацветок (voice): новое" and cli.read_cursor(tmp_path) == 2


def test_status_shows_the_public_address_when_set(sdir, monkeypatch, capsys):
    import os

    sdir.mkdir(parents=True)
    (sdir / "server.json").write_text(json.dumps({"pid": os.getpid(), "port": 18116, "token": "t"}))
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))
    monkeypatch.setenv("DM_SCREEN_PUBLIC_URL", "https://dnd-play.seedon.ru/")

    cli.main(["status"])

    assert capsys.readouterr().out.splitlines() == ["running on http://127.0.0.1:18116/", "public: https://dnd-play.seedon.ru/"]


def test_retitling_with_the_shown_art_keeps_every_other_field(sdir, art):
    """The online contract retitles an act with screen/art.png itself: no SameFileError, nothing reset to defaults."""
    cards = [{"zone": "tl", "title": "РИНСВИНД", "dot": [100, 200]}]
    first = cli.set_act(sdir, art, "Глава первая", kicker="Глава первая", place="Анк-Морпорк", date="24 Жнивня",
                        style="soft", captions=cards, labels={"stealth": "Скрытность"}, lang="ru")

    second = cli.set_act(sdir, sdir / "art.png", "Глава вторая")

    assert second["id"] == 2 and second["title"] == "Глава вторая"
    keep = ("kicker", "place", "date", "style", "lang", "captions", "labels")
    assert {k: second[k] for k in keep} == {k: first[k] for k in keep}


def test_a_new_picture_drops_the_old_captions_but_keeps_the_rest(sdir, art, tmp_path):
    cli.set_act(sdir, art, "Акт 1", style="severe", lang="ru", captions=[{"zone": "tl", "title": "МАКСИМ"}], labels={"a": "А"})
    other = tmp_path / "other.png"
    Image.new("RGB", (64, 36), (230, 90, 20)).save(other)

    second = cli.set_act(sdir, other, "Акт 2")

    assert second["captions"] == [] and (second["style"], second["lang"], second["labels"]) == ("severe", "ru", {"a": "А"})
    same = tmp_path / "copy.png"
    same.write_bytes(other.read_bytes())
    assert cli.set_act(sdir, same, "Акт 3", captions=[{"zone": "tr", "title": "X"}])["captions"][0]["title"] == "X"
    assert cli.set_act(sdir, same, "Акт 4")["captions"][0]["title"] == "X"      # the same picture by content


def test_a_turn_with_nan_never_reaches_the_file(sdir):
    cli.set_turn(sdir, {"blocks": ["<p>x</p>"]})
    with pytest.raises(ValueError):
        cli._write(sdir / "turn.json", {"bars": float("nan")})

    assert json.loads((sdir / "turn.json").read_text())["id"] == 1


def _online_screen(tmp_path, state="idle", pid=None):
    import os

    sdir = tmp_path / "world-state" / "campaigns" / "pratchett-dungeon" / "screen"
    sdir.mkdir(parents=True)
    (tmp_path / "world-state" / "online-play-status.json").write_text(json.dumps(
        {"pid": pid or os.getpid(), "campaign": "pratchett-dungeon", "state": state, "last_error": None}))
    return sdir


@pytest.mark.parametrize("command", [["listen"], ["listen", "--from-start"], ["wait", "--timeout", "0.1"]])
def test_listen_and_wait_refuse_while_the_online_driver_plays_the_screen(tmp_path, monkeypatch, command):
    sdir = _online_screen(tmp_path)
    inbox.append_event(sdir, "Ринсвинд", "text", "x")
    cli.write_cursor(sdir, 0)                      # the driver's cursor: nobody else may move it
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))

    with pytest.raises(SystemExit, match="online table driver"):
        cli.main(command)

    assert cli.read_cursor(sdir) == 0


def test_wait_works_again_once_the_driver_is_gone(tmp_path, monkeypatch, capsys):
    sdir = _online_screen(tmp_path, pid=99999999)
    inbox.append_event(sdir, "Ринсвинд", "text", "x")
    monkeypatch.setenv("DM_SCREEN_DIR", str(sdir))

    assert cli.main(["wait", "--timeout", "1"]) == 0 and "[screen #1]" in capsys.readouterr().out
