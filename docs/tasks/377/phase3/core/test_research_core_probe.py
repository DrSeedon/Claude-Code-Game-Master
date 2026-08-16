"""Assertions around the #11 synthetic research probe; not product tests."""

import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator


PROBE_PATH = Path(__file__).with_name("research_core_probe.py")
SPEC = importlib.util.spec_from_file_location("research_core_probe", PROBE_PATH)
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
run_probe = PROBE.run_probe


def test_integrated_core_contract_probe(tmp_path: Path) -> None:
    result = run_probe(tmp_path)

    assert result["oracle"] == "PASS", result["failed"]
    assert result["passed"] == result["assertion_count"]
    assert result["assertion_count"] >= 30
    assert result["secret_canary_absent_from_projection"] is True


def test_machine_contract_accepts_probe_shapes(tmp_path: Path) -> None:
    schema = json.loads(PROBE_PATH.with_name("core-contract.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    definition = PROBE.campaign_definition()
    result = run_probe(tmp_path)
    assert result["oracle"] == "PASS"
    store = PROBE.ResearchStore(tmp_path / "schema.sqlite")
    try:
        validator.validate(definition)
        validator.validate(store.state())
        validator.validate(store.build_projection_batch())
    finally:
        store.close()

    completed = PROBE.ResearchStore(tmp_path / "core-probe.sqlite")
    try:
        completed_state = completed.state()
        validator.validate(completed_state)
        plan = completed_state["turn"]["plan"]
        validator.validate(plan)
        validator.validate(
            PROBE.command(
                "cmd:schema:prepare",
                "turn.prepare",
                plan["expected_aggregate_version"],
                turn_id=plan["turn_id"],
                draft_version=plan["draft_version"],
                args={
                    "plan": plan,
                    "approval_nonce": "s" * 32,
                    "safe_intent": completed_state["turn"]["intent_summary"],
                },
            )
        )
        validator.validate(
            PROBE.command(
                "cmd:schema:approve",
                "turn.approve",
                completed_state["aggregate_version"],
                turn_id=plan["turn_id"],
                draft_version=plan["draft_version"],
                approval_nonce="s" * 32,
            )
        )
        for row in completed.connection.execute("SELECT result_json FROM command_results"):
            validator.validate(json.loads(row["result_json"]))
        for row in completed.connection.execute("SELECT * FROM projection_batches"):
            table = json.loads(row["table_json"])
            scene = json.loads(row["scene_json"])
            admin = json.loads(row["admin_json"])
            validator.validate(
                {
                    "projection_batch_id": row["batch_id"],
                    "aggregate_version": row["aggregate_version"],
                    "world_revision": table["world_revision"],
                    "table": table,
                    "scene": scene,
                    "admin": admin,
                }
            )
    finally:
        completed.close()
