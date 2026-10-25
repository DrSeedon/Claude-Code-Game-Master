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


def payload(command, stdout="", tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}, "tool_response": {"stdout": stdout}}


def test_hook_turns_dice_into_roll_events():
    out = "🎲 Торговля (Максим) vs DC 12: [14] +3 = 17 — ✓ SUCCESS\n"

    event = hook.activity_from_hook(payload('bash tools/dm-roll.sh --skill "Trade" --dc 12', out))

    assert event["kind"] == "roll"
    assert "17" in event["text"] and "SUCCESS" in event["text"]


def test_hook_turns_state_changes_into_save_events():
    event = hook.activity_from_hook(payload('bash tools/dm-player.sh hp "Максим" -3'))

    assert event["kind"] == "save" and "dm-player" in event["text"]


def test_hook_ignores_unrelated_commands_and_tools():
    assert hook.activity_from_hook(payload("ls -la")) is None
    assert hook.activity_from_hook(payload("git status", tool="Bash")) is None
    assert hook.activity_from_hook(payload("bash tools/dm-roll.sh 1d20", tool="Read")) is None


def test_hook_ignores_screen_tool_itself():
    assert hook.activity_from_hook(payload("bash tools/dm-screen.sh turn --file t.json")) is None


def test_hook_survives_garbage():
    assert hook.activity_from_hook({}) is None
    assert hook.activity_from_hook({"tool_name": "Bash", "tool_input": None}) is None
