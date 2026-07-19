"""Durable provider resume state scoped to one campaign."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

RUNTIME_SESSION_FILENAME = ".runtime-session.json"
RUNTIME_SESSION_VERSION = 1


@dataclass(frozen=True)
class RuntimeSessionState:
    runtime_id: str
    model_name: str
    session_id: str
    updated_at: str
    version: int = RUNTIME_SESSION_VERSION

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "RuntimeSessionState | None":
        try:
            version = int(raw.get("version", 0))
        except (TypeError, ValueError):
            return None
        runtime_id = str(raw.get("runtime_id") or "").strip()
        model_name = str(raw.get("model_name") or "").strip()
        session_id = str(raw.get("session_id") or "").strip()
        updated_at = str(raw.get("updated_at") or "").strip()
        if (
            version != RUNTIME_SESSION_VERSION
            or not runtime_id
            or not model_name
            or not session_id
            or not updated_at
        ):
            return None
        return cls(
            runtime_id=runtime_id,
            model_name=model_name,
            session_id=session_id,
            updated_at=updated_at,
            version=version,
        )


def runtime_session_path(campaign_dir: Path) -> Path:
    return Path(campaign_dir) / RUNTIME_SESSION_FILENAME


def load_runtime_session(campaign_dir: Path) -> RuntimeSessionState | None:
    """Load a valid resume token or return ``None`` for absent/corrupt state."""

    path = runtime_session_path(campaign_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable runtime session state %s: %s", path, exc)
        return None
    if not isinstance(raw, Mapping):
        logger.warning("Ignoring invalid runtime session state %s", path)
        return None
    state = RuntimeSessionState.from_mapping(raw)
    if state is None:
        logger.warning("Ignoring invalid runtime session state %s", path)
    return state


def save_runtime_session(
    campaign_dir: Path,
    *,
    runtime_id: str,
    model_name: str,
    session_id: str,
) -> RuntimeSessionState:
    """Atomically persist the current provider conversation identifier."""

    campaign_dir = Path(campaign_dir)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    state = RuntimeSessionState(
        runtime_id=runtime_id,
        model_name=model_name,
        session_id=session_id,
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    path = runtime_session_path(campaign_dir)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f"{RUNTIME_SESSION_FILENAME}.",
        suffix=".tmp",
        dir=campaign_dir,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(asdict(state), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise
    return state


def clear_runtime_session(campaign_dir: Path) -> None:
    """Forget provider memory without touching WorldGraph or the event log."""

    try:
        runtime_session_path(campaign_dir).unlink()
    except FileNotFoundError:
        pass
