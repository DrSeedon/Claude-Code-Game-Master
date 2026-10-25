import pytest

from lib.screen import activity, hook


def test_append_and_read_activity(tmp_path):
    a = activity.append_activity(tmp_path, "think", "Читаю намерение игроков")
    b = activity.append_activity(tmp_path, "roll", "Торговля против DC 12: 14 + 3 = 17, успех")

    assert (a["id"], b["id"]) == (1, 2)
    assert [e["kind"] for e in activity.read_activity(tmp_path)] == ["think", "roll"]
    assert [e["id"] for e in activity.read_activity(tmp_path, after_id=1)] == [2]


def test_unknown_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        activity.append_activity(tmp_path, "shout", "x")


def test_long_text_is_trimmed(tmp_path):
    assert len(activity.append_activity(tmp_path, "info", "я" * 900)["text"]) == activity.MAX_TEXT


def test_tail_limits_history(tmp_path):
    for i in range(30):
        activity.append_activity(tmp_path, "info", f"шаг {i}")

    assert len(activity.read_activity(tmp_path, tail=10)) == 10
    assert activity.read_activity(tmp_path, tail=10)[-1]["text"] == "шаг 29"


def first(payload, lang="en"):
    events = hook.activities_from_hook(payload, lang)
    return events[0] if events else None


def payload(command, stdout="", tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}, "tool_response": {"stdout": stdout}}


def test_hook_turns_dice_into_roll_events():
    out = "🎲 Торговля (Максим) vs DC 12: [14] +3 = 17 — ✓ SUCCESS\n"

    event = first(payload('bash tools/dm-roll.sh --skill "Trade" --dc 12', out))

    assert event["kind"] == "roll"
    assert "17" in event["text"] and "SUCCESS" in event["text"]


def test_hook_shows_friendly_state_changes_without_arguments():
    event = first(payload('bash tools/dm-player.sh hp "Максим" -3'), "ru")

    assert event == {"kind": "save", "text": "Здоровье героя изменилось"}
    assert first(payload('bash tools/dm-player.sh hp "Максим" -3'), "en")["text"] == "A hero's health changed"


def test_hook_never_leaks_names_or_descriptions_of_new_npcs():
    command = 'bash tools/dm-npc.sh create "Поручик Лабазов" "ищет надёжного человека, тайный шпион" neutral'

    event = first(payload(command), "ru")

    assert event["text"] == "Появился новый персонаж"
    assert "Лабазов" not in event["text"] and "шпион" not in event["text"]


@pytest.mark.parametrize("command", [
    'bash tools/dm-consequence.sh add "засада" "завтра" --hours 24',
    'bash tools/dm-note.sh "dm_secret" "Primary scenario: X"',
    'bash tools/dm-world.sh add-node misc:x --name X --type misc',
    'bash tools/dm-npc.sh locate "Лабазов" "Передняя"',
])
def test_hook_hides_machinery_and_secrets(command):
    assert first(payload(command), "ru") is None


@pytest.mark.parametrize("command,expected", [
    ('bash tools/dm-plot.sh objective "С чёрного хода" complete 1', "Цель задания выполнена"),
    ('bash tools/dm-plot.sh objective "Q" add "новая цель"', "В задании появилась новая цель"),
    ('bash tools/dm-plot.sh complete "Q"', "Задание завершено"),
    ('bash tools/dm-inventory.sh update Максим --gold +100 --reason "x"', "Вещи и товар перераспределены"),
])
def test_hook_describes_quests_and_inventory(command, expected):
    assert first(payload(command), "ru")["text"] == expected


def test_hook_reports_elapsed_time_in_minutes_and_hours():
    short = first(payload('bash tools/dm-time.sh "_" "d" --elapsed 0.1', "⏰ 20:06 (+0.1h)"), "ru")
    long = first(payload('bash tools/dm-time.sh "_" "d" --elapsed 8', "⏰ 04:00 (+8.0h)"), "en")

    assert short["text"] == "Проходит время: +6 мин"
    assert long["text"] == "Time passes: +8 h"


def test_hook_ignores_unrelated_commands_and_tools():
    assert first(payload("ls -la")) is None
    assert first(payload("git status", tool="Bash")) is None
    assert first(payload("bash tools/dm-roll.sh 1d20", tool="Read")) is None


def test_hook_ignores_screen_tool_itself():
    assert first(payload("bash tools/dm-screen.sh turn --file t.json")) is None


def test_hook_survives_garbage():
    assert first({}) is None
    assert first({"tool_name": "Bash", "tool_input": None}) is None


def test_chained_commands_yield_one_line_per_master_tool_in_order():
    command = ('bash tools/dm-npc.sh create "X" "d" neutral; bash tools/dm-plot.sh objective "Q" complete 1 '
               '&& bash tools/dm-consequence.sh add "e" "t" --hours 1; bash tools/dm-time.sh "_" "d" --elapsed 0.1')

    events = hook.activities_from_hook(payload(command, "⏰ 20:06 (+0.1h)"), "ru")

    assert [e["text"] for e in events] == ["Появился новый персонаж", "Цель задания выполнена", "Проходит время: +6 мин"]


def test_several_rolls_in_one_call_make_one_dice_line():
    out = "🎲 A: [10] +2 = 12 — ✓ SUCCESS\n🎲 B: [3] +1 = 4 — ✗ FAIL\n"

    events = hook.activities_from_hook(payload('bash tools/dm-roll.sh "1d20+2" --label A && bash tools/dm-roll.sh "1d20+1" --label B', out))

    assert len(events) == 1 and "A:" in events[0]["text"] and "B:" in events[0]["text"]


@pytest.mark.parametrize("command", ["bash tools/dm-player.sh gold", "bash tools/dm-player.sh hp", "bash tools/dm-player.sh xp"])
def test_reading_a_value_is_not_a_change(command):
    assert first(payload(command), "ru") is None


def test_changing_a_value_is_shown():
    assert first(payload("bash tools/dm-player.sh gold +9500"), "ru")["text"] == "Кошелёк изменился"
