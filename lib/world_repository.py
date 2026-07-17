"""Transactional persistence for a campaign's ``world.json`` file."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


class ConcurrentWriteError(RuntimeError):
    """Raised when a stale world snapshot attempts to replace newer state."""


class WorldRepository:
    """Load and atomically commit the authoritative world state.

    The lock file is stable across ``os.replace`` calls, unlike locking
    ``world.json`` itself. All writers in this project therefore coordinate on
    the same inode while readers continue to see only complete JSON files.
    """

    def __init__(self, world_file: Path, empty_factory: Callable[[], dict]):
        self.world_file = Path(world_file)
        self.lock_file = self.world_file.with_name(f".{self.world_file.name}.lock")
        self._empty_factory = empty_factory

    @staticmethod
    def revision(data: dict) -> int:
        value = data.get("meta", {}).get("revision", 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _read_unlocked(self) -> dict:
        if not self.world_file.exists():
            data = self._empty_factory()
        else:
            with self.world_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        data.setdefault("meta", {}).setdefault("revision", 0)
        return data

    @contextmanager
    def _lock(self, exclusive: bool) -> Iterator[None]:
        self.world_file.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_file.open("a", encoding="utf-8") as handle:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(handle.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def load(self) -> dict:
        with self._lock(exclusive=False):
            return self._read_unlocked()

    def _write_unlocked(self, data: dict, base_revision: int) -> None:
        data.setdefault("meta", {})["revision"] = base_revision + 1
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.world_file.name}.",
            suffix=".tmp",
            dir=self.world_file.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.world_file)
            directory_fd = os.open(self.world_file.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def save(self, data: dict, expected_revision: int | None = None) -> bool:
        if expected_revision is None:
            expected_revision = self.revision(data)
        with self._lock(exclusive=True):
            current = self._read_unlocked()
            current_revision = self.revision(current)
            if current_revision != expected_revision:
                raise ConcurrentWriteError(
                    f"world state changed: expected revision {expected_revision}, "
                    f"found {current_revision}"
                )
            self._write_unlocked(data, current_revision)
        return True

    def initialize(self) -> bool:
        """Create the world file once without replacing existing state."""
        with self._lock(exclusive=True):
            if self.world_file.exists():
                return False
            self._write_unlocked(self._empty_factory(), 0)
        return True

    def replace(self, data: dict) -> bool:
        """Administratively replace state while preserving revision ordering."""
        with self._lock(exclusive=True):
            current_revision = self.revision(self._read_unlocked())
            self._write_unlocked(data, current_revision)
        return True

    @contextmanager
    def transaction(self) -> Iterator[dict]:
        """Yield one mutable snapshot and commit it once on successful exit."""
        with self._lock(exclusive=True):
            data = self._read_unlocked()
            original = copy.deepcopy(data)
            base_revision = self.revision(data)
            yield data
            if data != original:
                self._write_unlocked(data, base_revision)
