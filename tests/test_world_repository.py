"""Persistence, transaction, and concurrency tests for WorldGraph."""

import json
import multiprocessing
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from world_graph import WorldGraph


def _add_node_in_transaction(campaign_dir: str, node_id: str, delay: float) -> None:
    graph = WorldGraph(Path(campaign_dir))
    with graph.transaction():
        time.sleep(delay)
        assert graph.add_node(node_id, "npc", node_id)


def test_transaction_loads_and_commits_once(tmp_path, monkeypatch):
    graph = WorldGraph(tmp_path)
    loads = 0
    writes = 0
    original_read = graph.repository._read_unlocked
    original_write = graph.repository._write_unlocked

    def counted_read():
        nonlocal loads
        loads += 1
        return original_read()

    def counted_write(data, revision):
        nonlocal writes
        writes += 1
        return original_write(data, revision)

    monkeypatch.setattr(graph.repository, "_read_unlocked", counted_read)
    monkeypatch.setattr(graph.repository, "_write_unlocked", counted_write)

    with graph.transaction():
        graph.add_node("npc:first", "npc", "First")
        graph.add_node("npc:second", "npc", "Second")
        graph.add_edge("npc:first", "npc:second", "relationship")

    assert loads == 1
    assert writes == 1
    assert graph.repository.load()["meta"]["revision"] == 1


def test_transaction_rolls_back_on_exception(tmp_path):
    graph = WorldGraph(tmp_path)

    with pytest.raises(RuntimeError):
        with graph.transaction():
            graph.add_node("npc:temporary", "npc", "Temporary")
            raise RuntimeError("abort")

    assert graph.get_node("npc:temporary") is None
    assert not graph.world_file.exists()


def test_stale_snapshot_is_rejected_without_overwrite(tmp_path, capsys):
    first = WorldGraph(tmp_path)
    second = WorldGraph(tmp_path)
    stale = first._load()

    assert second.add_node("npc:new", "npc", "New") is True
    stale["nodes"]["npc:stale"] = {
        "type": "npc",
        "name": "Stale",
        "data": {},
    }

    assert first._save(stale) is False
    assert first.get_node("npc:new") is not None
    assert first.get_node("npc:stale") is None
    assert "Concurrent world update rejected" in capsys.readouterr().err


def test_cross_process_transactions_preserve_both_updates(tmp_path):
    slow = multiprocessing.Process(
        target=_add_node_in_transaction,
        args=(str(tmp_path), "npc:slow", 0.2),
    )
    fast = multiprocessing.Process(
        target=_add_node_in_transaction,
        args=(str(tmp_path), "npc:fast", 0.0),
    )

    slow.start()
    time.sleep(0.05)
    fast.start()
    slow.join(timeout=5)
    fast.join(timeout=5)

    assert slow.exitcode == 0
    assert fast.exitcode == 0
    data = json.loads((tmp_path / "world.json").read_text(encoding="utf-8"))
    assert {"npc:slow", "npc:fast"} <= data["nodes"].keys()
    assert data["meta"]["revision"] == 2


def test_existing_world_gets_revision_without_schema_change(tmp_path):
    legacy = {
        "meta": {"version": 2, "schema": "graph"},
        "nodes": {},
        "edges": [],
    }
    (tmp_path / "world.json").write_text(json.dumps(legacy), encoding="utf-8")
    graph = WorldGraph(tmp_path)

    assert graph.add_node("npc:sage", "npc", "Sage")

    saved = json.loads((tmp_path / "world.json").read_text(encoding="utf-8"))
    assert saved["meta"]["version"] == 2
    assert saved["meta"]["revision"] == 1


def test_initialize_does_not_replace_existing_world(tmp_path):
    graph = WorldGraph(tmp_path)
    assert graph.ensure_initialized() is True
    assert graph.add_node("npc:keeper", "npc", "Keeper")

    assert graph.ensure_initialized() is False
    assert graph.get_node("npc:keeper") is not None


def test_reset_replaces_world_and_advances_revision(tmp_path):
    graph = WorldGraph(tmp_path)
    assert graph.add_node("npc:temporary", "npc", "Temporary")
    previous_revision = graph.repository.revision(graph.repository.load())

    assert graph.reset() is True

    saved = graph.repository.load()
    assert saved["nodes"] == {}
    assert saved["edges"] == []
    assert saved["meta"]["revision"] == previous_revision + 1
