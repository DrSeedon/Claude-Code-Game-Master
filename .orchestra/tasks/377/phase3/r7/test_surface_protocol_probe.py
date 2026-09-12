"""Mechanical oracle for the synthetic R7 contract probe."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from surface_protocol_probe import (
    CANARY,
    Client,
    Clock,
    OTHER_ROOM,
    PROJECTION_VALIDATOR,
    RenderFailure,
    SyntheticAuthority,
    make_session,
    normalize_pointer_gesture,
    run_probe,
)


def test_three_clients_converge_duplicate_once_and_secret_absent() -> None:
    result = run_probe()
    assert result["oracle"] == "PASS"
    assert result["client_versions"] == {
        "admin": [3],
        "composite": [3],
        "scene": [3],
        "table": [3],
    }
    assert result["duplicate_event_render_count"] == 1
    assert result["secret_canary_absent"] is True
    assert result["unauthorized_protected_state_unchanged"] is True
    assert result["final_audio_leader_count"] == 1


def test_projection_schema_rejects_unknown_and_secret_fields() -> None:
    projection_schema = json.loads(Path(__file__).with_name("projection-schemas.json").read_text())
    transport_schema = json.loads(Path(__file__).with_name("transport-schemas.json").read_text())
    Draft202012Validator.check_schema(projection_schema)
    Draft202012Validator.check_schema(transport_schema)
    transport = Draft202012Validator(transport_schema)
    transport.validate(
        {
            "protocol_version": 1,
            "kind": "draft.approve",
            "turn_id": "turn-1",
            "draft_version": 1,
            "approval_nonce": "a" * 32,
        }
    )
    poisoned_approval = {
        "protocol_version": 1,
        "kind": "draft.approve",
        "turn_id": "turn-1",
        "draft_version": 1,
        "approval_nonce": "a" * 32,
        "room_id": "attacker-room",
    }
    with pytest.raises(ValidationError):
        transport.validate(poisoned_approval)
    with pytest.raises(ValidationError):
        transport.validate(
            {
                "protocol_version": 1,
                "kind": "projection.ack",
                "event_id": "event-1",
                "projection_batch_id": "batch-1",
                "surface": "table",
                "stream_seq": 1,
                "projection_schema": "admin.v1",
                "reducer_version": 1,
            }
        )
    transport.validate(
        {
            "protocol_version": 1,
            "kind": "admin.operation",
            "operation_id": "operation-1",
            "expected_control_revision": 0,
            "operation": "set_volume",
            "parameters": {"volume": 0.5},
        }
    )
    with pytest.raises(ValidationError):
        transport.validate(
            {
                "protocol_version": 1,
                "kind": "admin.operation",
                "operation_id": "operation-2",
                "expected_control_revision": 0,
                "operation": "start",
                "parameters": {"volume": 0.5},
            }
        )
    server = SyntheticAuthority(Clock())
    message = server.commit_and_project()["table"]
    PROJECTION_VALIDATOR.validate(message)
    poisoned = copy.deepcopy(message)
    poisoned["payload"]["world_secret"] = CANARY
    with pytest.raises(ValidationError):
        PROJECTION_VALIDATOR.validate(poisoned)
    assert CANARY not in json.dumps(message, sort_keys=True)


def test_render_exception_does_not_advance_cursor_then_replay_applies_once() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    event = server.commit_and_project()["table"]
    client = Client("table", make_session("table", "table", clock))
    client.fail_once.add(event["event_id"])
    with pytest.raises(RenderFailure):
        client.receive_projection(event)
    assert client.cursors.get("table", 0) == 0
    assert event["event_id"] not in client.applied_event_ids
    assert client.receive_projection(event) == "applied"
    assert client.receive_projection(event) == "duplicate"
    assert client.cursors["table"] == 1
    assert client.render_counts[event["event_id"]] == 1


def test_reorder_gap_and_drop_recover_from_snapshot() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    session = make_session("scene", "scene", clock)
    client = Client("scene", session)
    v1 = server.commit_and_project()["scene"]
    server.commit_and_project()
    v3 = server.commit_and_project()["scene"]
    assert client.receive_projection(v1) == "applied"
    assert client.receive_projection(v3) == "gap"
    assert client.cursors["scene"] == 1
    assert client.receive_projection(server.snapshot("scene")) == "applied"
    assert client.cursors["scene"] == 3
    assert client.aggregate_versions() == {3}


def test_capability_denials_leave_every_protected_surface_unchanged() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    server.commit_and_project()
    table = make_session("table", "table", clock)
    scene = make_session("scene", "scene", clock)
    before = server.protected_fingerprint()
    cases = [
        (table, "room.start", {}),
        (scene, "draft.approve", {}),
        (table, "draft.approve", {"room_id": OTHER_ROOM}),
        (table, "draft.approve", {"surface": "admin"}),
        (table, "draft.approve", {"actor_id": "hero-2"}),
        (table, "kernel.execute", {}),
    ]
    for session, action, claims in cases:
        with pytest.raises(PermissionError):
            server.forbidden_browser_action(session, action, **claims)
        assert server.protected_fingerprint() == before
    assert len([row for row in server.audit if row["decision"] == "deny"]) == len(cases)
    server.redeem_enrollment_ticket("ticket")
    after_legitimate_consumption = server.protected_fingerprint()
    with pytest.raises(PermissionError):
        server.redeem_enrollment_ticket("ticket")
    assert server.protected_fingerprint() == after_legitimate_consumption
    assert server.ticket_audit[-1]["reason"] == "replay"


def test_overlay_survives_reconnect_until_server_ttl_without_world_change() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    table = make_session("table", "table", clock)
    canonical_before = (
        server.world_revision,
        server.aggregate_version,
        server.world_mutation_count,
    )
    item = server.create_overlay(
        table,
        command_id="overlay-command",
        overlay_id="overlay",
        kind="marker",
        points=[{"x": 2, "y": 3}],
        ttl_ms=1_000,
    )
    assert server.overlay_snapshot()["items"] == [item]
    duplicate = server.create_overlay(
        table,
        command_id="overlay-command",
        overlay_id="changed-id-is-ignored",
        kind="arrow",
        points=[{"x": 0, "y": 0}, {"x": 3, "y": 3}],
        ttl_ms=30_000,
    )
    assert duplicate == item
    clock.advance(999)
    assert server.overlay_snapshot()["items"] == [item]
    clock.advance(1)
    assert server.overlay_snapshot()["items"] == []
    assert (
        server.world_revision,
        server.aggregate_version,
        server.world_mutation_count,
    ) == canonical_before


def test_audio_leader_is_unique_and_stale_generation_is_fenced() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    table = make_session("table", "table", clock, audio_candidate=True)
    scene = make_session("scene", "scene", clock, audio_candidate=True)
    server.register_audio_candidate(table, priority=10, unlocked=True)
    server.register_audio_candidate(scene, priority=20, unlocked=True)
    first = server.elect_audio_leader()
    assert first is not None
    assert server.can_render_audio(table, first["generation"])
    assert not server.can_render_audio(scene, first["generation"])
    server.disconnect_audio_candidate(table.consumer_id)
    second = server.elect_audio_leader()
    assert second is not None
    assert second["generation"] > first["generation"]
    assert not server.can_render_audio(table, first["generation"])
    assert server.can_render_audio(scene, second["generation"])


def test_mouse_touch_and_pen_use_one_pointer_contract() -> None:
    def drag(pointer_type: str, pointer_id: int) -> list[dict[str, object]]:
        return [
            {
                "type": "pointerdown",
                "pointerId": pointer_id,
                "pointerType": pointer_type,
                "isPrimary": True,
                "buttons": 1,
                "x": 1,
                "y": 1,
            },
            {
                "type": "pointermove",
                "pointerId": pointer_id,
                "pointerType": pointer_type,
                "isPrimary": True,
                "buttons": 1,
                "x": 2,
                "y": 2,
            },
            {
                "type": "pointerup",
                "pointerId": pointer_id,
                "pointerType": pointer_type,
                "isPrimary": True,
                "buttons": 0,
                "x": 3,
                "y": 3,
            },
        ]

    expected = normalize_pointer_gesture(drag("mouse", 1))
    assert normalize_pointer_gesture(drag("touch", 44)) == expected
    assert normalize_pointer_gesture(drag("pen", 71)) == expected
    cancelled = drag("touch", 45)
    cancelled[-1]["type"] = "pointercancel"
    assert normalize_pointer_gesture(cancelled) is None
    nonprimary = drag("touch", 46)
    nonprimary[0]["isPrimary"] = False
    assert normalize_pointer_gesture(nonprimary) is None


def test_composite_gets_table_and_scene_only_at_one_batch() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    server.commit_and_project()
    composite = Client(
        "composite",
        make_session("table", "composite", clock, composite=True),
    )
    assert composite.receive_projection(server.snapshot("table")) == "staged"
    assert composite.states == {}
    assert composite.cursors == {}
    assert composite.receive_projection(server.snapshot("scene")) == "applied_batch"
    assert set(composite.states) == {"table", "scene"}
    assert composite.aggregate_versions() == {1}
    assert composite.visible_batch_id == "batch:1"
    with pytest.raises(PermissionError):
        composite.receive_projection(server.snapshot("admin"))


def test_admin_controls_are_operational_and_world_neutral() -> None:
    clock = Clock()
    server = SyntheticAuthority(clock)
    admin = make_session("admin", "admin", clock)
    before = (server.world_revision, server.aggregate_version, server.world_mutation_count)
    assert server.admin_action(admin, "room.start")["run_state"] == "running"
    assert server.admin_action(admin, "room.pause")["run_state"] == "paused"
    assert server.admin_action(admin, "diagnostics.read") == {
        "microphone": "ok",
        "websocket": "ok",
    }
    assert server.admin_action(admin, "volume.set")["world_revision"] == 0
    assert server.admin_action(admin, "generation.cancel")["world_revision"] == 0
    assert server.admin_action(admin, "audio.cancel")["world_revision"] == 0
    assert server.admin_action(admin, "projection.reproject")["world_revision"] == 0
    assert server.admin_action(admin, "room.end")["run_state"] == "ended"
    assert (server.world_revision, server.aggregate_version, server.world_mutation_count) == before
