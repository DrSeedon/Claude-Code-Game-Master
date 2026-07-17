#!/usr/bin/env python3
"""
JSON operations module for DM tools
Provides safe JSON read/write/update operations with proper error handling
"""

import json
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone


class JsonOperations:
    """Safe JSON file operations for world state management"""

    def __init__(self, world_state_dir: str = "world-state"):
        self.world_state_dir = Path(world_state_dir)
        self.world_state_dir.mkdir(parents=True, exist_ok=True)

    def load_json(self, filename: str, default: Any = None) -> Any:
        """
        Load JSON file with error handling
        Returns default value if file doesn't exist or is invalid
        """
        filepath = self._resolve_path(filename)

        if not filepath.exists():
            if default is None:
                default = {}
            return default

        try:
            with self._lock(filepath, exclusive=False):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON in {filename}: {e}")
            return default if default is not None else {}
        except Exception as e:
            print(f"[ERROR] Failed to read {filename}: {e}")
            return default if default is not None else {}

    def save_json(self, filename: str, data: Any, indent: int = 2) -> bool:
        """
        Save data to JSON file with atomic write
        Returns True on success, False on failure
        """
        filepath = self._resolve_path(filename)

        try:
            with self._lock(filepath, exclusive=True):
                self._write_unlocked(filepath, data, indent)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save {filename}: {e}")
            return False

    @contextmanager
    def transaction(self, filename: str, default: Any = None, indent: int = 2):
        """Lock, load, mutate, and atomically commit one JSON document."""
        filepath = self._resolve_path(filename)
        with self._lock(filepath, exclusive=True):
            if filepath.exists():
                with filepath.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            else:
                data = {} if default is None else default
            original = json.dumps(data, sort_keys=True, ensure_ascii=False)
            yield data
            if json.dumps(data, sort_keys=True, ensure_ascii=False) != original:
                self._write_unlocked(filepath, data, indent)

    def update_json(self, filename: str, updates: Dict, path: List[str] = None) -> bool:
        """
        Update JSON file with partial data
        If path is provided, updates nested structure at that path
        """
        try:
            with self.transaction(filename) as data:
                if path:
                    current = data
                    for key in path[:-1]:
                        if key not in current:
                            current[key] = {}
                        current = current[key]

                    if isinstance(updates, dict) and isinstance(current.get(path[-1]), dict):
                        current[path[-1]].update(updates)
                    else:
                        current[path[-1]] = updates
                elif isinstance(data, dict) and isinstance(updates, dict):
                    data.update(updates)
                else:
                    raise TypeError("Root JSON update requires object values")
            return True
        except Exception as exc:
            print(f"[ERROR] Failed to update {filename}: {exc}")
            return False

    def append_to_list(self, filename: str, item: Any, path: List[str] = None) -> bool:
        """
        Append item to a list in JSON file
        If path is provided, appends to list at that path
        """
        try:
            with self.transaction(filename, default=[] if not path else {}) as data:
                if path:
                    current = data
                    for key in path[:-1]:
                        current = current.setdefault(key, {})
                    target = current.setdefault(path[-1], [])
                else:
                    target = data
                if not isinstance(target, list):
                    raise TypeError("Target is not a list")
                target.append(item)
            return True
        except Exception as exc:
            print(f"[ERROR] Failed to append to {filename}: {exc}")
            return False

    def check_exists(self, filename: str, key: str, path: List[str] = None) -> bool:
        """
        Check if a key exists in JSON file
        If path is provided, checks at that nested path
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for p in path:
                if not isinstance(current, dict) or p not in current:
                    return False
                current = current[p]

            return isinstance(current, dict) and key in current
        else:
            return isinstance(data, dict) and key in data

    def get_value(self, filename: str, key: str = None, path: List[str] = None) -> Any:
        """
        Get value from JSON file
        If path is provided, gets value at that nested path
        If key is provided, gets that specific key
        """
        data = self.load_json(filename)

        if path:
            # Navigate to nested path
            current = data
            for p in path:
                if not isinstance(current, dict) or p not in current:
                    return None
                current = current[p]
            data = current

        if key:
            if isinstance(data, dict):
                return data.get(key)
            return None

        return data

    def delete_key(self, filename: str, key: str, path: List[str] = None) -> bool:
        """
        Delete a key from JSON file
        If path is provided, deletes from that nested path
        """
        try:
            with self.transaction(filename) as data:
                current = data
                if path:
                    for part in path:
                        if not isinstance(current, dict) or part not in current:
                            return False
                        current = current[part]
                if not isinstance(current, dict) or key not in current:
                    return False
                del current[key]
            return True
        except Exception as exc:
            print(f"[ERROR] Failed to delete from {filename}: {exc}")
            return False

    @contextmanager
    def _lock(self, filepath: Path, exclusive: bool):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        lock_path = filepath.with_name(f".{filepath.name}.lock")
        with lock_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _write_unlocked(filepath: Path, data: Any, indent: int) -> None:
        fd, temporary = tempfile.mkstemp(
            prefix=f".{filepath.name}.",
            suffix=".tmp",
            dir=filepath.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=indent, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, filepath)
            directory_fd = os.open(filepath.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def _resolve_path(self, filename: str) -> Path:
        """Resolve file path relative to world state directory"""
        if os.path.isabs(filename):
            return Path(filename)
        return self.world_state_dir / filename

    @staticmethod
    def get_timestamp() -> str:
        """Get ISO format timestamp"""
        return datetime.now(timezone.utc).isoformat()


# Convenience functions for command-line usage
def main():
    """CLI interface for JSON operations"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='JSON file operations')
    parser.add_argument('action', choices=['get', 'set', 'update', 'append', 'exists', 'delete'])
    parser.add_argument('filename', help='JSON file name')
    parser.add_argument('--key', help='Key to operate on')
    parser.add_argument('--value', help='Value to set (JSON string)')
    parser.add_argument('--path', help='Nested path (dot-separated)')
    parser.add_argument('--world-state-dir', default='world-state', help='World state directory')

    args = parser.parse_args()

    ops = JsonOperations(args.world_state_dir)
    path = args.path.split('.') if args.path else None

    if args.action == 'get':
        result = ops.get_value(args.filename, args.key, path)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.action == 'set' or args.action == 'update':
        if not args.value:
            print("[ERROR] --value required for set/update")
            sys.exit(1)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value  # Treat as string if not valid JSON

        if args.key:
            updates = {args.key: value}
        else:
            updates = value

        if ops.update_json(args.filename, updates, path):
            print("[SUCCESS] Updated")
        else:
            sys.exit(1)

    elif args.action == 'append':
        if not args.value:
            print("[ERROR] --value required for append")
            sys.exit(1)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value

        if ops.append_to_list(args.filename, value, path):
            print("[SUCCESS] Appended")
        else:
            sys.exit(1)

    elif args.action == 'exists':
        if not args.key:
            print("[ERROR] --key required for exists check")
            sys.exit(1)
        exists = ops.check_exists(args.filename, args.key, path)
        print("true" if exists else "false")
        sys.exit(0 if exists else 1)

    elif args.action == 'delete':
        if not args.key:
            print("[ERROR] --key required for delete")
            sys.exit(1)
        if ops.delete_key(args.filename, args.key, path):
            print("[SUCCESS] Deleted")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
