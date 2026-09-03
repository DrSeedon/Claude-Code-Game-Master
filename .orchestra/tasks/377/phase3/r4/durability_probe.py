#!/usr/bin/env python
"""Synthetic, deterministic fault harness for R4 persistence candidates.

This is research code, not product runtime. It compares two persistence shapes
behind the same decision/evolution functions and the same observable oracle.
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SCHEMA_VERSION = 1
ROOM_ID = "room-synthetic"
TURN_ID = "turn-0001"
SECRET_CANARY = "GM_ONLY_CANARY_377_R4"
FAULT_STAGES = (
    "receive",
    "draft_persist",
    "approval",
    "execution_start",
    "world_commit",
    "outbox_publish",
    "projection_ack",
    "audio_enqueue",
)
SELECTION_RULE = (
    "Reject a candidate on any common-oracle failure. If both pass, prefer the "
    "candidate whose cold recovery reads canonical current state directly and "
    "does not require semantic event replay on the availability path."
)
INTERNAL_COMMANDS = {
    "start_execution",
    "commit_world",
    "prepare_projection",
    "enqueue_audio",
}


class IntegrityFailure(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=None)
def contract_validator(definition: str) -> Draft202012Validator:
    schema_path = Path(__file__).with_name("command-event-schemas.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    wrapped = {
        "$schema": schema["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    Draft202012Validator.check_schema(wrapped)
    return Draft202012Validator(wrapped)


def validate_contract(instance: dict[str, Any], definition: str) -> None:
    contract_validator(definition).validate(instance)


def request_digest(cmd: dict[str, Any]) -> str:
    return digest({key: value for key, value in cmd.items() if key != "request_digest"})


def initial_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "aggregate_version": 0,
        "world": {
            "revision": 0,
            "hero_hp": 12,
            "mutation_count": 0,
            "public_facts": [],
            "narration_text": "",
            "image_prompt": "",
            "gm_secret": SECRET_CANARY,
            "unclassified": {},
        },
        "turn": {
            "turn_id": None,
            "stage": "listening",
            "draft_version": 0,
            "draft_text": None,
            "approved_draft_version": None,
            "execution_attempt_id": None,
            "result": None,
            "recovery_action": "none",
        },
        "projection": {
            "last_safe": {
                "revision": 0,
                "hero_hp": 12,
                "public_facts": [],
                "narration_text": "",
                "image_prompt": "",
            },
            "pending_event": None,
            "error": None,
            "acked_event_id": None,
        },
        "audio": {
            "pending_line_id": None,
            "pending_job": None,
            "enqueued_line_ids": [],
        },
    }


def command(
    command_id: str,
    command_type: str,
    expected_version: int,
    payload: dict[str, Any] | None = None,
    *,
    room_id: str = ROOM_ID,
    actor: dict[str, str] | None = None,
) -> dict[str, Any]:
    if actor is None:
        if command_type in INTERNAL_COMMANDS:
            actor = {"actor_id": "coordinator-1", "surface": "server", "role": "coordinator"}
        elif command_type == "provider_event":
            actor = {"actor_id": "provider-1", "surface": "server", "role": "provider"}
        elif command_type in {"retry_audio", "cancel_audio"}:
            actor = {"actor_id": "admin-1", "surface": "admin", "role": "admin"}
        else:
            actor = {"actor_id": "player-1", "surface": "table", "role": "player"}
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command_id": command_id,
        "room_id": room_id,
        "turn_id": TURN_ID,
        "actor": actor,
        "expected_aggregate_version": expected_version,
        "type": command_type,
        "payload": payload or {},
    }
    envelope["request_digest"] = request_digest(envelope)
    validate_contract(envelope, "CommandEnvelope")
    return envelope


def event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "type": event_type, "payload": payload}


def durable_event_envelope(
    cmd: dict[str, Any], item: dict[str, Any], state: dict[str, Any], index: int
) -> dict[str, Any]:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"event:{cmd['room_id']}:{cmd['command_id']}:{index}",
        "causation_command_id": cmd["command_id"],
        "room_id": cmd["room_id"],
        "turn_id": cmd["turn_id"],
        "aggregate_version": state["aggregate_version"],
        "world_revision": state["world"]["revision"],
        "type": item["type"],
        "payload": item["payload"],
    }
    validate_contract(envelope, "DurableEventEnvelope")
    return envelope


def command_result(
    cmd: dict[str, Any], raw: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    reserved = {
        "status",
        "code",
        "turn_id",
        "aggregate_version",
        "stage",
        "world_revision",
        "world_mutation_count",
    }
    details = {key: value for key, value in raw.items() if key not in reserved}
    result = {
        "schema_version": SCHEMA_VERSION,
        "command_id": cmd["command_id"],
        "request_digest": cmd["request_digest"],
        "room_id": cmd["room_id"],
        "turn_id": cmd["turn_id"],
        "status": raw["status"],
        "code": raw["code"],
        "aggregate_version": state["aggregate_version"],
        "stage": state["turn"]["stage"],
        "world_revision": state["world"]["revision"],
        "world_mutation_count": state["world"]["mutation_count"],
    }
    if details:
        result["details"] = details
    validate_contract(result, "CommandResult")
    return result


def evolve(source: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(source)
    payload = item["payload"]
    kind = item["type"]
    state["aggregate_version"] += 1

    if kind == "TurnReceived":
        state["turn"].update(
            turn_id=payload["turn_id"],
            stage="drafting",
            recovery_action="retry_draft",
        )
    elif kind in {"DraftPersisted", "DraftRevised"}:
        state["turn"].update(
            stage="awaiting_approval",
            draft_version=payload["draft_version"],
            draft_text=payload["draft_text"],
            recovery_action="wait_for_approval",
        )
    elif kind == "ApprovalAccepted":
        state["turn"].update(
            stage="executing",
            approved_draft_version=payload["draft_version"],
            recovery_action="start_execution",
        )
    elif kind == "ExecutionStarted":
        state["turn"].update(
            execution_attempt_id=payload["execution_attempt_id"],
            recovery_action="retry_uncommitted_execution",
        )
    elif kind == "WorldCommitted":
        world = state["world"]
        world["hero_hp"] -= payload["damage"]
        world["revision"] += 1
        world["mutation_count"] += 1
        world["public_facts"].append(payload["public_fact"])
        world["narration_text"] = payload["narration_text"]
        world["image_prompt"] = payload["image_prompt"]
        if payload.get("inject_unknown_secret"):
            world["unclassified"]["future_field"] = SECRET_CANARY
        state["turn"].update(
            stage="presenting",
            result={
                "world_revision": world["revision"],
                "hero_hp": world["hero_hp"],
                "damage": payload["damage"],
            },
            recovery_action="resume_projection",
        )
        state["projection"].update(pending_event=None, error=None)
    elif kind == "ProjectionReady":
        state["projection"].update(
            last_safe=payload["projection"], pending_event=payload["envelope"], error=None
        )
        state["turn"]["recovery_action"] = "publish_projection"
    elif kind == "ProjectionFailed":
        state["projection"].update(pending_event=None, error=payload["error_code"])
        state["turn"]["recovery_action"] = "repair_projection_schema"
    elif kind == "ProjectionAcknowledged":
        state["projection"].update(
            acked_event_id=payload["event_id"], pending_event=None, error=None
        )
        state["turn"].update(stage="committed", recovery_action="enqueue_audio")
        state["audio"]["pending_line_id"] = payload["audio_job"]["line_id"]
        state["audio"]["pending_job"] = payload["audio_job"]
    elif kind == "AudioEnqueued":
        line_id = payload["audio_job"]["line_id"]
        if line_id not in state["audio"]["enqueued_line_ids"]:
            state["audio"]["enqueued_line_ids"].append(line_id)
        state["audio"]["pending_line_id"] = None
        state["audio"]["pending_job"] = None
        state["turn"]["recovery_action"] = "none"
    else:
        raise AssertionError(f"unknown event type: {kind}")
    return state


def safe_projection(state: dict[str, Any]) -> dict[str, Any]:
    if state["world"]["unclassified"]:
        raise IntegrityFailure("unknown_world_field")
    projected = {
        "revision": state["world"]["revision"],
        "hero_hp": state["world"]["hero_hp"],
        "public_facts": list(state["world"]["public_facts"]),
        "narration_text": state["world"]["narration_text"],
        "image_prompt": state["world"]["image_prompt"],
    }
    if SECRET_CANARY in canonical(projected):
        raise IntegrityFailure("secret_canary_in_player_projection")
    return projected


def decide(state: dict[str, Any], cmd: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if cmd["schema_version"] != SCHEMA_VERSION:
        return [], {"status": "rejected", "code": "unsupported_schema"}
    if cmd["room_id"] != ROOM_ID or cmd["turn_id"] != TURN_ID:
        return [], {"status": "rejected", "code": "wrong_aggregate"}
    if cmd["expected_aggregate_version"] != state["aggregate_version"]:
        return [], {
            "status": "rejected",
            "code": "aggregate_version_conflict",
            "actual_version": state["aggregate_version"],
        }

    turn = state["turn"]
    kind = cmd["type"]
    payload = cmd["payload"]
    produced: list[dict[str, Any]] = []

    role = cmd["actor"]["role"]
    surface = cmd["actor"]["surface"]
    if kind in INTERNAL_COMMANDS and (role, surface) != ("coordinator", "server"):
        return [], {"status": "rejected", "code": "unauthorized"}
    if kind == "provider_event" and (role, surface) != ("provider", "server"):
        return [], {"status": "rejected", "code": "unauthorized"}

    if kind == "receive":
        if turn["stage"] != "listening":
            return [], {"status": "rejected", "code": "invalid_stage"}
        produced.append(event("TurnReceived", {"turn_id": TURN_ID}))
    elif kind == "persist_draft":
        if turn["stage"] != "drafting" or payload.get("draft_version") != 1:
            return [], {"status": "rejected", "code": "invalid_stage"}
        produced.append(
            event(
                "DraftPersisted",
                {"draft_version": 1, "draft_text": payload["draft_text"]},
            )
        )
    elif kind == "redraft":
        if turn["stage"] != "awaiting_approval":
            return [], {"status": "rejected", "code": "invalid_stage"}
        expected = turn["draft_version"] + 1
        if payload.get("draft_version") != expected:
            return [], {"status": "rejected", "code": "draft_version_conflict"}
        produced.append(
            event(
                "DraftRevised",
                {"draft_version": expected, "draft_text": payload["draft_text"]},
            )
        )
    elif kind == "approve":
        if turn["stage"] != "awaiting_approval":
            return [], {"status": "rejected", "code": "invalid_stage"}
        if payload.get("draft_version") != turn["draft_version"]:
            return [], {
                "status": "rejected",
                "code": "stale_draft",
                "current_draft_version": turn["draft_version"],
            }
        produced.append(event("ApprovalAccepted", {"draft_version": turn["draft_version"]}))
    elif kind == "start_execution":
        if turn["stage"] != "executing" or turn["execution_attempt_id"] is not None:
            return [], {"status": "rejected", "code": "invalid_stage"}
        produced.append(
            event("ExecutionStarted", {"execution_attempt_id": "exec-turn-0001-a1"})
        )
    elif kind == "commit_world":
        if turn["stage"] != "executing" or turn["execution_attempt_id"] is None:
            return [], {"status": "rejected", "code": "invalid_stage"}
        produced.append(
            event(
                "WorldCommitted",
                {
                    "damage": payload.get("damage", 3),
                    "public_fact": payload.get("public_fact", "hero_was_hit"),
                    "narration_text": payload.get(
                        "narration_text", "The hero is struck for three damage."
                    ),
                    "image_prompt": payload.get(
                        "image_prompt", "A disclosed hero recoils on a stone bridge."
                    ),
                    "inject_unknown_secret": bool(payload.get("inject_unknown_secret")),
                },
            )
        )
    elif kind == "prepare_projection":
        if turn["stage"] != "presenting" or state["projection"]["pending_event"] is not None:
            return [], {"status": "rejected", "code": "invalid_stage"}
        try:
            projection = safe_projection(state)
        except IntegrityFailure as exc:
            produced.append(
                event(
                    "ProjectionFailed",
                    {"error_code": str(exc), "world_revision": state["world"]["revision"]},
                )
            )
        else:
            event_id = f"projection:{TURN_ID}:{state['world']['revision']}"
            envelope = {
                "schema_version": SCHEMA_VERSION,
                "event_id": event_id,
                "room_id": ROOM_ID,
                "turn_id": TURN_ID,
                "aggregate_version": state["aggregate_version"] + 1,
                "type": "player_projection",
                "payload": projection,
            }
            validate_contract(envelope, "PlayerProjectionEnvelope")
            produced.append(
                event("ProjectionReady", {"projection": projection, "envelope": envelope})
            )
    elif kind == "ack_projection":
        pending = state["projection"]["pending_event"]
        if turn["stage"] != "presenting" or pending is None:
            return [], {"status": "rejected", "code": "invalid_stage"}
        if payload.get("event_id") != pending["event_id"]:
            return [], {"status": "rejected", "code": "cursor_conflict"}
        audio_job = {
            "schema_version": SCHEMA_VERSION,
            "line_id": f"line:{TURN_ID}:{state['world']['revision']}",
            "context_id": f"context:{TURN_ID}",
            "turn_id": TURN_ID,
            "text_event_id": pending["event_id"],
            "text": pending["payload"]["narration_text"],
            "status": "pending",
        }
        validate_contract(audio_job, "AudioJob")
        produced.append(
            event(
                "ProjectionAcknowledged",
                {
                    "event_id": pending["event_id"],
                    "audio_job": audio_job,
                },
            )
        )
    elif kind == "enqueue_audio":
        audio_job = state["audio"]["pending_job"]
        if turn["stage"] != "committed" or not audio_job:
            return [], {"status": "rejected", "code": "invalid_stage"}
        validate_contract(audio_job, "AudioJob")
        produced.append(event("AudioEnqueued", {"audio_job": audio_job}))
    elif kind == "provider_event":
        if payload.get("execution_attempt_id") != turn["execution_attempt_id"] or turn[
            "stage"
        ] == "committed":
            return [], {"status": "ignored", "code": "late_provider_event"}
        return [], {"status": "accepted", "code": "provider_observation_only"}
    else:
        return [], {"status": "rejected", "code": "unknown_command"}

    next_state = state
    for produced_event in produced:
        next_state = evolve(next_state, produced_event)
    result = {
        "status": "accepted",
        "code": produced[-1]["type"],
        "turn_id": TURN_ID,
        "aggregate_version": next_state["aggregate_version"],
        "stage": next_state["turn"]["stage"],
        "world_revision": next_state["world"]["revision"],
        "world_mutation_count": next_state["world"]["mutation_count"],
    }
    return produced, result


class Store:
    model_name = "abstract"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def reopen(self) -> "Store":
        self.close()
        return type(self)(self.path)

    def _create_schema(self) -> None:
        raise NotImplementedError

    def state(self) -> dict[str, Any]:
        raise NotImplementedError

    def process(self, cmd: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def publish_projection(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def stats(self) -> dict[str, Any]:
        raise NotImplementedError

    def corrupt_canonical(self) -> None:
        raise NotImplementedError

    def corrupt_recovery_pointer(self) -> None:
        raise NotImplementedError

    def prepare_projection(self) -> dict[str, Any]:
        current = self.state()
        cmd = command(
            f"internal-project:{TURN_ID}:{current['world']['revision']}",
            "prepare_projection",
            current["aggregate_version"],
        )
        return self.process(cmd)

    def ack_projection(self, event_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        current = self.state()
        cmd = command(
            f"ack:{event_id}",
            "ack_projection",
            current["aggregate_version"],
            {"event_id": event_id, "surface": "table", "reducer_version": 1},
        )
        return cmd, self.process(cmd)

    def enqueue_audio(self) -> tuple[dict[str, Any], dict[str, Any]]:
        current = self.state()
        line_id = current["audio"]["pending_line_id"]
        cmd = command(
            f"internal-audio:{line_id}",
            "enqueue_audio",
            current["aggregate_version"],
        )
        return cmd, self.process(cmd)


class EventCheckpointStore(Store):
    model_name = "event_log_checkpoints"
    checkpoint_every = 4

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                event_seq INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_results (
                room_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                result_json TEXT NOT NULL,
                checksum TEXT NOT NULL,
                PRIMARY KEY(room_id, command_id)
            );
            CREATE TABLE IF NOT EXISTS delivery_attempts (
                event_id TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audio_jobs (
                line_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def _event_checksum(event_id: str, event_type: str, payload_json: str) -> str:
        return digest(f"{event_id}|{event_type}|{payload_json}")

    @staticmethod
    def _checkpoint_checksum(event_seq: int, state_json: str) -> str:
        return digest(f"{event_seq}|{state_json}")

    def _load_state(self, *, verify_all: bool = True) -> tuple[dict[str, Any], dict[str, int]]:
        verified = 0
        if verify_all:
            for row in self.connection.execute("SELECT * FROM events ORDER BY seq"):
                verified += 1
                expected = self._event_checksum(
                    row["event_id"], row["event_type"], row["payload_json"]
                )
                if expected != row["checksum"]:
                    raise IntegrityFailure(f"event_checksum:{row['seq']}")
                validate_contract(json.loads(row["payload_json"]), "DurableEventEnvelope")
        checkpoint = self.connection.execute(
            "SELECT * FROM checkpoints WHERE singleton = 1"
        ).fetchone()
        if checkpoint:
            if (
                self._checkpoint_checksum(checkpoint["event_seq"], checkpoint["state_json"])
                != checkpoint["checksum"]
            ):
                raise IntegrityFailure("checkpoint_checksum")
            state = json.loads(checkpoint["state_json"])
            after = checkpoint["event_seq"]
        else:
            state = initial_state()
            after = 0
        replayed = 0
        for row in self.connection.execute(
            "SELECT * FROM events WHERE seq > ? ORDER BY seq", (after,)
        ):
            replayed += 1
            envelope = json.loads(row["payload_json"])
            validate_contract(envelope, "DurableEventEnvelope")
            item = {
                "schema_version": SCHEMA_VERSION,
                "type": envelope["type"],
                "payload": envelope["payload"],
            }
            state = evolve(state, item)
        return state, {"integrity_rows": verified, "replayed_rows": replayed}

    def state(self) -> dict[str, Any]:
        return self._load_state()[0]

    def _stored_result(self, cmd: dict[str, Any]) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM command_results WHERE room_id = ? AND command_id = ?",
            (cmd["room_id"], cmd["command_id"]),
        ).fetchone()
        if not row:
            return None
        fingerprint = cmd["request_digest"]
        if row["fingerprint"] != fingerprint:
            raise IdempotencyConflict(cmd["command_id"])
        if digest(row["result_json"]) != row["checksum"]:
            raise IntegrityFailure("command_result_checksum")
        result = json.loads(row["result_json"])
        validate_contract(result, "CommandResult")
        return result

    def process(self, cmd: dict[str, Any]) -> dict[str, Any]:
        validate_contract(cmd, "CommandEnvelope")
        if request_digest(cmd) != cmd["request_digest"]:
            raise IntegrityFailure("request_digest_mismatch")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            try:
                stored = self._stored_result(cmd)
            except IdempotencyConflict:
                state, _ = self._load_state()
                conflict = command_result(
                    cmd, {"status": "rejected", "code": "idempotency_conflict"}, state
                )
                self.connection.commit()
                return conflict
            if stored is not None:
                self.connection.commit()
                return stored
            state, _ = self._load_state()
            produced, raw_result = decide(state, cmd)
            new_state = state
            last_seq = self.connection.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events"
            ).fetchone()[0]
            for index, produced_event in enumerate(produced, start=1):
                new_state = evolve(new_state, produced_event)
                envelope = durable_event_envelope(cmd, produced_event, new_state, index)
                payload_json = canonical(envelope)
                event_id = envelope["event_id"]
                checksum = self._event_checksum(
                    event_id, produced_event["type"], payload_json
                )
                cursor = self.connection.execute(
                    "INSERT INTO events(event_id,event_type,payload_json,checksum) VALUES(?,?,?,?)",
                    (event_id, produced_event["type"], payload_json, checksum),
                )
                last_seq = cursor.lastrowid
                if produced_event["type"] == "AudioEnqueued":
                    audio_job = produced_event["payload"]["audio_job"]
                    validate_contract(audio_job, "AudioJob")
                    line_id = audio_job["line_id"]
                    audio_json = canonical(audio_job)
                    self.connection.execute(
                        "INSERT OR IGNORE INTO audio_jobs(line_id,payload_json,checksum) VALUES(?,?,?)",
                        (line_id, audio_json, digest(audio_json)),
                    )
            result = command_result(cmd, raw_result, new_state)
            result_json = canonical(result)
            self.connection.execute(
                "INSERT INTO command_results(room_id,command_id,fingerprint,result_json,checksum) "
                "VALUES(?,?,?,?,?)",
                (
                    cmd["room_id"],
                    cmd["command_id"],
                    cmd["request_digest"],
                    result_json,
                    digest(result_json),
                ),
            )
            if produced and last_seq % self.checkpoint_every == 0:
                state_json = canonical(new_state)
                self.connection.execute(
                    "INSERT INTO checkpoints(singleton,event_seq,state_json,checksum) VALUES(1,?,?,?) "
                    "ON CONFLICT(singleton) DO UPDATE SET event_seq=excluded.event_seq, "
                    "state_json=excluded.state_json, checksum=excluded.checksum",
                    (
                        last_seq,
                        state_json,
                        self._checkpoint_checksum(last_seq, state_json),
                    ),
                )
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            raise

    def publish_projection(self) -> dict[str, Any] | None:
        pending = self.state()["projection"]["pending_event"]
        if pending is None:
            return None
        self.connection.execute(
            "INSERT INTO delivery_attempts(event_id,attempts) VALUES(?,1) "
            "ON CONFLICT(event_id) DO UPDATE SET attempts=attempts+1",
            (pending["event_id"],),
        )
        self.connection.commit()
        return copy.deepcopy(pending)

    def stats(self) -> dict[str, Any]:
        _, recovery = self._load_state()
        counts = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "events",
                "checkpoints",
                "command_results",
                "delivery_attempts",
                "audio_jobs",
            )
        }
        return {**counts, **recovery, "database_bytes": self.path.stat().st_size}

    def corrupt_canonical(self) -> None:
        self.connection.execute(
            "UPDATE events SET payload_json = payload_json || ' ' WHERE seq = (SELECT MAX(seq) FROM events)"
        )
        self.connection.commit()

    def corrupt_recovery_pointer(self) -> None:
        self.connection.execute(
            "UPDATE checkpoints SET event_seq = event_seq + 1 WHERE singleton = 1"
        )
        self.connection.commit()


class TransactionalOutboxStore(Store):
    model_name = "transactional_state_dedupe_outbox"

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS aggregate_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                state_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_results (
                room_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                result_json TEXT NOT NULL,
                checksum TEXT NOT NULL,
                PRIMARY KEY(room_id, command_id)
            );
            CREATE TABLE IF NOT EXISTS outbox (
                event_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS delivery_acks (
                surface TEXT PRIMARY KEY,
                event_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audio_jobs (
                line_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
            """
        )
        row = self.connection.execute(
            "SELECT 1 FROM aggregate_state WHERE singleton = 1"
        ).fetchone()
        if not row:
            state_json = canonical(initial_state())
            self.connection.execute(
                "INSERT INTO aggregate_state(singleton,state_json,checksum) VALUES(1,?,?)",
                (state_json, digest(state_json)),
            )
        self.connection.commit()

    def state(self) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT state_json,checksum FROM aggregate_state WHERE singleton = 1"
        ).fetchone()
        if row is None or digest(row["state_json"]) != row["checksum"]:
            raise IntegrityFailure("aggregate_state_checksum")
        return json.loads(row["state_json"])

    def _stored_result(self, cmd: dict[str, Any]) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM command_results WHERE room_id = ? AND command_id = ?",
            (cmd["room_id"], cmd["command_id"]),
        ).fetchone()
        if not row:
            return None
        if row["fingerprint"] != cmd["request_digest"]:
            raise IdempotencyConflict(cmd["command_id"])
        if digest(row["result_json"]) != row["checksum"]:
            raise IntegrityFailure("command_result_checksum")
        result = json.loads(row["result_json"])
        validate_contract(result, "CommandResult")
        return result

    def process(self, cmd: dict[str, Any]) -> dict[str, Any]:
        validate_contract(cmd, "CommandEnvelope")
        if request_digest(cmd) != cmd["request_digest"]:
            raise IntegrityFailure("request_digest_mismatch")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            try:
                stored = self._stored_result(cmd)
            except IdempotencyConflict:
                conflict = command_result(
                    cmd,
                    {"status": "rejected", "code": "idempotency_conflict"},
                    self.state(),
                )
                self.connection.commit()
                return conflict
            if stored is not None:
                self.connection.commit()
                return stored
            state = self.state()
            produced, raw_result = decide(state, cmd)
            new_state = state
            for index, produced_event in enumerate(produced, start=1):
                new_state = evolve(new_state, produced_event)
                envelope = durable_event_envelope(cmd, produced_event, new_state, index)
                payload_json = canonical(envelope)
                self.connection.execute(
                    "INSERT INTO audit_events(event_type,payload_json,checksum) VALUES(?,?,?)",
                    (produced_event["type"], payload_json, digest(payload_json)),
                )
                self._apply_outbox_side_effect(produced_event, new_state)
            state_json = canonical(new_state)
            self.connection.execute(
                "UPDATE aggregate_state SET state_json=?,checksum=? WHERE singleton=1",
                (state_json, digest(state_json)),
            )
            result = command_result(cmd, raw_result, new_state)
            result_json = canonical(result)
            self.connection.execute(
                "INSERT INTO command_results(room_id,command_id,fingerprint,result_json,checksum) "
                "VALUES(?,?,?,?,?)",
                (
                    cmd["room_id"],
                    cmd["command_id"],
                    cmd["request_digest"],
                    result_json,
                    digest(result_json),
                ),
            )
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            raise

    def _apply_outbox_side_effect(
        self, produced_event: dict[str, Any], new_state: dict[str, Any]
    ) -> None:
        kind = produced_event["type"]
        payload = produced_event["payload"]
        if kind == "WorldCommitted":
            task_id = f"project:{TURN_ID}:{new_state['world']['revision']}"
            task_json = canonical({"turn_id": TURN_ID, "task": "project_after_commit"})
            self.connection.execute(
                "INSERT OR IGNORE INTO outbox(event_id,kind,payload_json,checksum,status) "
                "VALUES(?,?,?,?,?)",
                (task_id, "projection_task", task_json, digest(task_json), "pending"),
            )
        elif kind == "ProjectionReady":
            envelope = payload["envelope"]
            payload_json = canonical(envelope)
            self.connection.execute(
                "INSERT OR IGNORE INTO outbox(event_id,kind,payload_json,checksum,status) "
                "VALUES(?,?,?,?,?)",
                (
                    envelope["event_id"],
                    "player_projection",
                    payload_json,
                    digest(payload_json),
                    "pending",
                ),
            )
            self.connection.execute(
                "UPDATE outbox SET status='done' WHERE kind='projection_task' AND status='pending'"
            )
        elif kind == "ProjectionFailed":
            self.connection.execute(
                "UPDATE outbox SET status='error' WHERE kind='projection_task' AND status='pending'"
            )
        elif kind == "ProjectionAcknowledged":
            self.connection.execute(
                "UPDATE outbox SET status='acked' WHERE event_id=?",
                (payload["event_id"],),
            )
            self.connection.execute(
                "INSERT INTO delivery_acks(surface,event_id) VALUES('table',?) "
                "ON CONFLICT(surface) DO UPDATE SET event_id=excluded.event_id",
                (payload["event_id"],),
            )
            audio_job = payload["audio_job"]
            validate_contract(audio_job, "AudioJob")
            audio_payload = canonical(audio_job)
            self.connection.execute(
                "INSERT OR IGNORE INTO outbox(event_id,kind,payload_json,checksum,status) "
                "VALUES(?,?,?,?,?)",
                (
                    f"audio:{audio_job['line_id']}",
                    "audio_enqueue",
                    audio_payload,
                    digest(audio_payload),
                    "pending",
                ),
            )
        elif kind == "AudioEnqueued":
            audio_job = payload["audio_job"]
            validate_contract(audio_job, "AudioJob")
            line_id = audio_job["line_id"]
            audio_json = canonical(audio_job)
            self.connection.execute(
                "INSERT OR IGNORE INTO audio_jobs(line_id,payload_json,checksum) VALUES(?,?,?)",
                (line_id, audio_json, digest(audio_json)),
            )
            self.connection.execute(
                "UPDATE outbox SET status='done' WHERE event_id=?",
                (f"audio:{line_id}",),
            )

    def publish_projection(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM outbox WHERE kind='player_projection' AND status != 'acked' "
            "ORDER BY event_id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        if digest(row["payload_json"]) != row["checksum"]:
            raise IntegrityFailure("outbox_checksum")
        self.connection.execute(
            "UPDATE outbox SET attempts=attempts+1,status='attempted' WHERE event_id=?",
            (row["event_id"],),
        )
        self.connection.commit()
        return json.loads(row["payload_json"])

    def stats(self) -> dict[str, Any]:
        counts = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "aggregate_state",
                "command_results",
                "outbox",
                "delivery_acks",
                "audio_jobs",
                "audit_events",
            )
        }
        return {
            **counts,
            "integrity_rows": 1,
            "replayed_rows": 0,
            "database_bytes": self.path.stat().st_size,
        }

    def corrupt_canonical(self) -> None:
        self.connection.execute(
            "UPDATE aggregate_state SET state_json = state_json || ' ' WHERE singleton=1"
        )
        self.connection.commit()

    def corrupt_recovery_pointer(self) -> None:
        self.connection.execute(
            "UPDATE outbox SET payload_json = payload_json || ' ' "
            "WHERE event_id = (SELECT event_id FROM outbox WHERE kind='player_projection' LIMIT 1)"
        )
        self.connection.commit()


