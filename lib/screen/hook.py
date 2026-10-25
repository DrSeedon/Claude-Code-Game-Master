"""PostToolUse hook: turn the Master's tool calls into short, spoiler-free lines for the live feed.

The feed never shows command arguments (names, descriptions, secrets). Hidden machinery
(consequences, notes, world edits) is not shown at all.
"""

import re
import shlex

_DM_TOOL = re.compile(r"(?:^|[\s;&|])(?:bash\s+)?(?:\./)?(?:modules/[\w-]+/)?tools/(dm-[\w-]+)\.sh\b(.*)")
_DICE = re.compile(r"🎲[^\n]*")
_ELAPSED = re.compile(r"\(\+([\d.]+)h\)")
_ROLL_TOOLS = {"dm-roll", "dm-mass-combat"}
MAX_TEXT = 300

# (tool, first word, second word or None) -> (kind, message key); anything not listed stays hidden
_RULES = {
    ("dm-npc", "create", None): ("world", "npc_new"),
    ("dm-npc", "update", None): ("world", "npc_memory"),
    ("dm-npc", "event", None): ("world", "npc_memory"),
    ("dm-npc", "promote", None): ("world", "npc_party"),
    ("dm-npc", "demote", None): ("world", "npc_leave"),
    ("dm-npc", "hp", None): ("save", "npc_hp"),
    ("dm-npc", "attitude", None): ("world", "npc_attitude"),
    ("dm-plot", "add", None): ("world", "quest_new"),
    ("dm-plot", "complete", None): ("world", "quest_done"),
    ("dm-plot", "fail", None): ("world", "quest_failed"),
    ("dm-plot", "objective", "complete"): ("world", "quest_goal_done"),
    ("dm-plot", "objective", "add"): ("world", "quest_goal_new"),
    ("dm-player", "hp", None): ("save", "player_hp"),
    ("dm-player", "hp-max", None): ("save", "player_hp"),
    ("dm-player", "xp", None): ("save", "player_xp"),
    ("dm-player", "gold", None): ("save", "player_gold"),
    ("dm-player", "condition", None): ("save", "player_cond"),
    ("dm-condition", "add", None): ("save", "player_cond"),
    ("dm-condition", "remove", None): ("save", "player_cond"),
    ("dm-inventory", "update", None): ("save", "inventory"),
    ("dm-inventory", "loot", None): ("save", "inventory"),
    ("dm-inventory", "transfer", None): ("save", "inventory"),
    ("dm-inventory", "remove", None): ("save", "inventory"),
    ("dm-inventory", "use", None): ("save", "inventory"),
    ("dm-session", "move", None): ("world", "move"),
    ("dm-scene", None, None): ("world", "scene"),
    ("dm-time", None, None): ("world", "time"),
}

MESSAGES = {
    "ru": {
        "npc_new": "Появился новый персонаж", "npc_memory": "Персонаж запомнил происходящее",
        "npc_party": "Персонаж присоединился к спутникам", "npc_leave": "Персонаж покинул спутников",
        "npc_hp": "Здоровье спутника изменилось", "npc_attitude": "Отношение персонажа изменилось",
        "quest_new": "Записано новое задание", "quest_done": "Задание завершено", "quest_failed": "Задание провалено",
        "quest_goal_done": "Цель задания выполнена", "quest_goal_new": "В задании появилась новая цель",
        "player_hp": "Здоровье героя изменилось", "player_xp": "Герой получил опыт", "player_gold": "Кошелёк изменился",
        "player_cond": "Состояние героя изменилось", "inventory": "Вещи и товар перераспределены",
        "move": "Герои переходят в другое место", "scene": "Сцена сменилась", "time": "Проходит время{amount}",
        "min": "мин", "hour": "ч",
    },
    "en": {
        "npc_new": "A new character appears", "npc_memory": "A character remembers what happened",
        "npc_party": "A character joins the party", "npc_leave": "A character leaves the party",
        "npc_hp": "A companion's health changed", "npc_attitude": "A character's attitude changed",
        "quest_new": "A new quest is recorded", "quest_done": "Quest completed", "quest_failed": "Quest failed",
        "quest_goal_done": "A quest objective is done", "quest_goal_new": "A new quest objective appeared",
        "player_hp": "A hero's health changed", "player_xp": "A hero gained experience", "player_gold": "The purse changed",
        "player_cond": "A hero's condition changed", "inventory": "Items and goods were moved",
        "move": "The heroes move on", "scene": "The scene changes", "time": "Time passes{amount}",
        "min": "min", "hour": "h",
    },
}


def _amount(stdout, words):
    match = _ELAPSED.search(stdout or "")
    if not match:
        return ""
    hours = float(match.group(1))
    if hours < 1:
        return f": +{max(1, round(hours * 60))} {words['min']}"
    return f": +{hours:g} {words['hour']}"


def describe(tool, rest, stdout="", lang="en"):
    """Return {'kind','text'} for a Master tool call that is worth showing, otherwise None."""
    try:
        words = shlex.split(rest)
    except ValueError:
        words = rest.split()
    rule = None
    sub = words[0] if words else None
    sub2 = words[2] if len(words) > 2 else None
    for key in ((tool, sub, sub2), (tool, sub, None), (tool, None, None)):
        if key in _RULES:
            rule = _RULES[key]
            break
    if not rule:
        return None
    if tool == "dm-player" and sub in ("gold", "hp", "hp-max", "xp") and len(words) < 2:
        return None  # a bare "gold" / "hp" only shows the value, nothing changed
    kind, message = rule
    texts = MESSAGES.get(lang, MESSAGES["en"])
    text = texts[message].format(amount=_amount(stdout, texts) if message == "time" else "")
    return {"kind": kind, "text": text}


_SEGMENT_SPLIT = re.compile(r"\s*(?:;|&&|\|\||\n)\s*")


def activities_from_hook(payload, lang="en"):
    """All feed lines for one Bash call: a chained command (a; b && c) yields one line per Master tool."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return []
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    response = payload.get("tool_response")
    stdout = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
    events, rolled = [], False
    for segment in _SEGMENT_SPLIT.split(command):
        match = _DM_TOOL.search(segment)
        if not match:
            continue
        tool, rest = match.group(1), match.group(2)
        if tool in _ROLL_TOOLS:
            lines = _DICE.findall(stdout)
            if lines and not rolled:
                rolled = True
                events.append({"kind": "roll", "text": " | ".join(line.strip() for line in lines[:3])[:MAX_TEXT]})
            continue
        event = describe(tool, rest, stdout, lang)
        if event:
            events.append(event)
    return events
