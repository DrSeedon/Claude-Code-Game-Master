from pathlib import Path

import pytest

from durability_probe import (
    FAULT_STAGES,
    EventCheckpointStore,
    STORE_TYPES,
    TransactionalOutboxStore,
    run_edge_cases,
    run_fault_case,
    run_golden_stats,
)


@pytest.mark.parametrize("store_type", STORE_TYPES, ids=lambda item: item.model_name)
@pytest.mark.parametrize("fault_stage", FAULT_STAGES)
def test_crash_reload_common_oracle(tmp_path: Path, store_type, fault_stage: str) -> None:
    result = run_fault_case(store_type, tmp_path, fault_stage)
    assert result["pass"], result
    assert result["duplicate_returned_stored_result"] is True
    assert result["final_mutation_count"] == 1


@pytest.mark.parametrize("store_type", STORE_TYPES, ids=lambda item: item.model_name)
def test_duplicate_order_stale_replay_projection_and_corruption_oracles(
    tmp_path: Path, store_type
) -> None:
    results = run_edge_cases(store_type, tmp_path)
    assert len(results) == 11
    assert all(item["pass"] for item in results), results


def test_candidates_converge_to_byte_equivalent_observables(tmp_path: Path) -> None:
    event_result = run_golden_stats(EventCheckpointStore, tmp_path / "events")
    tx_result = run_golden_stats(TransactionalOutboxStore, tmp_path / "transactions")
    assert event_result["pass"] and tx_result["pass"]
    assert event_result["world_digest"] == tx_result["world_digest"]
    assert event_result["projection_digest"] == tx_result["projection_digest"]
    assert event_result["stored_world_result"] == tx_result["stored_world_result"]