class ProjectionClient:
    def __init__(self) -> None:
        self.projection = {
            "revision": 0,
            "hero_hp": 12,
            "public_facts": [],
            "narration_text": "",
            "image_prompt": "",
        }
        self.seen: set[str] = set()
        self.apply_count = 0

    def apply(self, envelope: dict[str, Any], *, fail: bool = False) -> str:
        event_id = envelope["event_id"]
        if event_id in self.seen:
            return "duplicate"
        if fail:
            raise RuntimeError("synthetic_reducer_failure")
        validate_contract(envelope, "PlayerProjectionEnvelope")
        if set(envelope) != {
            "schema_version",
            "event_id",
            "room_id",
            "turn_id",
            "aggregate_version",
            "type",
            "payload",
        }:
            raise IntegrityFailure("unknown_projection_envelope_field")
        if set(envelope["payload"]) != {
            "revision",
            "hero_hp",
            "public_facts",
            "narration_text",
            "image_prompt",
        }:
            raise IntegrityFailure("unknown_projection_payload_field")
        if SECRET_CANARY in canonical(envelope):
            raise IntegrityFailure("secret_canary_reached_client")
        self.projection = copy.deepcopy(envelope["payload"])
        self.seen.add(event_id)
        self.apply_count += 1
        return "applied"


