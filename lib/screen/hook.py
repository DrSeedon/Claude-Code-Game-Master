"""PostToolUse hook: turn the Master's tool calls into activity events for the live feed."""

import re

_DM_TOOL = re.compile(r"(?:^|[\s;&|])(?:bash\s+)?(?:\./)?(?:modules/[\w-]+/)?tools/(dm-[\w-]+)\.sh\b(.*)")
_DICE = re.compile(r"🎲[^\n]*")
_ROLL_TOOLS = {"dm-roll", "dm-mass-combat"}
_QUIET = {"dm-screen", "dm-search", "dm-overview", "dm-status"}
MAX_TEXT = 300


def activity_from_hook(payload):
    """Return {'kind', 'text'} for a Master tool call worth showing, otherwise None."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    match = _DM_TOOL.search(command)
    if not match:
        return None
    tool, rest = match.group(1), match.group(2)
    if tool in _QUIET:
        return None
    response = payload.get("tool_response")
    stdout = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
    if tool in _ROLL_TOOLS:
        lines = _DICE.findall(stdout)
        if lines:
            return {"kind": "roll", "text": " | ".join(line.strip() for line in lines[:3])[:MAX_TEXT]}
    summary = f"{tool}.sh{rest}".strip()
    return {"kind": "save", "text": " ".join(summary.split())[:MAX_TEXT]}
