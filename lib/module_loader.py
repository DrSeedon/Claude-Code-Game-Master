#!/usr/bin/env python3
"""
Module Loader for DM System

Discovers, validates, and loads campaign modules.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ModuleLoader:
    """Load and manage DM System modules."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root
        self.modules_dir = self.project_root / ".claude" / "modules"
        self.registry_file = self.modules_dir / "registry.json"

    def scan_modules(self) -> Dict[str, Dict]:
        """
        Scan .claude/modules/ directory and build registry.

        Returns:
            Dict mapping module_id -> module metadata
        """
        if not self.modules_dir.exists():
            return {}

        modules = {}
        for module_dir in self.modules_dir.iterdir():
            if not module_dir.is_dir():
                continue

            module_json = module_dir / "module.json"
            if not module_json.exists():
                continue

            try:
                with open(module_json, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    module_id = metadata.get("id")
                    if module_id:
                        modules[module_id] = metadata
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[WARNING] Failed to load {module_dir.name}: {e}")
                continue

        return modules

    def update_registry(self) -> bool:
        """Scan modules and update registry.json."""
        modules = self.scan_modules()

        registry = {
            "version": "1.0.0",
            "last_updated": None,  # Could add timestamp
            "modules": modules
        }

        try:
            self.modules_dir.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write registry: {e}")
            return False

    def load_registry(self) -> Dict[str, Dict]:
        """Load module registry from disk."""
        if not self.registry_file.exists():
            # Auto-generate if missing
            self.update_registry()

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)
                return registry.get("modules", {})
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def list_modules(self, filter_status: Optional[str] = None) -> List[Dict]:
        """
        List available modules.

        Args:
            filter_status: Filter by _status field (e.g., "Active", "Planned")

        Returns:
            List of module metadata dicts
        """
        modules = self.load_registry()
        result = []

        for module_id, metadata in modules.items():
            if filter_status:
                status = metadata.get("_status", "Active")
                if filter_status.lower() not in status.lower():
                    continue
            result.append(metadata)

        return result

    def get_module(self, module_id: str) -> Optional[Dict]:
        """Get metadata for a specific module."""
        modules = self.load_registry()
        return modules.get(module_id)

    def check_dependencies(self, module_id: str, enabled_modules: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if module dependencies are satisfied.

        Args:
            module_id: Module to check
            enabled_modules: Currently enabled modules

        Returns:
            (dependencies_met, missing_dependencies)
        """
        module = self.get_module(module_id)
        if not module:
            return False, [f"Module '{module_id}' not found"]

        dependencies = module.get("dependencies", [])
        missing = [dep for dep in dependencies if dep not in enabled_modules]

        return len(missing) == 0, missing

    def validate_module(self, module_id: str) -> Tuple[bool, str]:
        """
        Validate module structure.

        Returns:
            (is_valid, error_message)
        """
        module = self.get_module(module_id)
        if not module:
            return False, f"Module '{module_id}' not found in registry"

        required_fields = ["id", "name", "version", "description"]
        for field in required_fields:
            if field not in module:
                return False, f"Missing required field: {field}"

        return True, ""


def main():
    """CLI for module management."""
    import argparse

    parser = argparse.ArgumentParser(description="DM System Module Loader")
    parser.add_argument("action", choices=["scan", "list", "info", "validate"],
                        help="Action to perform")
    parser.add_argument("--module", help="Module ID (for info/validate)")
    parser.add_argument("--filter", help="Filter modules by status")

    args = parser.parse_args()
    loader = ModuleLoader()

    if args.action == "scan":
        print("Scanning modules...")
        if loader.update_registry():
            modules = loader.load_registry()
            print(f"[SUCCESS] Found {len(modules)} modules")
            for module_id, metadata in modules.items():
                status = metadata.get("_status", "Active")
                print(f"  • {module_id} — {metadata['name']} ({status})")
        else:
            print("[ERROR] Failed to update registry")

    elif args.action == "list":
        modules = loader.list_modules(filter_status=args.filter)
        if not modules:
            print("No modules found")
        else:
            print(f"Available modules ({len(modules)}):\n")
            for module in modules:
                module_id = module["id"]
                name = module["name"]
                status = module.get("_status", "Active")
                desc = module["description"]
                print(f"  {module_id}")
                print(f"    Name: {name}")
                print(f"    Status: {status}")
                print(f"    Description: {desc}")
                print()

    elif args.action == "info":
        if not args.module:
            print("[ERROR] --module required for 'info' action")
            return

        module = loader.get_module(args.module)
        if not module:
            print(f"[ERROR] Module '{args.module}' not found")
            return

        print(json.dumps(module, indent=2, ensure_ascii=False))

    elif args.action == "validate":
        if not args.module:
            print("[ERROR] --module required for 'validate' action")
            return

        is_valid, error = loader.validate_module(args.module)
        if is_valid:
            print(f"[SUCCESS] Module '{args.module}' is valid")
        else:
            print(f"[ERROR] {error}")


if __name__ == "__main__":
    main()