STORE_TYPES = (EventCheckpointStore, TransactionalOutboxStore)


def issue(store: Store, command_id: str, kind: str, payload: dict[str, Any] | None = None):
    cmd = command(command_id, kind, store.state()["aggregate_version"], payload)
    return cmd, store.process(cmd)


def prefix_to(store: Store, target: str, *, secret_failure: bool = False) -> dict[str, Any]:
    history: dict[str, Any] = {}
    steps = [
        (
            "receive",
            "cmd-receive",
            "receive",
            {"final_transcript_id": "transcript-0001", "text": "Hero crosses the marked cell."},
        ),
        (
            "draft_persist",
            "cmd-draft-v1",
            "persist_draft",
            {"draft_version": 1, "draft_text": "Hero crosses the marked cell."},
        ),
        ("approval", "cmd-approve-v1", "approve", {"draft_version": 1}),
        ("execution_start", "cmd-start", "start_execution", {}),
        (
            "world_commit",
            "cmd-world",
            "commit_world",
            {
                "damage": 3,
                "public_fact": "hero_was_hit",
                "narration_text": "The hero is struck for three damage.",
                "image_prompt": "A disclosed hero recoils on a stone bridge.",
                "inject_unknown_secret": secret_failure,
            },
        ),
    ]
    for stage, command_id, kind, payload in steps:
        cmd, result = issue(store, command_id, kind, payload)
        history[stage] = {"command": cmd, "result": result}
        if stage == target:
            return history
    result = store.prepare_projection()
    history["prepare_projection"] = {"result": result}
    if secret_failure:
        return history
    envelope = store.publish_projection()
    if envelope is None:
        raise AssertionError("projection was not publishable")
    history["outbox_publish"] = {"envelope": envelope}
    if target == "outbox_publish":
        return history
    client = ProjectionClient()
    history["client"] = client
    client.apply(envelope)
    ack_cmd, ack_result = store.ack_projection(envelope["event_id"])
    history["projection_ack"] = {"command": ack_cmd, "result": ack_result}
    if target == "projection_ack":
        return history
    audio_cmd, audio_result = store.enqueue_audio()
    history["audio_enqueue"] = {"command": audio_cmd, "result": audio_result}
    return history


