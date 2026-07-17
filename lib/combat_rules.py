"""Shared combat-stat normalization and armor penetration rules."""

from typing import Any, Mapping


def first_present(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first explicitly present value, including zero."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def node_mechanics(node: Mapping[str, Any]) -> dict:
    """Return mechanics from either canonical data or legacy nested mechanics."""
    data = node.get("data", {})
    if not isinstance(data, dict):
        return {}
    nested = data.get("mechanics")
    return nested if isinstance(nested, dict) else data


def penetration_damage(raw_damage: int, pen: int = 0, prot: int = 0) -> tuple[int, str]:
    """Scale positive damage by PEN/PROT and keep successful hits meaningful."""
    raw_damage = max(0, int(raw_damage))
    pen = int(pen or 0)
    prot = int(prot or 0)
    if raw_damage == 0:
        return 0, "NONE"
    if pen > prot or (pen == 0 and prot == 0):
        return raw_damage, "FULL"
    if pen <= prot / 2:
        return max(1, raw_damage // 4), "QUARTER"
    return max(1, raw_damage // 2), "HALF"
