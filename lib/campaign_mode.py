#!/usr/bin/env python3
"""Persistent player-agency mode for the active campaign."""

import argparse
import json
from pathlib import Path
from typing import Optional

try:
    from .campaign_manager import CampaignManager
    from .json_ops import JsonOperations
except ImportError:
    from campaign_manager import CampaignManager
    from json_ops import JsonOperations


DEFAULT_MODE = "interactive"
MODE_ALIASES = {
    "interactive": "interactive",
    "dnd": "interactive",
    "manual": "interactive",
    "narrative": "narrative",
    "book": "narrative",
    "story": "narrative",
}


class CampaignModeManager:
    def __init__(self, world_state_dir: str = "world-state"):
        campaign_manager = CampaignManager(world_state_dir)
        self.campaign_dir = campaign_manager.get_active_campaign_dir()
        if not self.campaign_dir:
            raise RuntimeError("No active campaign.")
        self.overview_path = Path(self.campaign_dir) / "campaign-overview.json"
        self.json_ops = JsonOperations(str(self.campaign_dir))

    @staticmethod
    def normalize(mode: str) -> str:
        normalized = MODE_ALIASES.get(mode.strip().lower())
        if not normalized:
            valid = ", ".join(sorted(MODE_ALIASES))
            raise ValueError(f"Unknown play mode '{mode}'. Valid values: {valid}")
        return normalized

    def _load(self) -> dict:
        if not self.overview_path.exists():
            raise RuntimeError(f"Campaign overview not found: {self.overview_path}")
        with open(self.overview_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def get_mode(self) -> str:
        overview = self._load()
        raw_mode = overview.get("play_mode", DEFAULT_MODE)
        if isinstance(raw_mode, dict):
            raw_mode = raw_mode.get("id", DEFAULT_MODE)
        return MODE_ALIASES.get(str(raw_mode).lower(), DEFAULT_MODE)

    def set_mode(self, mode: str) -> str:
        normalized = self.normalize(mode)
        with self.json_ops.transaction("campaign-overview.json") as overview:
            overview["play_mode"] = normalized
        return normalized


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Get or set active campaign play mode")
    parser.add_argument(
        "mode",
        nargs="?",
        default="status",
        help="interactive|dnd|narrative|book|status",
    )
    args = parser.parse_args(argv)

    try:
        manager = CampaignModeManager()
        if args.mode.lower() == "status":
            print(f"Play mode: {manager.get_mode()}")
        else:
            print(f"Play mode set: {manager.set_mode(args.mode)}")
        return 0
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