def finish_after_restart(store: Store, crashed_at: str, history: dict[str, Any]) -> ProjectionClient:
    if crashed_at == "receive":
        issue(
            store,
            "cmd-draft-v1",
            "persist_draft",
            {"draft_version": 1, "draft_text": "Hero crosses the marked cell."},
        )
    if crashed_at in {"receive", "draft_persist"}:
        issue(store, "cmd-approve-v1", "approve", {"draft_version": 1})
    if crashed_at in {"receive", "draft_persist", "approval"}:
        issue(store, "cmd-start", "start_execution")
    if crashed_at in {"receive", "draft_persist", "approval", "execution_start"}:
        issue(
            store,
            "cmd-world",
            "commit_world",
            {"damage": 3, "public_fact": "hero_was_hit"},
        )
    if store.state()["turn"]["stage"] == "presenting" and store.state()["projection"][
        "pending_event"
    ] is None:
        store.prepare_projection()
    client = history.get("client") or ProjectionClient()
    if store.state()["turn"]["stage"] == "presenting":
        envelope = store.publish_projection()
        if envelope is None:
            raise AssertionError("projection missing during recovery")
        client.apply(envelope)
        store.ack_projection(envelope["event_id"])
    if store.state()["audio"]["pending_line_id"]:
        store.enqueue_audio()
    return client


