"""Damage profile exported by the firearms combat module."""

from __future__ import annotations

from typing import Any


def normalize_profile(entity: dict[str, Any]) -> dict[str, int]:
    """Extract this provider's fields from a WorldGraph entity or profile."""
    profile = entity.get("combat_profile", entity)
    if not isinstance(profile, dict):
        return {}
    normalized = {}
    if "pen" in profile:
        normalized["pen"] = int(profile["pen"])
    if "prot" in profile:
        normalized["prot"] = int(profile["prot"])
    return normalized


def describe_profile(entity: dict[str, Any]) -> str:
    """Return a compact provider-owned status label."""
    profile = normalize_profile(entity)
    pen = profile.get("pen", 0)
    prot = profile.get("prot", 0)
    return f"PEN{pen}/PROT{prot}" if pen or prot else ""


def resolve_damage(
    raw_damage: int,
    attacker: dict[str, Any],
    defender: dict[str, Any],
) -> dict[str, Any]:
    """Apply penetration/protection scaling to one successful hit."""
    damage = max(0, int(raw_damage))
    pen = normalize_profile(attacker).get("pen", 0)
    prot = normalize_profile(defender).get("prot", 0)

    if pen == 0 and prot == 0:
        return {"damage": damage, "details": ""}
    if pen > prot:
        scale = "FULL"
        resolved = max(1, damage)
    elif pen > prot / 2:
        scale = "HALF"
        resolved = max(1, damage // 2)
    else:
        scale = "QUARTER"
        resolved = max(1, damage // 4)
    return {
        "damage": resolved,
        "details": f"PEN{pen}/PROT{prot}[{scale}]",
    }
