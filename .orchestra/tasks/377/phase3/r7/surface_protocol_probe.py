"""Synthetic R7 transport/capability probe; not production frontend or server code."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CANARY = "GM_ONLY_CANARY_377_R7"
ROOM = "room-a"
OTHER_ROOM = "room-b"
SCHEMA_PATH = Path(__file__).with_name("projection-schemas.json")
PROJECTION_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
PROJECTION_VALIDATOR = Draft202012Validator(PROJECTION_SCHEMA)


CAPABILITIES = {
    "table": {
        "projection.read.table",
        "projection.ack.table",
        "draft.submit",
        "actor.select",
        "draft.approve",
        "draft.reject",
        "overlay.write",
    },
    "scene": {"projection.read.scene", "projection.ack.scene"},
    "admin": {
        "projection.read.admin",
        "projection.ack.admin",
        "room.start",
        "room.pause",
        "room.end",
        "diagnostics.read",
        "volume.set",
        "generation.cancel",
        "audio.cancel",
        "projection.reproject",
        "stage.retry_unfinished",
    },
}


class RenderFailure(RuntimeError):
    """A deterministic stand-in for a DOM reducer/render exception."""


@dataclass
class Clock:
    now_ms: int = 1_000_000

    def advance(self, delta_ms: int) -> None:
        self.now_ms += delta_ms


@dataclass(frozen=True)
class Session:
    session_id: str
    consumer_id: str
    room_id: str
    role: str
    allowed_actor_ids: frozenset[str]
    capabilities: frozenset[str]
    expires_at_ms: int
    projection_surfaces: tuple[str, ...]


@dataclass
class Client:
    name: str
    session: Session
    states: dict[str, dict[str, Any]] = field(default_factory=dict)
    cursors: dict[str, int] = field(default_factory=dict)
    applied_event_ids: set[str] = field(default_factory=set)
    render_counts: dict[str, int] = field(default_factory=dict)
    fail_once: set[str] = field(default_factory=set)
    overlays: dict[str, dict[str, Any]] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)
    staged_batches: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    visible_batch_id: str | None = None

    def _commit_projection(self, envelope: dict[str, Any]) -> None:
        surface = envelope["surface"]
        event_id = envelope["event_id"]
        self.states[surface] = copy.deepcopy(envelope["payload"])
        self.versions[surface] = envelope["aggregate_version"]
        self.applied_event_ids.add(event_id)
        self.cursors[surface] = envelope["stream_seq"]
        self.render_counts[event_id] = self.render_counts.get(event_id, 0) + 1

    def receive_projection(self, envelope: dict[str, Any]) -> str:
        errors = list(PROJECTION_VALIDATOR.iter_errors(envelope))
        if errors:
            raise ValueError(errors[0].message)
        surface = envelope["surface"]
        if surface not in self.session.projection_surfaces:
            raise PermissionError("projection surface is not in the server-owned session")
        seq = envelope["stream_seq"]
        cursor = self.cursors.get(surface, 0)
        event_id = envelope["event_id"]
        if event_id in self.applied_event_ids or seq <= cursor:
            return "duplicate"
        if envelope["kind"] == "projection.event" and seq != cursor + 1:
            return "gap"

        is_composite = set(self.session.projection_surfaces) == {"table", "scene"}
        if is_composite:
            batch_id = envelope["projection_batch_id"]
            batch = self.staged_batches.setdefault(batch_id, {})
            batch[surface] = copy.deepcopy(envelope)
            if set(batch) != {"table", "scene"}:
                return "staged"
            versions = {
                (item["aggregate_version"], item["world_revision"]) for item in batch.values()
            }
            if len(versions) != 1:
                self.staged_batches.pop(batch_id, None)
                return "gap"
            for item in batch.values():
                if item["event_id"] in self.fail_once:
                    self.fail_once.remove(item["event_id"])
                    raise RenderFailure(item["event_id"])
            for item in batch.values():
                self._commit_projection(item)
            self.visible_batch_id = batch_id
            self.staged_batches.pop(batch_id, None)
            return "applied_batch"

        if event_id in self.fail_once:
            self.fail_once.remove(event_id)
            raise RenderFailure(event_id)
        # A real browser builds a detached render tree and swaps it here.
        self._commit_projection(envelope)
        return "applied"

    def aggregate_versions(self) -> set[int]:
        return set(self.versions.values())


class SyntheticAuthority:
    """Production-shaped invariants without HTTP, WebSocket, provider, or DB I/O."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.world_revision = 0
        self.aggregate_version = 0
        self.world_mutation_count = 0
        self.control_revision = 0
        self.run_state = "stopped"
        self.volume = 0.7
        self.canonical = {
            "secret": CANARY,
            "board_id": "board-public",
            "hero_hp": 12,
        }
        self.streams: dict[str, list[dict[str, Any]]] = {
            "table": [],
            "scene": [],
            "admin": [],
        }
        self.audit: list[dict[str, Any]] = []
        self.overlays: dict[str, dict[str, Any]] = {}
        self.overlay_seq = 0
        self.overlay_dedupe: dict[tuple[str, str], dict[str, Any]] = {}
        self.audio_candidates: dict[str, tuple[Session, int, bool]] = {}
        self.audio_lease: dict[str, Any] | None = None
        self.audio_generation = 0
        self.used_enrollment_tickets: set[str] = set()
        self.ticket_audit: list[dict[str, Any]] = []

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:12]

    def _audit(self, session: Session, action: str, decision: str, reason: str) -> None:
        self.audit.append(
            {
                "at_ms": self.clock.now_ms,
                "session_ref": self._hash(session.session_id),
                "server_role": session.role,
                "server_room": session.room_id,
                "action": action,
                "decision": decision,
                "reason": reason,
            }
        )

    def protected_fingerprint(self) -> str:
        protected = {
            "world_revision": self.world_revision,
            "aggregate_version": self.aggregate_version,
            "world_mutation_count": self.world_mutation_count,
            "control_revision": self.control_revision,
            "run_state": self.run_state,
            "volume": self.volume,
            "canonical": self.canonical,
            "stream_lengths": {key: len(value) for key, value in self.streams.items()},
            "overlays": self.overlays,
            "audio_lease": self.audio_lease,
        }
        return hashlib.sha256(
            json.dumps(protected, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _authorize(
        self,
        session: Session,
        action: str,
        *,
        claimed_room: str | None = None,
        claimed_surface: str | None = None,
        claimed_actor: str | None = None,
    ) -> None:
        if self.clock.now_ms >= session.expires_at_ms:
            self._audit(session, action, "deny", "expired_session")
            raise PermissionError("expired_session")
        if claimed_room is not None and claimed_room != session.room_id:
            self._audit(session, action, "deny", "cross_room")
            raise PermissionError("cross_room")
        if claimed_surface is not None and claimed_surface != session.role:
            self._audit(session, action, "deny", "surface_spoof")
            raise PermissionError("surface_spoof")
        if claimed_actor is not None and claimed_actor not in session.allowed_actor_ids:
            self._audit(session, action, "deny", "actor_spoof")
            raise PermissionError("actor_spoof")
        if action not in session.capabilities:
            self._audit(session, action, "deny", "missing_capability")
            raise PermissionError("missing_capability")

    def redeem_enrollment_ticket(self, ticket_jti: str) -> None:
        if ticket_jti in self.used_enrollment_tickets:
            self.ticket_audit.append(
                {"ticket_ref": self._hash(ticket_jti), "decision": "deny", "reason": "replay"}
            )
            raise PermissionError("replayed_ticket")
        self.used_enrollment_tickets.add(ticket_jti)
        self.ticket_audit.append(
            {"ticket_ref": self._hash(ticket_jti), "decision": "allow", "reason": "consumed"}
        )

    def _base_envelope(self, surface: str, version: int, *, kind: str) -> dict[str, Any]:
        seq = len(self.streams[surface]) + (1 if kind == "projection.event" else 0)
        return {
            "protocol_version": 1,
            "kind": kind,
            "event_id": f"projection:{version}:{surface}",
            "projection_batch_id": f"batch:{version}",
            "room_id": ROOM,
            "surface": surface,
            "stream_seq": seq,
            "aggregate_version": version,
            "world_revision": version,
            "projection_schema": f"{surface}.v1",
        }

    @staticmethod
    def _health(surface: str, version: int) -> dict[str, Any]:
        return {
            "surface": surface,
            "status": "current",
            "projected_aggregate_version": version,
            "last_ack_age_bucket": "lt_5s",
        }

    def _payload(self, surface: str, version: int) -> dict[str, Any]:
        if surface == "table":
            return {
                "board": {
                    "board_id": "board-public",
                    "width": 4,
                    "height": 4,
                    "cells": [
                        {
                            "x": 0,
                            "y": 0,
                            "terrain": "floor",
                            "movement_cost": 1,
                            "blocked": False,
                            "visible": True,
                        }
                    ],
                    "tokens": [
                        {
                            "public_id": "hero-1",
                            "kind": "hero",
                            "display_name": "Hero",
                            "x": version % 4,
                            "y": 0,
                            "hp": self.canonical["hero_hp"],
                            "hp_max": 12,
                            "conditions": [],
                            "acted": False,
                        }
                    ],
                    "legal_cells": [{"x": 1, "y": 0}],
                    "public_rolls": [],
                },
                "phase": {
                    "mode": "combat",
                    "round": version,
                    "side": "players",
                    "acted_actor_ids": [],
                },
                "draft_card": None,
                "public_events": [
                    {
                        "public_event_id": f"public-{version}",
                        "kind": "result",
                        "text": f"Committed public result {version}",
                    }
                ],
                "activity": "idle",
            }
        if surface == "scene":
            return {
                "scene": {
                    "public_scene_id": "scene-public",
                    "title": "Public chamber",
                    "image_asset_ref": "asset-scene-public",
                    "transition": "fade",
                },
                "speaker": None,
                "subtitle": f"Public narration {version}",
                "public_result": f"Committed public result {version}",
                "activity": "idle",
            }
        return {
            "run_state": self.run_state,
            "coordinator": {
                "stage": "committed",
                "recovery_action": "none",
                "aggregate_version": version,
                "world_revision": version,
                "control_revision": self.control_revision,
            },
            "projection_health": [self._health(name, version) for name in self.streams],
            "audio_health": {
                "status": "idle",
                "leader_present": self.audio_lease is not None,
                "generation": self.audio_generation,
                "buffer_bucket": "empty",
                "current_line_ref": None,
            },
            "input_health": {
                "microphone": "ok",
                "websocket": "ok",
                "stt": "ok",
                "model": "ok",
                "tts": "ok",
            },
            "safe_error": None,
            "allowed_recovery_actions": [],
            "last_operation": None,
        }

    def commit_and_project(self) -> dict[str, dict[str, Any]]:
        self.world_revision += 1
        self.aggregate_version += 1
        self.world_mutation_count += 1
        version = self.aggregate_version
        published = {}
        for surface in self.streams:
            envelope = self._base_envelope(surface, version, kind="projection.event")
            envelope["payload"] = self._payload(surface, version)
            PROJECTION_VALIDATOR.validate(envelope)
            raw = json.dumps(envelope, sort_keys=True)
            assert CANARY not in raw
            self.streams[surface].append(envelope)
            published[surface] = copy.deepcopy(envelope)
        return published

    def snapshot(self, surface: str) -> dict[str, Any]:
        version = self.aggregate_version
        envelope = self._base_envelope(surface, version, kind="projection.snapshot")
        envelope["stream_seq"] = len(self.streams[surface])
        envelope["event_id"] = f"snapshot:{version}:{surface}:{len(self.streams[surface])}"
        envelope["payload"] = self._payload(surface, version)
        PROJECTION_VALIDATOR.validate(envelope)
        assert CANARY not in json.dumps(envelope, sort_keys=True)
        return envelope

    def create_overlay(
        self,
        session: Session,
        *,
        command_id: str,
        overlay_id: str,
        kind: str,
        points: list[dict[str, int]],
        ttl_ms: int,
    ) -> dict[str, Any]:
        self._authorize(session, "overlay.write")
        key = (session.session_id, command_id)
        if key in self.overlay_dedupe:
            return copy.deepcopy(self.overlay_dedupe[key])
        if kind not in {"arrow", "marker"} or not 1_000 <= ttl_ms <= 30_000:
            raise ValueError("invalid_overlay")
        if not points or len(points) > 64:
            raise ValueError("invalid_overlay_points")
        self.overlay_seq += 1
        record = {
            "overlay_id": overlay_id,
            "overlay_kind": kind,
            "points": copy.deepcopy(points),
            "creator_ref": next(iter(session.allowed_actor_ids)),
            "created_at_ms": self.clock.now_ms,
            "expires_at_ms": self.clock.now_ms + ttl_ms,
            "overlay_seq": self.overlay_seq,
        }
        self.overlays[overlay_id] = record
        self.overlay_dedupe[key] = copy.deepcopy(record)
        self._audit(session, "overlay.write", "allow", "active_until_ttl")
        return copy.deepcopy(record)

    def overlay_snapshot(self) -> dict[str, Any]:
        self.expire_overlays()
        return {
            "server_now_ms": self.clock.now_ms,
            "overlay_seq": self.overlay_seq,
            "items": [copy.deepcopy(value) for value in self.overlays.values()],
        }

    def expire_overlays(self) -> None:
        expired = [
            key
            for key, value in self.overlays.items()
            if value["expires_at_ms"] <= self.clock.now_ms
        ]
        for key in expired:
            del self.overlays[key]
            self.overlay_seq += 1

    def admin_action(self, session: Session, action: str) -> dict[str, Any]:
        self._authorize(session, action)
        if action == "room.start":
            self.run_state = "running"
        elif action == "room.pause":
            self.run_state = "paused"
        elif action == "room.end":
            self.run_state = "ended"
        elif action == "volume.set":
            self.volume = 0.5
        elif action == "diagnostics.read":
            self._audit(session, action, "allow", "read_only")
            return {"microphone": "ok", "websocket": "ok"}
        self.control_revision += 1
        self._audit(session, action, "allow", "operational_only")
        return {
            "run_state": self.run_state,
            "control_revision": self.control_revision,
            "world_revision": self.world_revision,
        }

    def forbidden_browser_action(
        self,
        session: Session,
        action: str,
        **claims: str,
    ) -> None:
        self._authorize(
            session,
            action,
            claimed_room=claims.get("room_id"),
            claimed_surface=claims.get("surface"),
            claimed_actor=claims.get("actor_id"),
        )
        if action == "kernel.execute":
            raise AssertionError("no browser role may receive kernel.execute")

    def register_audio_candidate(self, session: Session, *, priority: int, unlocked: bool) -> None:
        self._authorize(session, "audio.candidate")
        self.audio_candidates[session.consumer_id] = (session, priority, unlocked)

    def elect_audio_leader(self) -> dict[str, Any] | None:
        if self.audio_lease and self.audio_lease["expires_at_ms"] > self.clock.now_ms:
            return copy.deepcopy(self.audio_lease)
        eligible = [
            (priority, consumer_id, session)
            for consumer_id, (session, priority, unlocked) in self.audio_candidates.items()
            if unlocked and session.expires_at_ms > self.clock.now_ms
        ]
        if not eligible:
            self.audio_lease = None
            return None
        priority, consumer_id, session = min(eligible)
        self.audio_generation += 1
        self.audio_lease = {
            "lease_id": f"audio-lease-{self.audio_generation}",
            "generation": self.audio_generation,
            "consumer_id": consumer_id,
            "room_id": session.room_id,
            "not_before_ms": self.clock.now_ms,
            "expires_at_ms": self.clock.now_ms + 5_000,
        }
        return copy.deepcopy(self.audio_lease)

    def disconnect_audio_candidate(self, consumer_id: str) -> None:
        self.audio_candidates.pop(consumer_id, None)
        if self.audio_lease and self.audio_lease["consumer_id"] == consumer_id:
            self.audio_lease = None

    def can_render_audio(self, session: Session, generation: int) -> bool:
        return bool(
            self.audio_lease
            and self.audio_lease["consumer_id"] == session.consumer_id
            and self.audio_lease["generation"] == generation
            and self.audio_lease["not_before_ms"]
            <= self.clock.now_ms
            < self.audio_lease["expires_at_ms"]
        )


def make_session(
    role: str,
    consumer_id: str,
    clock: Clock,
    *,
    room_id: str = ROOM,
    composite: bool = False,
    audio_candidate: bool = False,
    expires_in_ms: int = 60_000,
) -> Session:
    capabilities = set(CAPABILITIES[role])
    surfaces = (role,)
    if composite:
        if role != "table":
            raise ValueError("composite is a table presentation mode")
        capabilities.update({"projection.read.scene", "projection.ack.scene"})
        surfaces = ("table", "scene")
    if audio_candidate:
        capabilities.add("audio.candidate")
    return Session(
        session_id=f"session-{consumer_id}",
        consumer_id=consumer_id,
        room_id=room_id,
        role=role,
        allowed_actor_ids=frozenset({"hero-1"}) if role == "table" else frozenset(),
        capabilities=frozenset(capabilities),
        expires_at_ms=clock.now_ms + expires_in_ms,
        projection_surfaces=surfaces,
    )


def normalize_pointer_gesture(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Normalize mouse/touch/pen drag using Pointer Events capture semantics."""

    if not events or events[0]["type"] != "pointerdown":
        return None
    first = events[0]
    if first.get("pointerType") not in {"mouse", "touch", "pen", ""}:
        return None
    if not first.get("isPrimary", False) or not first.get("buttons", 0) & 1:
        return None
    pointer_id = first["pointerId"]
    points = [[first["x"], first["y"]]]
    for event in events[1:]:
        if event["pointerId"] != pointer_id:
            continue
        if event["type"] == "pointercancel":
            return None
        if event["type"] == "pointermove":
            points.append([event["x"], event["y"]])
        if event["type"] == "pointerup":
            points.append([event["x"], event["y"]])
            return {
                "intent": "drag",
                "from": points[0],
                "to": points[-1],
                "points": points,
            }
    return None


def run_probe() -> dict[str, Any]:
    clock = Clock()
    server = SyntheticAuthority(clock)
    sessions = {
        "table": make_session("table", "table-1", clock, audio_candidate=True),
        "scene": make_session("scene", "scene-1", clock, audio_candidate=True),
        "admin": make_session("admin", "admin-1", clock),
        "composite": make_session("table", "composite-1", clock, composite=True),
    }
    clients = {name: Client(name, session) for name, session in sessions.items()}

    first = server.commit_and_project()
    for name in ("table", "scene", "admin"):
        clients[name].receive_projection(first[name])
        assert clients[name].receive_projection(first[name]) == "duplicate"

    second = server.commit_and_project()
    third = server.commit_and_project()
    clients["table"].receive_projection(second["table"])
    assert clients["table"].receive_projection(third["table"]) == "applied"
    assert clients["scene"].receive_projection(third["scene"]) == "gap"
    clients["scene"].receive_projection(second["scene"])
    clients["scene"].receive_projection(third["scene"])
    # Admin dropped v2/v3 and uses a full rehydrate snapshot.
    clients["admin"].receive_projection(server.snapshot("admin"))

    render_failure_event = first["table"]
    failed_client = Client("render-failure", sessions["table"])
    failed_client.fail_once.add(render_failure_event["event_id"])
    try:
        failed_client.receive_projection(render_failure_event)
    except RenderFailure:
        pass
    assert failed_client.cursors.get("table", 0) == 0
    assert failed_client.receive_projection(render_failure_event) == "applied"

    composite = clients["composite"]
    composite.receive_projection(server.snapshot("table"))
    composite.receive_projection(server.snapshot("scene"))
    assert composite.aggregate_versions() == {3}

    browser_bytes = json.dumps(
        {name: client.states for name, client in clients.items()},
        sort_keys=True,
    )
    assert CANARY not in browser_bytes

    protected = server.protected_fingerprint()
    negative_cases = [
        (sessions["table"], "room.start", {}),
        (sessions["scene"], "draft.approve", {}),
        (sessions["table"], "draft.approve", {"room_id": OTHER_ROOM}),
        (sessions["table"], "draft.approve", {"surface": "admin"}),
        (sessions["table"], "draft.approve", {"actor_id": "hero-other"}),
        (sessions["table"], "kernel.execute", {}),
    ]
    for session, action, claims in negative_cases:
        try:
            server.forbidden_browser_action(session, action, **claims)
        except PermissionError:
            pass
        assert server.protected_fingerprint() == protected
    unauthorized_unchanged = True

    expired = make_session("table", "expired", clock, expires_in_ms=0)
    try:
        server.forbidden_browser_action(expired, "draft.approve")
    except PermissionError:
        pass
    assert server.protected_fingerprint() == protected

    server.redeem_enrollment_ticket("ticket-1")
    after_ticket_consumption = server.protected_fingerprint()
    try:
        server.redeem_enrollment_ticket("ticket-1")
    except PermissionError:
        pass
    assert server.protected_fingerprint() == after_ticket_consumption

    world_before_admin = (
        server.world_revision,
        server.aggregate_version,
        server.world_mutation_count,
    )
    admin_actions = [
        "room.start",
        "room.pause",
        "diagnostics.read",
        "volume.set",
        "generation.cancel",
        "audio.cancel",
        "projection.reproject",
        "room.end",
    ]
    for action in admin_actions:
        server.admin_action(sessions["admin"], action)
    admin_world_unchanged = (
        server.world_revision,
        server.aggregate_version,
        server.world_mutation_count,
    ) == world_before_admin
    assert admin_world_unchanged

    canonical_before_overlay = (server.world_revision, server.world_mutation_count)
    overlay = server.create_overlay(
        sessions["table"],
        command_id="overlay-command-1",
        overlay_id="overlay-1",
        kind="arrow",
        points=[{"x": 0, "y": 0}, {"x": 1, "y": 1}],
        ttl_ms=2_000,
    )
    reconnect_overlays = server.overlay_snapshot()
    assert reconnect_overlays["items"] == [overlay]
    clock.advance(2_000)
    assert server.overlay_snapshot()["items"] == []
    assert (server.world_revision, server.world_mutation_count) == canonical_before_overlay

    server.register_audio_candidate(sessions["table"], priority=10, unlocked=True)
    server.register_audio_candidate(sessions["scene"], priority=20, unlocked=True)
    lease1 = server.elect_audio_leader()
    assert lease1 and server.can_render_audio(sessions["table"], lease1["generation"])
    assert not server.can_render_audio(sessions["scene"], lease1["generation"])
    server.disconnect_audio_candidate(sessions["table"].consumer_id)
    lease2 = server.elect_audio_leader()
    assert lease2 and lease2["consumer_id"] == sessions["scene"].consumer_id
    assert not server.can_render_audio(sessions["table"], lease1["generation"])
    assert server.can_render_audio(sessions["scene"], lease2["generation"])

    mouse = [
        {
            "type": "pointerdown",
            "pointerId": 1,
            "pointerType": "mouse",
            "isPrimary": True,
            "buttons": 1,
            "x": 0,
            "y": 0,
        },
        {
            "type": "pointermove",
            "pointerId": 1,
            "pointerType": "mouse",
            "isPrimary": True,
            "buttons": 1,
            "x": 1,
            "y": 0,
        },
        {
            "type": "pointerup",
            "pointerId": 1,
            "pointerType": "mouse",
            "isPrimary": True,
            "buttons": 0,
            "x": 2,
            "y": 0,
        },
    ]
    touch = copy.deepcopy(mouse)
    for event in touch:
        event["pointerId"] = 41
        event["pointerType"] = "touch"
    assert normalize_pointer_gesture(mouse) == normalize_pointer_gesture(touch)

    versions = {
        name: sorted(client.aggregate_versions())
        for name, client in clients.items()
        if name in {"table", "scene", "admin", "composite"}
    }
    assert all(value == [3] for value in versions.values())
    return {
        "oracle": "PASS",
        "aggregate_version": server.aggregate_version,
        "world_revision": server.world_revision,
        "world_mutation_count": server.world_mutation_count,
        "client_versions": versions,
        "composite_visible_batch_id": composite.visible_batch_id,
        "duplicate_event_render_count": clients["table"].render_counts[first["table"]["event_id"]],
        "failed_render_cursor_before_retry": 0,
        "failed_render_cursor_after_retry": failed_client.cursors["table"],
        "secret_canary_absent": CANARY not in browser_bytes,
        "unauthorized_case_count": len(negative_cases) + 2,
        "unauthorized_protected_state_unchanged": unauthorized_unchanged,
        "admin_operation_count": len(admin_actions),
        "admin_control_revision": server.control_revision,
        "admin_world_state_unchanged": admin_world_unchanged,
        "overlay_visible_on_reconnect_within_ttl": reconnect_overlays["items"] == [overlay],
        "overlay_expired": not server.overlays,
        "overlay_canonical_state_unchanged": (server.world_revision, server.world_mutation_count)
        == canonical_before_overlay,
        "audio_leader_generations": [lease1["generation"], lease2["generation"]],
        "final_audio_leader_count": 1 if server.audio_lease else 0,
        "pointer_mouse_touch_equivalent": normalize_pointer_gesture(mouse)
        == normalize_pointer_gesture(touch),
        "admin_browser_field_set": sorted(server._payload("admin", 3)),
        "audit_denial_count": sum(item["decision"] == "deny" for item in server.audit)
        + sum(item["decision"] == "deny" for item in server.ticket_audit),
    }


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2, sort_keys=True))
