#!/usr/bin/env python3
"""
Universal Calendar System
Configurable per-campaign calendars with auto-advance.
Date stored as {day, month_index, year}. Config in campaign-overview.json.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, Union

DEFAULT_CONFIG = {
    "epoch": "AD",
    "months": [
        {"id": "january", "name": "January", "days": 31},
        {"id": "february", "name": "February", "days": 28},
        {"id": "march", "name": "March", "days": 31},
        {"id": "april", "name": "April", "days": 30},
        {"id": "may", "name": "May", "days": 31},
        {"id": "june", "name": "June", "days": 30},
        {"id": "july", "name": "July", "days": 31},
        {"id": "august", "name": "August", "days": 31},
        {"id": "september", "name": "September", "days": 30},
        {"id": "october", "name": "October", "days": 31},
        {"id": "november", "name": "November", "days": 30},
        {"id": "december", "name": "December", "days": 31},
    ],
    "weekdays": [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ],
    "year_zero_weekday": 0,
}


def load_config(campaign_path: Union[str, Path]) -> Dict:
    campaign_path = Path(campaign_path)
    overview_file = campaign_path / "campaign-overview.json"
    if overview_file.exists():
        try:
            with open(overview_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = data.get("calendar")
            if cfg and "months" in cfg:
                months = cfg["months"]
                if all("name" in m and "days" in m for m in months):
                    for m in months:
                        m.setdefault("id", m["name"].lower())
                    return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG


def days_in_year(config: Dict) -> int:
    return sum(m["days"] for m in config["months"])


def parse_date(date_str: str, config: Optional[Dict] = None) -> Dict:
    if config is None:
        config = DEFAULT_CONFIG

    date_str = date_str.strip()
    months = config["months"]
    epoch = config.get("epoch", "")

    month_names = {m["name"].lower(): i for i, m in enumerate(months)}
    month_ids = {m["id"].lower(): i for i, m in enumerate(months)}

    epoch_clean = re.escape(epoch) if epoch else ""
    pattern = rf'(\d+)\s+(\w+)[,]?\s*(\d+)\s*{epoch_clean}?'
    m = re.match(pattern, date_str, re.IGNORECASE)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = int(m.group(3))

        month_idx = month_names.get(month_str) or month_ids.get(month_str)
        if month_idx is None:
            for name, idx in month_names.items():
                if name.startswith(month_str) or month_str.startswith(name[:4]):
                    month_idx = idx
                    break

        if month_idx is None:
            raise ValueError(f"Unknown month: '{m.group(2)}' in '{date_str}'")

        return {"day": day, "month": month_idx, "year": year}

    raise ValueError(f"Cannot parse date: '{date_str}'")


def format_date(date: Dict, config: Optional[Dict] = None) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    months = config["months"]
    epoch = config.get("epoch", "")
    month_name = months[date["month"]]["name"]
    epoch_str = f" {epoch}" if epoch else ""
    return f"{date['day']} {month_name}, {date['year']}{epoch_str}"


def weekday(date: Dict, config: Optional[Dict] = None) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    weekdays = config.get("weekdays", [])
    if not weekdays:
        return ""

    total_days = _absolute_day(date, config)
    y0_wd = config.get("year_zero_weekday", 0)
    idx = (total_days + y0_wd) % len(weekdays)
    return weekdays[idx]


def _absolute_day(date: Dict, config: Dict) -> int:
    dy = days_in_year(config)
    months = config["months"]
    total = date["year"] * dy
    for i in range(date["month"]):
        total += months[i]["days"]
    total += date["day"] - 1
    return total


def advance_days(date: Dict, days: int, config: Optional[Dict] = None) -> Dict:
    if config is None:
        config = DEFAULT_CONFIG

    months = config["months"]
    d = date["day"]
    m = date["month"]
    y = date["year"]

    remaining = days
    while remaining > 0:
        days_left_in_month = months[m]["days"] - d
        if remaining <= days_left_in_month:
            d += remaining
            remaining = 0
        else:
            remaining -= (days_left_in_month + 1)
            m += 1
            d = 1
            if m >= len(months):
                m = 0
                y += 1

    while remaining < 0:
        if d + remaining >= 1:
            d += remaining
            remaining = 0
        else:
            remaining += d
            m -= 1
            if m < 0:
                m = len(months) - 1
                y -= 1
            d = months[m]["days"]

    return {"day": d, "month": m, "year": y}


def advance_hours(date: Dict, clock: str, hours: float,
                  config: Optional[Dict] = None) -> tuple:
    if config is None:
        config = DEFAULT_CONFIG

    h, m = map(int, clock.split(":"))
    total_min = h * 60 + m + int(hours * 60)

    days_passed = total_min // (24 * 60)
    leftover_min = total_min % (24 * 60)
    if leftover_min < 0:
        leftover_min += 24 * 60
        days_passed -= 1

    new_h = leftover_min // 60
    new_m = leftover_min % 60
    new_clock = f"{new_h:02d}:{new_m:02d}"

    new_date = advance_days(date, days_passed, config) if days_passed != 0 else dict(date)
    return new_date, new_clock


def days_between(date1: Dict, date2: Dict, config: Optional[Dict] = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG
    return _absolute_day(date2, config) - _absolute_day(date1, config)


def format_full(date: Dict, clock: str, config: Optional[Dict] = None) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    date_str = format_date(date, config)
    wd = weekday(date, config)
    wd_str = f"{wd}, " if wd else ""
    return f"{wd_str}{date_str} — {clock}"


def save_config(campaign_path: Union[str, Path], config: Dict):
    campaign_path = Path(campaign_path)
    overview_file = campaign_path / "campaign-overview.json"
    if not overview_file.exists():
        return

    with open(overview_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["calendar"] = config

    with open(overview_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: calendar.py <campaign_path> [info|parse|format|advance|weekday] [args...]")
        sys.exit(1)

    campaign_path = Path(sys.argv[1])
    config = load_config(campaign_path)
    action = sys.argv[2] if len(sys.argv) > 2 else "info"

    if action == "info":
        print(f"Calendar: {config.get('epoch', 'none')}")
        print(f"  Year: {days_in_year(config)} days")
        for m in config["months"]:
            print(f"  {m['name']}: {m['days']} days")
        if config.get("weekdays"):
            print(f"  Week: {', '.join(config['weekdays'])}")

    elif action == "parse":
        date_str = " ".join(sys.argv[3:])
        d = parse_date(date_str, config)
        print(json.dumps(d))

    elif action == "format":
        d = json.loads(sys.argv[3])
        print(format_date(d, config))

    elif action == "advance":
        date_str = " ".join(sys.argv[3:-1])
        days_n = int(sys.argv[-1])
        d = parse_date(date_str, config)
        new_d = advance_days(d, days_n, config)
        print(format_date(new_d, config))

    elif action == "weekday":
        date_str = " ".join(sys.argv[3:])
        d = parse_date(date_str, config)
        print(weekday(d, config))