def run_fault_case(store_type: type[Store], root: Path, crashed_at: str) -> dict[str, Any]:
    path = root / f"{store_type.model_name}-{crashed_at}.sqlite"
    store = store_type(path)
    history = prefix_to(store, crashed_at)
    before = store.state()
    store = store.reopen()
    recovered = store.state()
    duplicate_equal: bool | None = None
    if crashed_at in history and "command" in history[crashed_at]:
        original = history[crashed_at]
        duplicate_equal = store.process(original["command"]) == original["result"]
    elif crashed_at == "outbox_publish":
        replayed = store.publish_projection()
        duplicate_equal = replayed == history["outbox_publish"]["envelope"]
    client = finish_after_restart(store, crashed_at, history)
    final = store.state()
    passed = all(
        (
            before == recovered,
            duplicate_equal is True,
            final["world"]["mutation_count"] == 1,
            final["world"]["revision"] == 1,
            final["turn"]["stage"] == "committed",
            final["turn"]["recovery_action"] == "none",
            final["projection"]["last_safe"] == client.projection,
            SECRET_CANARY not in canonical(client.projection),
            len(final["audio"]["enqueued_line_ids"]) == 1,
        )
    )
    result = {
        "model": store_type.model_name,
        "scenario": f"crash_after_{crashed_at}",
        "pass": passed,
        "recovered_stage": recovered["turn"]["stage"],
        "recovery_action": recovered["turn"]["recovery_action"],
        "mutation_count_at_reload": recovered["world"]["mutation_count"],
        "duplicate_returned_stored_result": duplicate_equal,
        "final_world_digest": digest(final["world"]),
        "final_projection_digest": digest(final["projection"]["last_safe"]),
        "final_mutation_count": final["world"]["mutation_count"],
        "client_apply_count": client.apply_count,
    }
    store.close()
    return result


