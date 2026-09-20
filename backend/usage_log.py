"""Persistent token usage accounting for completed game turns."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

USAGE_DIRECTORY = "usage"
USAGE_FILENAME = "game-turns.jsonl"

# Virtual prices, not actual subscription charges.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"input": 2.0, "output": 10.0},
    "claude-opus-5": {"input": 5.0, "output": 25.0},
    "claude-fable-5-1": {"input": 10.0, "output": 50.0},
}
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def usage_log_path(project_root: Path) -> Path:
    """Return this feature's log path without creating its directory."""

    return Path(project_root) / "world-state" / USAGE_DIRECTORY / USAGE_FILENAME


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_usage(raw: Mapping[str, Any] | None) -> dict[str, int] | None:
    """Normalize Claude or Codex provider usage into the accounting fields."""

    if not isinstance(raw, Mapping):
        return None
    # Claude SDK uses snake_case; Codex app-server uses camelCase.
    return {
        "input_tokens": _token_count(
            raw.get("input_tokens", raw.get("inputTokens"))
        ),
        "output_tokens": _token_count(
            raw.get("output_tokens", raw.get("outputTokens"))
        ),
        "cache_read_tokens": _token_count(
            raw.get(
                "cache_read_input_tokens",
                raw.get("cached_input_tokens", raw.get("cachedInputTokens")),
            )
        ),
        "cache_write_tokens": _token_count(
            raw.get(
                "cache_creation_input_tokens",
                raw.get("cache_write_tokens", raw.get("cacheCreationInputTokens")),
            )
        ),
    }


def calculate_price_usd(model_id: str, usage: Mapping[str, int]) -> float | None:
    """Calculate the virtual price, or ``None`` when no model rate is known."""

    rates = MODEL_PRICING.get(model_id)
    if rates is None:
        return None
    input_cost = (
        usage["input_tokens"]
        + usage["cache_read_tokens"] * CACHE_READ_MULTIPLIER
        + usage["cache_write_tokens"] * CACHE_WRITE_MULTIPLIER
    ) * rates["input"] / 1_000_000
    output_cost = usage["output_tokens"] * rates["output"] / 1_000_000
    return round(input_cost + output_cost, 8)


def build_usage_record(
    *,
    campaign: str,
    runtime: str,
    model_id: str,
    usage: Mapping[str, Any],
    duration_seconds: float,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build one stable JSONL record from provider usage."""

    normalized = normalize_usage(usage)
    if normalized is None:
        raise ValueError("usage must be a mapping")
    price = calculate_price_usd(model_id, normalized)
    return {
        "timestamp": recorded_at or datetime.now(timezone.utc).isoformat(),
        "campaign": campaign,
        "runtime": runtime,
        "model": model_id,
        **normalized,
        "price_usd": price,
        "price_status": "known" if price is not None else "unknown_model",
        "duration_seconds": round(max(0.0, duration_seconds), 6),
    }


def append_usage_record(project_root: Path, record: Mapping[str, Any]) -> Path:
    """Append one JSON object without reading or rewriting existing records."""

    path = usage_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return path


def record_usage(
    *,
    project_root: Path,
    campaign: str,
    runtime: str,
    model_id: str,
    usage: Mapping[str, Any] | None,
    duration_seconds: float,
) -> dict[str, Any] | None:
    """Normalize and append usage, returning the record or ``None`` if absent."""

    if usage is None:
        logger.warning(
            "Usage accounting unavailable for campaign=%s runtime=%s model=%s: "
            "provider returned no usage",
            campaign,
            runtime,
            model_id,
        )
        return None
    record = build_usage_record(
        campaign=campaign,
        runtime=runtime,
        model_id=model_id,
        usage=usage,
        duration_seconds=duration_seconds,
    )
    if record["price_status"] != "known":
        logger.warning(
            "Usage pricing unavailable for unknown model=%s campaign=%s",
            model_id,
            campaign,
        )
    append_usage_record(project_root, record)
    return record


def _empty_totals() -> dict[str, Any]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "price_usd": 0.0,
        "price_known": True,
        "turns": 0,
    }


def _add_record(total: dict[str, Any], record: Mapping[str, Any]) -> None:
    for field in TOKEN_FIELDS:
        total[field] += _token_count(record.get(field))
    total["turns"] += 1
    price = record.get("price_usd")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        total["price_usd"] += float(price)
    else:
        total["price_known"] = False


def usage_totals(project_root: Path) -> dict[str, Any]:
    """Aggregate valid records by campaign, model, and globally."""

    by_campaign: defaultdict[str, dict[str, Any]] = defaultdict(_empty_totals)
    by_model: defaultdict[str, dict[str, Any]] = defaultdict(_empty_totals)
    total = _empty_totals()
    path = usage_log_path(project_root)
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Ignoring malformed usage log line %s:%s", path, line_number)
                    continue
                if not isinstance(record, Mapping):
                    logger.warning("Ignoring non-object usage log line %s:%s", path, line_number)
                    continue
                campaign = str(record.get("campaign") or "unknown")
                model = str(record.get("model") or "unknown")
                _add_record(by_campaign[campaign], record)
                _add_record(by_model[model], record)
                _add_record(total, record)
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Could not read usage log %s", path)

    for values in (*by_campaign.values(), *by_model.values(), total):
        values["price_usd"] = (
            round(values["price_usd"], 8) if values["price_known"] else None
        )
    return {
        "campaigns": dict(sorted(by_campaign.items())),
        "models": dict(sorted(by_model.items())),
        "total": total,
    }
