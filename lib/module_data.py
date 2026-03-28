#!/usr/bin/env python3
"""
Module Data Manager — universal per-campaign storage for module data.

Each module gets its own JSON file at:
  world-state/campaigns/<campaign>/module-data/<module-id>.json

Provides load/save + auto-migration from campaign-overview.json for modules
that previously stored config there.
"""

import json
from pathlib import Path
from typing import Dict, Optional


class ModuleDataManager:
    """Read/write module-specific data in per-campaign module-data/ directory."""

    def __init__(self, campaign_dir: Path):
        self.campaign_dir = Path(campaign_dir)
        self.data_dir = self.campaign_dir / "module-data"

    def _ensure_dir(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, module_id: str) -> Path:
        return self.data_dir / f"{module_id}.json"

    def load(self, module_id: str) -> Dict:
        p = self.path_for(module_id)
        if not p.exists():
            return {}
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save(self, module_id: str, data: Dict) -> bool:
        self._ensure_dir()
        p = self.path_for(module_id)
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save module data '{module_id}': {e}")
            return False

    def exists(self, module_id: str) -> bool:
        return self.path_for(module_id).exists()

    def delete(self, module_id: str) -> bool:
        p = self.path_for(module_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def list_modules(self):
        if not self.data_dir.exists():
            return []
        return [f.stem for f in self.data_dir.glob("*.json")]

    @classmethod
    def from_world_state(cls, world_state_dir: str = "world-state") -> Optional["ModuleDataManager"]:
        ws = Path(world_state_dir)
        active_file = ws / "active-campaign.txt"
        if not active_file.exists():
            return None
        name = active_file.read_text().strip()
        if not name:
            return None
        campaign_dir = ws / "campaigns" / name
        if not campaign_dir.exists():
            return None
        return cls(campaign_dir)