def run_edge_cases(store_type: type[Store], root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def fresh(name: str) -> Store:
        return store_type(root / f"{store_type.model_name}-{name}.sqlite")

    store = fresh("out-of-order")
    cmd = command("approve-too-early", "approve", 0, {"draft_version": 1})
    first = store.process(cmd)
    second = store.process(cmd)
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "out_of_order_approval",
            "pass": first == second
            and first["code"] == "invalid_stage"
            and store.state()["world"]["mutation_count"] == 0,
            "stored_code": first["code"],
        }
    )
    store.close()

    store = fresh("capability")
    forged = command(
        "forged-world",
        "commit_world",
        0,
        {"damage": 99, "public_fact": "forged"},
    )
    forged["actor"] = {"actor_id": "player-1", "surface": "table", "role": "player"}
    forged["request_digest"] = request_digest(forged)
    schema_rejected = False
    runtime_rejected = False
    try:
        validate_contract(forged, "CommandEnvelope")
    except ValidationError:
        schema_rejected = True
    try:
        store.process(forged)
    except ValidationError:
        runtime_rejected = True
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "actor_capability_boundary",
            "pass": schema_rejected
            and runtime_rejected
            and store.state()["world"]["mutation_count"] == 0,
            "schema_rejected": schema_rejected,
            "runtime_rejected": runtime_rejected,
        }
    )
    store.close()

    store = fresh("stale-draft")
    issue(
        store,
        "receive",
        "receive",
        {"final_transcript_id": "transcript-stale", "text": "first"},
    )
    issue(
        store,
        "draft-1",
        "persist_draft",
        {"draft_version": 1, "draft_text": "first"},
    )
    issue(store, "draft-2", "redraft", {"draft_version": 2, "draft_text": "second"})
    stale_cmd = command(
        "approve-stale",
        "approve",
        store.state()["aggregate_version"],
        {"draft_version": 1},
    )
    first = store.process(stale_cmd)
    second = store.process(stale_cmd)
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "stale_draft",
            "pass": first == second
            and first["code"] == "stale_draft"
            and store.state()["world"]["mutation_count"] == 0,
            "stored_code": first["code"],
            "current_draft_version": store.state()["turn"]["draft_version"],
        }
    )
    store.close()

    store = fresh("idempotency-conflict")
    original = command(
        "same-id",
        "receive",
        0,
        {"final_transcript_id": "transcript-conflict", "text": "first"},
    )
    store.process(original)
    conflicting = copy.deepcopy(original)
    conflicting["payload"] = {
        "final_transcript_id": "transcript-conflict",
        "text": "different",
    }
    conflicting["request_digest"] = request_digest(conflicting)
    conflict = store.process(conflicting)
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "command_id_payload_conflict",
            "pass": conflict["code"] == "idempotency_conflict"
            and conflict["status"] == "rejected"
            and store.state()["aggregate_version"] == 1,
            "conflict_detected": conflict["code"] == "idempotency_conflict",
        }
    )
    store.close()

    store = fresh("room-scope")
    first_room = command(
        "room-shared-id",
        "receive",
        0,
        {"final_transcript_id": "transcript-room-a", "text": "room a"},
    )
    accepted = store.process(first_room)
    other_room = command(
        "room-shared-id",
        "receive",
        store.state()["aggregate_version"],
        {"final_transcript_id": "transcript-room-b", "text": "room b"},
        room_id="room-other",
    )
    rejected = store.process(other_room)
    repeated = store.process(other_room)
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "room_scoped_command_dedupe",
            "pass": accepted["code"] == "TurnReceived"
            and rejected == repeated
            and rejected["code"] == "wrong_aggregate"
            and rejected["room_id"] == "room-other",
            "first_room_code": accepted["code"],
            "other_room_code": rejected["code"],
        }
    )
    store.close()

    store = fresh("duplicate-world")
    history = prefix_to(store, "audio_enqueue")
    original = history["world_commit"]
    duplicate = store.process(original["command"])
    late_cmd = command(
        "late-provider",
        "provider_event",
        store.state()["aggregate_version"],
        {
            "provider_event_id": "provider-event-late-1",
            "execution_attempt_id": "exec-turn-0001-a1",
            "provider_type": "model",
            "data": {"text": "late"},
        },
    )
    late_first = store.process(late_cmd)
    late_second = store.process(late_cmd)
    state = store.state()
    audio_rows = store.connection.execute("SELECT payload_json FROM audio_jobs").fetchall()
    audio_jobs = [json.loads(row["payload_json"]) for row in audio_rows]
    for audio_job in audio_jobs:
        validate_contract(audio_job, "AudioJob")
    projection = state["projection"]["last_safe"]
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "duplicate_world_and_late_provider_event",
            "pass": duplicate == original["result"]
            and late_first == late_second
            and late_first["code"] == "late_provider_event"
            and state["world"]["mutation_count"] == 1
            and len(audio_jobs) == 1
            and SECRET_CANARY not in canonical(audio_jobs)
            and SECRET_CANARY not in projection["image_prompt"]
            and projection["image_prompt"] != "",
            "mutation_count": state["world"]["mutation_count"],
            "late_code": late_first["code"],
            "audio_job_schema_valid": len(audio_jobs) == 1,
            "canary_in_audio_or_image_prompt": SECRET_CANARY
            in canonical({"audio_jobs": audio_jobs, "image_prompt": projection["image_prompt"]}),
        }
    )
    store.close()

    store = fresh("replay-live")
    prefix_to(store, "world_commit")
    store.prepare_projection()
    replay = store.publish_projection()
    live = store.publish_projection()
    client = ProjectionClient()
    first_apply = client.apply(replay)
    second_apply = client.apply(live)
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "replay_live_overlap",
            "pass": replay == live
            and first_apply == "applied"
            and second_apply == "duplicate"
            and client.apply_count == 1,
            "same_event_id": replay["event_id"] == live["event_id"],
            "client_apply_count": client.apply_count,
        }
    )
    store.close()

    store = fresh("reducer-failure")
    prefix_to(store, "world_commit")
    store.prepare_projection()
    envelope = store.publish_projection()
    client = ProjectionClient()
    failed = False
    try:
        client.apply(envelope, fail=True)
    except RuntimeError:
        failed = True
    unacked = store.state()["projection"]["acked_event_id"] is None
    replay = store.publish_projection()
    applied = client.apply(replay)
    store.ack_projection(replay["event_id"])
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "projection_reducer_failure",
            "pass": failed
            and unacked
            and applied == "applied"
            and client.apply_count == 1
            and store.state()["turn"]["stage"] == "committed",
            "cursor_advanced_on_failure": not unacked,
            "client_apply_count": client.apply_count,
        }
    )
    store.close()

    store = fresh("secret-projection")
    prefix_to(store, "world_commit", secret_failure=True)
    project = store.prepare_projection()
    state = store.state()
    published = store.publish_projection()
    serial = canonical({"result": project, "state": state, "published": published})
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "secret_projection_failure",
            "pass": state["world"]["mutation_count"] == 1
            and state["turn"]["stage"] == "presenting"
            and state["turn"]["recovery_action"] == "repair_projection_schema"
            and state["projection"]["error"] == "unknown_world_field"
            and published is None
            and SECRET_CANARY not in canonical(state["projection"])
            and SECRET_CANARY not in canonical(project),
            "world_committed": state["world"]["mutation_count"] == 1,
            "published": published is not None,
            "projection_error": state["projection"]["error"],
            "canary_in_player_or_result": SECRET_CANARY in serial.replace(
                canonical(state["world"]), ""
            ),
        }
    )
    store.close()

    store = fresh("corruption")
    prefix_to(store, "world_commit")
    store.corrupt_canonical()
    store = store.reopen()
    detected = False
    try:
        store.state()
    except IntegrityFailure:
        detected = True
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "canonical_corruption",
            "pass": detected,
            "corruption_detected": detected,
        }
    )
    store.close()

    store = fresh("recovery-pointer")
    prefix_to(store, "world_commit")
    store.prepare_projection()
    store.corrupt_recovery_pointer()
    store = store.reopen()
    detected = False
    try:
        if store_type is EventCheckpointStore:
            store.state()
        else:
            store.publish_projection()
    except IntegrityFailure:
        detected = True
    results.append(
        {
            "model": store_type.model_name,
            "scenario": "recovery_pointer_corruption",
            "pass": detected,
            "corruption_detected": detected,
        }
    )
    store.close()
    return results


