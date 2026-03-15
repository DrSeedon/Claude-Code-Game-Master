#!/usr/bin/env python3
"""
Universal Currency System
Configurable per-campaign denominations with auto-change.
All values stored internally as smallest unit (base).
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

DEFAULT_CONFIG = {
    "base": "cp",
    "denominations": [
        {"id": "cp", "name": "медяк", "symbol": "c", "rate": 1},
        {"id": "sp", "name": "серебряк", "symbol": "s", "rate": 10},
        {"id": "gp", "name": "золотой", "symbol": "g", "rate": 100},
    ]
}


def load_config(campaign_path: Union[str, Path]) -> Dict:
    campaign_path = Path(campaign_path)
    overview_file = campaign_path / "campaign-overview.json"
    if overview_file.exists():
        try:
            with open(overview_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = data.get("currency")
            if cfg and "denominations" in cfg:
                denoms = cfg["denominations"]
                if all("id" in d and "rate" in d for d in denoms):
                    for d in denoms:
                        d.setdefault("symbol", d["id"])
                        d.setdefault("name", d["id"])
                    denoms.sort(key=lambda d: d["rate"])
                    return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG


def _sorted_denoms(config: Dict) -> List[Dict]:
    denoms = list(config["denominations"])
    denoms.sort(key=lambda d: d["rate"], reverse=True)
    return denoms


def format_money(amount: int, config: Optional[Dict] = None, *, compact: bool = True) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = _sorted_denoms(config)

    if len(denoms) == 1:
        d = denoms[0]
        return f"{amount} {d['symbol']}"

    remainder = amount
    parts = []
    for d in denoms:
        count = remainder // d["rate"]
        remainder = remainder % d["rate"]
        if count > 0 or not compact:
            parts.append(f"{count}{d['symbol']}")

    if not parts:
        smallest = denoms[-1]
        return f"0{smallest['symbol']}"

    return " ".join(parts)


def format_money_long(amount: int, config: Optional[Dict] = None) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = _sorted_denoms(config)

    if len(denoms) == 1:
        d = denoms[0]
        return f"{amount} {d['name']}"

    remainder = amount
    parts = []
    for d in denoms:
        count = remainder // d["rate"]
        remainder = remainder % d["rate"]
        if count > 0:
            parts.append(f"{count} {d['name']}")

    if not parts:
        smallest = denoms[-1]
        return f"0 {smallest['name']}"

    return ", ".join(parts)


def parse_money(value: str, config: Optional[Dict] = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = {d["id"]: d["rate"] for d in config["denominations"]}
    symbols = {d["symbol"]: d["rate"] for d in config["denominations"]}

    value = value.strip()

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return int(float(value))
    except ValueError:
        pass

    total = 0
    found = False
    pattern = r'([+-]?\d+)\s*([a-zA-Zа-яА-ЯёЁ₽$€¢£¥]+)'
    for match in re.finditer(pattern, value):
        num = int(match.group(1))
        unit = match.group(2).strip().lower()
        rate = denoms.get(unit) or symbols.get(unit)
        if rate is not None:
            total += num * rate
            found = True

    if not found:
        raise ValueError(f"Cannot parse money value: '{value}'")

    return total


def convert(amount: int, from_id: str, to_id: str, config: Optional[Dict] = None) -> float:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = {d["id"]: d["rate"] for d in config["denominations"]}
    if from_id not in denoms or to_id not in denoms:
        raise ValueError(f"Unknown denomination: {from_id} or {to_id}")

    base_amount = amount * denoms[from_id]
    return base_amount / denoms[to_id]


def migrate_gold(gold_value: Union[int, float], config: Optional[Dict] = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = {d["id"]: d["rate"] for d in config["denominations"]}
    gp_rate = denoms.get("gp", denoms.get("gold", 1))

    return int(gold_value * gp_rate)


def can_afford(current: int, cost: int) -> bool:
    return current >= cost


def make_change(amount: int, config: Optional[Dict] = None) -> Dict[str, int]:
    if config is None:
        config = DEFAULT_CONFIG

    denoms = _sorted_denoms(config)
    result = {}
    remainder = amount
    for d in denoms:
        count = remainder // d["rate"]
        remainder = remainder % d["rate"]
        result[d["id"]] = count
    return result


def format_delta(delta: int, config: Optional[Dict] = None) -> str:
    if config is None:
        config = DEFAULT_CONFIG

    sign = "+" if delta >= 0 else "-"
    formatted = format_money(abs(delta), config)
    return f"{sign}{formatted}"


def save_config(campaign_path: Union[str, Path], config: Dict):
    campaign_path = Path(campaign_path)
    overview_file = campaign_path / "campaign-overview.json"
    if not overview_file.exists():
        return

    with open(overview_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["currency"] = config

    with open(overview_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: currency.py <campaign_path> [format|parse|migrate] [args...]")
        sys.exit(1)

    campaign_path = Path(sys.argv[1])
    config = load_config(campaign_path)
    action = sys.argv[2] if len(sys.argv) > 2 else "info"

    if action == "info":
        print(f"Currency config:")
        print(f"  Base unit: {config['base']}")
        for d in config["denominations"]:
            print(f"  {d['id']} ({d['name']}): 1 = {d['rate']} {config['base']}, symbol: {d['symbol']}")

    elif action == "format":
        amount = int(sys.argv[3])
        print(format_money(amount, config))

    elif action == "parse":
        value = " ".join(sys.argv[3:])
        print(parse_money(value, config))

    elif action == "migrate":
        gold = float(sys.argv[3])
        print(migrate_gold(gold, config))

    elif action == "change":
        amount = int(sys.argv[3])
        breakdown = make_change(amount, config)
        for denom_id, count in breakdown.items():
            if count > 0:
                print(f"  {denom_id}: {count}")
