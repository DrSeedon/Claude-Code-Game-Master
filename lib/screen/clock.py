"""Live game time and place for the page header (the act only carries a label)."""

import json
from pathlib import Path

from lib import calendar as game_calendar


def world_clock(campaign_dir):
    """{'text': 'Weekday, date — HH:MM', 'location': name} from campaign-overview.json, or None."""
    path = Path(campaign_dir) / "campaign-overview.json"
    try:
        overview = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    raw_date, raw_time = overview.get("current_date", ""), overview.get("precise_time", "")
    try:
        config = game_calendar.load_config(campaign_dir)
        text = game_calendar.format_full(game_calendar.parse_date(raw_date, config), raw_time, config)
    except Exception:  # an unusual date string: show it as the Master wrote it
        text = f"{raw_date} — {raw_time}".strip(" —")
    return {"text": text, "location": (overview.get("player_position") or {}).get("current_location")}
