"""PostToolUse hook: turn the Master's tool calls into short, spoiler-free lines for the live feed.

The feed never shows secret NPC descriptions or hidden machinery (consequences, notes, world edits).
Player-facing mechanical saves (HP, conditions, gold, XP, inventory) show concrete details.
"""

import re
import shlex

_DM_TOOL = re.compile(r"(?:^|[\s;&|])(?:bash\s+)?(?:\./)?(?:modules/[\w-]+/)?tools/(dm-[\w-]+)\.sh\b(.*)")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_DICE = re.compile(r"🎲[^\n]*")
_ELAPSED = re.compile(r"\(\+([\d.]+)h\)")
_NPC_HP_OUT = re.compile(r"✓\s*(.+?)\s+HP:\s*(\d+\s*→\s*\d+/\d+)")
_INT_ARG = re.compile(r"^[+-]?\d+$")
_ROLL_TOOLS = {"dm-roll", "dm-mass-combat"}
MAX_TEXT = 300

_COND_RU = {
    "poisoned": "Отравлен",
    "charmed": "Очарован",
    "frightened": "Испуган",
    "prone": "Сбит с ног",
    "stunned": "Оглушён",
    "paralyzed": "Парализован",
    "blinded": "Ослеплён",
    "deafened": "Оглох",
    "invisible": "Невидим",
    "exhaustion": "Истощение",
    "exhausted": "Истощён",
    "unconscious": "Без сознания",
    "restrained": "Опутан",
    "grappled": "Схвачен",
    "incapacitated": "Недееспособен",
    "petrified": "Окаменел",
    "blessed": "Благословлён",
    "cursed": "Проклят",
    "drunk": "Пьян",
    "intoxicated": "Опьянён",
    "burning": "Горит",
    "bleeding": "Кровотечение",
}

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


def _signed(val):
    s = str(val).strip()
    if not s:
        return ""
    if s[0] in "+-":
        return s
    return f"+{s}"


def _cond_name(cond, lang):
    if lang == "ru":
        return _COND_RU.get(cond.strip().lower(), cond.strip())
    return cond.strip()


def _player_delta(words):
    """Extract (who, signed_delta) from dm-player hp/hp-max/xp/gold words."""
    if len(words) < 2:
        return None, None
    sub = words[0]
    if sub == "hp" and len(words) >= 3 and words[1] in ("heal", "damage"):
        sign = "+" if words[1] == "heal" else "-"
        return None, f"{sign}{words[2].lstrip('+-')}"
    if _INT_ARG.match(words[1]) and len(words) == 2:
        return None, _signed(words[1])
    if len(words) >= 3 and _INT_ARG.match(words[2]):
        return words[1], _signed(words[2])
    return None, None


