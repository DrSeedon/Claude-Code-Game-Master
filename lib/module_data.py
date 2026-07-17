#!/usr/bin/env python3
"""
Module Data Manager — universal per-campaign storage for module data.

Each module gets its own JSON file at:
  world-state/campaigns/<campaign>/module-data/<module-id>.json

Provides load/save + auto-migration from campaign-overview.json for modules
that previously stored config there.
"""

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
    scoped_campaign_name,
)
from lib.json_ops import JsonOperations


class ModuleDataManager:
    """Read/write module-specific data in per-campaign module-data/ directory."""

    def __init__(self, campaign_dir: Path):
        self.campaign_dir = Path(campaign_dir)
        self.data_dir = self.campaign_dir / "module-data"

    def _ensure_dir(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, module_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", module_id):
            raise ValueError(f"Invalid module id: {module_id!r}")
        return self.data_dir / f"{module_id}.json"

    def load(self, module_id: str) -> Dict:
        self.path_for(module_id)
        return JsonOperations(str(self.data_dir)).load_json(
            f"{module_id}.json", {}
        )

    def save(self, module_id: str, data: Dict) -> bool:
        self._ensure_dir()
        self.path_for(module_id)
        return JsonOperations(str(self.data_dir)).save_json(
            f"{module_id}.json", data
        )

    @contextmanager
    def transaction(self, module_id: str):
        self._ensure_dir()
        self.path_for(module_id)
        with JsonOperations(str(self.data_dir)).transaction(
            f"{module_id}.json"
        ) as data:
            yield data

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
        try:
            name = scoped_campaign_name(ws)
            if not name:
                return None
            campaign_dir = resolve_campaign_dir(
                ws / "campaigns", name, must_exist=True
            )
        except (InvalidCampaignName, FileNotFoundError):
            return None
        return cls(campaign_dir)
