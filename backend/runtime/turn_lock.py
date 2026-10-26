"""One master turn per campaign across processes: the web game session and the online screen driver."""

from __future__ import annotations

import asyncio
import fcntl
from contextlib import contextmanager
from pathlib import Path

TURN_LOCK_FILENAME = ".turn.lock"


class TurnLockBusy(RuntimeError):
    """Another process runs a turn of this campaign."""


class CampaignTurnLock:
    """fcntl.flock on <campaign>/.turn.lock; each instance is its own open file, so two instances exclude each other."""

    def __init__(self, campaign_dir: Path) -> None:
        self.path = Path(campaign_dir) / TURN_LOCK_FILENAME
        self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self, blocking: bool = True) -> bool:
        if self._handle is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            handle.close()
            return False
        except BaseException:
            handle.close()
            raise
        self._handle = handle
        return True

    async def acquire_async(self, poll: float = 0.5) -> None:
        """Blocking for the caller, cancellable for asyncio (no thread left waiting on flock)."""
        while not self.acquire(blocking=False):
            await asyncio.sleep(poll)

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            finally:
                handle.close()

    def __enter__(self) -> "CampaignTurnLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextmanager
def campaign_turn_lock(campaign_dir: Path, blocking: bool = True):
    """Hold the campaign's turn lock for the block; TurnLockBusy when `blocking` is False and it is taken."""
    lock = CampaignTurnLock(campaign_dir)
    if not lock.acquire(blocking=blocking):
        raise TurnLockBusy(f"a turn of {Path(campaign_dir).name} is already running")
    try:
        yield lock
    finally:
        lock.release()


def try_campaign_turn_lock(campaign_dir: Path) -> CampaignTurnLock | None:
    """The held lock, or None when another process runs a turn; the caller releases it."""
    lock = CampaignTurnLock(campaign_dir)
    return lock if lock.acquire(blocking=False) else None