def _save_detail(tool, words, stdout, lang):
    """Concrete player-facing suffix for save events (conditions, HP, gold, XP, inventory)."""
    sub = words[0] if words else None
    ru = lang == "ru"

    if tool == "dm-player" and sub == "condition":
        if len(words) < 4 or words[2] not in ("add", "remove"):
            return ""
        who, act, cond = words[1], words[2], _cond_name(words[3], lang)
        if act == "add":
            return f": {who} — +{cond}" if ru else f": {who} +{cond}"
        return f": {who} — снято «{cond}»" if ru else f": {who} −{cond}"

    if tool == "dm-condition" and sub in ("add", "remove"):
        if len(words) < 3:
            return ""
        act, who, cond = sub, words[1], _cond_name(words[2], lang)
        if act == "add":
            return f": {who} — +{cond}" if ru else f": {who} +{cond}"
        return f": {who} — снято «{cond}»" if ru else f": {who} −{cond}"

    if tool == "dm-player" and sub in ("hp", "hp-max"):
        who, delta = _player_delta(words)
        if not delta:
            return ""
        prefix = f"{who} " if who else ""
        if sub == "hp-max":
            return f": {prefix}{'макс. ' if ru else 'max '}{delta} HP"
        return f": {prefix}{delta} HP"

    if tool == "dm-npc" and sub == "hp":
        who = words[1] if len(words) > 1 else ""
        delta = _signed(words[2]) if len(words) > 2 and _INT_ARG.match(words[2]) else ""
        m = _NPC_HP_OUT.search(stdout or "")
        if m:
            name, trans = m.group(1).strip(), m.group(2).strip()
            return f": {name} {delta + ' HP ' if delta else ''}({trans})"
        if who and delta:
            return f": {who} {delta} HP"
        return f": {who}" if who else ""

    if tool == "dm-player" and sub == "xp":
        who, delta = _player_delta(words)
        if not delta:
            return ""
        return f": {who + ' ' if who else ''}{delta} XP"

    if tool == "dm-player" and sub == "gold":
        who, delta = _player_delta(words)
        if not delta:
            return ""
        return f": {who + ' ' if who else ''}{delta}"

    if tool == "dm-inventory":
        owner = words[1] if len(words) > 1 and words[1] != "_auto" else ""
        if sub == "remove" and len(words) >= 3:
            item = words[2]
            qty = "1"
            for i in range(3, len(words) - 1):
                if words[i] == "--qty":
                    qty = words[i + 1]
            q_str = f" ×{qty}" if qty != "1" else ""
            return f": {owner + ' ' if owner else ''}−{item}{q_str}"
        if sub == "use" and len(words) >= 3:
            item = words[2]
            return f": {owner + ' — ' if owner else ''}{'использовано' if ru else 'used'} «{item}»"
        if sub == "transfer" and len(words) >= 2:
            target = owner
            src, item, qty = "", "", "1"
            i = 2
            while i < len(words):
                if words[i] == "--from" and i + 1 < len(words):
                    src = words[i + 1]
                    i += 2
                elif words[i] == "--item" and i + 1 < len(words):
                    item = words[i + 1]
                    i += 2
                elif words[i] == "--qty" and i + 1 < len(words):
                    qty = words[i + 1]
                    i += 2
                else:
                    i += 1
            q_str = f" ×{qty}" if qty != "1" else ""
            arrow = f"{src} → {target}" if src and target else (target or src)
            if item and arrow:
                return f": {arrow} ({item}{q_str})"
            if item:
                return f": {item}{q_str}"
        if sub in ("update", "loot"):
            parts = []
            i = 2
            while i < len(words):
                w = words[i]
                if w == "--add" and i + 1 < len(words):
                    iname = words[i + 1]
                    iqty = words[i + 2] if i + 2 < len(words) and not words[i + 2].startswith("--") else "1"
                    q_str = f" ×{iqty}" if iqty not in ("1", "") else ""
                    parts.append(f"+{iname}{q_str}")
                    i += 4
                elif w == "--items" and i + 1 < len(words):
                    for entry in words[i + 1].split(","):
                        seg = entry.split(":")
                        if seg and seg[0]:
                            iqty = seg[1] if len(seg) > 1 else "1"
                            q_str = f" ×{iqty}" if iqty not in ("1", "") else ""
                            parts.append(f"+{seg[0]}{q_str}")
                    i += 2
                elif w == "--gold" and i + 1 < len(words):
                    g = _signed(words[i + 1])
                    parts.append(f"{'золото' if ru else 'gold'} {g}")
                    i += 2
                elif w == "--xp" and i + 1 < len(words):
                    parts.append(f"{_signed(words[i + 1])} XP")
                    i += 2
                elif w == "--hp" and i + 1 < len(words):
                    parts.append(f"{_signed(words[i + 1])} HP")
                    i += 2
                else:
                    i += 1
            if parts:
                joined = ", ".join(parts)
                return f": {owner} ({joined})" if owner else f": {joined}"
            if owner:
                return f": {owner}"
    return ""


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
    clean_out = _ANSI.sub("", stdout or "").strip()
    if clean_out.startswith(("Usage:", "Error:")):
        return None
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
    if tool == "dm-player" and sub in ("gold", "hp", "hp-max", "xp"):
        _, delta = _player_delta(words)
        if not delta:
            return None  # a bare "gold" / "hp" or "gold <name>" only shows the value, nothing changed
    if tool == "dm-player" and sub == "condition":
        if len(words) < 4 or words[2] not in ("add", "remove"):
            return None  # "condition <name> list" only shows conditions
    if tool == "dm-condition" and (len(words) < 3 or sub not in ("add", "remove")):
        return None
    kind, message = rule
    texts = MESSAGES.get(lang, MESSAGES["en"])
    text = texts[message].format(amount=_amount(clean_out, texts) if message == "time" else "")
    if kind == "save":
        text += _save_detail(tool, words, clean_out, lang)
    return {"kind": kind, "text": text[:MAX_TEXT]}


_SEGMENT_SPLIT = re.compile(r"\s*(?:;|&&|\|\||\n)\s*")


def activities_from_hook(payload, lang="en"):
    """All feed lines for one Bash call: a chained command (a; b && c) yields one line per Master tool."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return []
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    response = payload.get("tool_response")
    stdout = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
    clean_stdout = _ANSI.sub("", stdout)
    events, rolled = [], False
    for segment in _SEGMENT_SPLIT.split(command):
        match = _DM_TOOL.search(segment)
        if not match:
            continue
        tool, rest = match.group(1), match.group(2)
        if tool in _ROLL_TOOLS:
            lines = _DICE.findall(clean_stdout)
            if lines and not rolled:
                rolled = True
                events.append({"kind": "roll", "text": " | ".join(line.strip() for line in lines[:3])[:MAX_TEXT]})
            continue
        event = describe(tool, rest, clean_stdout, lang)
        if event:
            events.append(event)
    return events


_SCENE_MOVE = re.compile(r"tools/dm-scene\.sh\b|tools/dm-session\.sh\s+move\b")
_ACT_SET = re.compile(r"tools/dm-screen\.sh\s+act\b")


def act_nudge(payload, act, online):
    """A reminder for the Master when it moved the scene but left the act (header and picture) where it was: the
    rule alone was not enough (playtest 2026-10-27: two moves to new places, no new act). None otherwise."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not _SCENE_MOVE.search(command) or _ACT_SET.search(command):
        return None
    act = act if isinstance(act, dict) else {}
    art = ('order its picture with `bash tools/dm-art.sh --prompt "<English scene description>"` (one to five minutes), '
           if online else "generate its key art (the html-screen rule), ")
    return (f"Screen: the scene moved, but the act on the screen still shows the place {act.get('place') or '(none)'!r} "
            f"under the title {act.get('title') or '(none)'!r}. If the story now stays somewhere else, start a new act "
            f"before you publish this turn: {art}then `bash tools/dm-screen.sh act --image <png> --title \"...\" "
            f"--kicker \"...\" --place \"...\" --date \"...\"`. A short stop in the same place keeps the act.")

