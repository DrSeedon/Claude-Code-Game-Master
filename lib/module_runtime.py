"""Runtime discovery and neutral dispatch for active gameplay modules."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional

from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
    scoped_campaign_name,
)


class ModuleRuntimeError(RuntimeError):
    """Raised when active module contracts are invalid or ambiguous."""


class ModuleRuntime:
    """Resolve capabilities, providers, and action routes for one campaign."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        campaign_dir: Optional[Path] = None,
        overview_path: Optional[Path] = None,
    ):
        self.project_root = Path(project_root or Path(__file__).parent.parent)
        self.modules_dir = self.project_root / "modules"
        self.campaign_dir = Path(campaign_dir) if campaign_dir else None
        self.overview_path = (
            Path(overview_path)
            if overview_path
            else self._resolve_overview_path()
        )
        self._provider_cache: dict[tuple[str, str], Callable[..., Any]] = {}

    def _resolve_overview_path(self) -> Optional[Path]:
        if self.campaign_dir:
            return self.campaign_dir / "campaign-overview.json"

        world_state = self.project_root / "world-state"
        try:
            campaign_name = scoped_campaign_name(world_state)
            if not campaign_name:
                return None
            campaign_dir = resolve_campaign_dir(
                world_state / "campaigns",
                campaign_name,
                must_exist=True,
            )
        except (InvalidCampaignName, FileNotFoundError):
            return None
        self.campaign_dir = campaign_dir
        return campaign_dir / "campaign-overview.json"

    def enabled_module_ids(self) -> list[str]:
        if not self.overview_path or not self.overview_path.exists():
            return []
        try:
            overview = json.loads(self.overview_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        configured = overview.get("modules", {})
        if isinstance(configured, dict):
            return sorted(
                module_id
                for module_id, enabled in configured.items()
                if enabled
            )
        if isinstance(configured, list):
            return sorted(dict.fromkeys(str(module_id) for module_id in configured))
        return []

    def active_manifests(self) -> list[tuple[str, dict[str, Any], Path]]:
        manifests = []
        for module_id in self.enabled_module_ids():
            module_dir = self.modules_dir / module_id
            manifest_path = module_dir / "module.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("id") != module_id:
                raise ModuleRuntimeError(
                    f"Module directory '{module_id}' has manifest id "
                    f"'{manifest.get('id')}'."
                )
            manifests.append((module_id, manifest, module_dir))
        return manifests

    def capabilities(self) -> set[str]:
        result: set[str] = set()
        for _, manifest, _ in self.active_manifests():
            provided = manifest.get("provides", [])
            if not isinstance(provided, list):
                raise ModuleRuntimeError("'provides' must be a list.")
            result.update(str(capability) for capability in provided)
            result.update(self._mapping(manifest, "providers"))
            result.update(self._mapping(manifest, "action_routes"))
        return result

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities()

    def _mapping(self, manifest: dict[str, Any], field: str) -> dict[str, str]:
        value = manifest.get(field, {})
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ModuleRuntimeError(f"'{field}' must be an object.")
        return {str(key): str(item) for key, item in value.items()}

    def _unique_contract(
        self,
        field: str,
        contract: str,
    ) -> Optional[tuple[str, str, Path]]:
        matches = []
        for module_id, manifest, module_dir in self.active_manifests():
            value = self._mapping(manifest, field).get(contract)
            if value:
                matches.append((module_id, value, module_dir))

        if len(matches) > 1:
            providers = ", ".join(module_id for module_id, _, _ in matches)
            raise ModuleRuntimeError(
                f"Active modules provide conflicting '{contract}' contracts: "
                f"{providers}."
            )
        return matches[0] if matches else None

    def action_route(self, action: str) -> Optional[str]:
        contract = self._unique_contract("action_routes", action)
        return contract[1] if contract else None

    def has_provider(self, capability: str) -> bool:
        return self._unique_contract("providers", capability) is not None

    def call_provider(
        self,
        capability: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        contract = self._unique_contract("providers", capability)
        if not contract:
            return None
        module_id, provider_spec, module_dir = contract
        provider = self._load_provider(module_id, provider_spec, module_dir)
        return provider(*args, **kwargs)

    def _load_provider(
        self,
        module_id: str,
        provider_spec: str,
        module_dir: Path,
    ) -> Callable[..., Any]:
        cache_key = (module_id, provider_spec)
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        try:
            relative_file, function_name = provider_spec.rsplit(":", 1)
        except ValueError as exc:
            raise ModuleRuntimeError(
                f"Invalid provider '{provider_spec}' in '{module_id}'."
            ) from exc

        module_root = module_dir.resolve()
        provider_path = (module_dir / relative_file).resolve()
        if not provider_path.is_relative_to(module_root):
            raise ModuleRuntimeError(
                f"Provider '{provider_spec}' escapes module '{module_id}'."
            )
        if not provider_path.is_file():
            raise ModuleRuntimeError(
                f"Provider file not found for '{module_id}': {relative_file}"
            )

        import_name = (
            f"_dm_module_{module_id.replace('-', '_')}_"
            f"{provider_path.stem}_{function_name}"
        )
        spec = importlib.util.spec_from_file_location(import_name, provider_path)
        if not spec or not spec.loader:
            raise ModuleRuntimeError(
                f"Cannot load provider '{provider_spec}' from '{module_id}'."
            )
        module: ModuleType = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        provider = getattr(module, function_name, None)
        if not callable(provider):
            raise ModuleRuntimeError(
                f"Provider '{provider_spec}' from '{module_id}' is not callable."
            )
        self._provider_cache[cache_key] = provider
        return provider
