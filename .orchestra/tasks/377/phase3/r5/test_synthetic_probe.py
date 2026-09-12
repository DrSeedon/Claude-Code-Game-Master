import json
import importlib.util
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("r5_synthetic_probe", HERE / "synthetic_probe.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
run_probe = MODULE.run_probe


def test_r5_synthetic_contract_trace() -> None:
    result = run_probe()
    assert result["network_or_provider_calls"] == 0
    assert result["raw_audio_files_created"] == 0
    assert result["summary"] == {
        "checks_passed": 26,
        "checks_total": 26,
        "attempts": 9,
        "drafts": 4,
        "declared_roll_commits": 1,
        "world_mutations": 0,
        "late_provider_events_ignored": 2,
    }
    assert all(result["checks"].values())


def test_r5_schema_samples_and_durable_attempts() -> None:
    result = run_probe()
    schema = json.loads((HERE / "protocol-schemas.json").read_text(encoding="utf-8"))
    event_validator = Draft202012Validator(schema)
    attempt_validator = Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$ref": "#/$defs/InputAttempt",
            "$defs": schema["$defs"],
        }
    )
    for sample in result["schema_samples"]:
        event_validator.validate(sample)
    for attempt in result["durable_attempts"]:
        attempt_validator.validate(attempt)

    accepted = next(
        sample for sample in result["schema_samples"] if sample["kind"] == "input.capture.accepted"
    )
    assert not event_validator.is_valid(
        {**accepted, "purpose": "declared_roll", "pending_roll_id": None}
    )
    assert not event_validator.is_valid(
        {**accepted, "purpose": "action", "pending_roll_id": "pending-roll-invalid"}
    )


def test_schema_closes_authority_and_raw_audio_fields() -> None:
    schema = json.loads((HERE / "protocol-schemas.json").read_text(encoding="utf-8"))
    start = schema["$defs"]["CaptureStart"]
    assert start["additionalProperties"] is False
    assert "room_id" not in start["properties"]
    assert "role" not in start["properties"]
    assert "raw_audio" not in schema["$defs"]["InputAttempt"]["properties"]
    assert "interim_text" not in schema["$defs"]["InputAttempt"]["properties"]