def run_golden_stats(store_type: type[Store], root: Path) -> dict[str, Any]:
    store = store_type(root / f"{store_type.model_name}-golden.sqlite")
    history = prefix_to(store, "audio_enqueue")
    state = store.state()
    stats = store.stats()
    result = {
        "model": store_type.model_name,
        "pass": state["world"]["mutation_count"] == 1
        and state["turn"]["stage"] == "committed"
        and state["turn"]["recovery_action"] == "none",
        "world_digest": digest(state["world"]),
        "projection_digest": digest(state["projection"]["last_safe"]),
        "stored_world_result": history["world_commit"]["result"],
        "stats": stats,
    }
    store.close()
    return result


def run_matrix(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    golden: list[dict[str, Any]] = []
    for store_type in STORE_TYPES:
        cases.extend(run_fault_case(store_type, root, stage) for stage in FAULT_STAGES)
        cases.extend(run_edge_cases(store_type, root))
        golden.append(run_golden_stats(store_type, root))
    by_model = {
        store_type.model_name: {
            "passed": sum(
                1 for case in cases if case["model"] == store_type.model_name and case["pass"]
            ),
            "total": sum(1 for case in cases if case["model"] == store_type.model_name),
        }
        for store_type in STORE_TYPES
    }
    all_pass = all(case["pass"] for case in cases) and all(item["pass"] for item in golden)
    return {
        "schema_version": SCHEMA_VERSION,
        "selection_rule_predeclared": SELECTION_RULE,
        "fault_stages": list(FAULT_STAGES),
        "all_pass": all_pass,
        "summary": by_model,
        "golden_path": golden,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keep-databases", type=Path)
    args = parser.parse_args()
    if args.keep_databases:
        result = run_matrix(args.keep_databases)
    else:
        with tempfile.TemporaryDirectory(prefix="r4-durability-") as directory:
            result = run_matrix(Path(directory))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
