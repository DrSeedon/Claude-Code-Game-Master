#!/usr/bin/env python3
"""Synthetic research probe for the #11 unified-core contract.

This is deliberately not product code.  It uses a tiny SQLite model and fixed
fixtures to falsify authority, atomicity, branch/reveal, tactical, and
projection claims made by ``core-adr.md`` without calling external providers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


SECRET_CANARY = "CORE_SECRET_CANARY_377"
GM_CANARY = "CORE_GM_ONLY_CANARY_377"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def campaign_definition() -> dict[str, Any]:
    definition = {
        "schema_version": 1,
        "campaign_id": "synthetic-core",
        "facts": {
            "fact:seal": {
                "truth": f"The bronze seal names the traitor. {SECRET_CANARY}",
                "public_fact": "The bronze seal identifies a traitor.",
                "classification": "secret",
                "mandatory": True,
            },
            "fact:warden-warning": {
                "truth": "The warden warns that the bridge is trapped.",
                "public_fact": "The bridge is trapped.",
                "classification": "secret",
                "mandatory": False,
            },
        },
        "routes": {
            "route:warden": {
                "fact_id": "fact:seal",
                "carrier": {"kind": "npc", "id": "npc:warden"},
                "reveal_fact_ids": ["fact:seal"],
                "requires": {"npc_status": ["npc:warden", "alive_present"]},
            },
            "route:archive": {
                "fact_id": "fact:seal",
                "carrier": {"kind": "location", "id": "location:archive"},
                "reveal_fact_ids": ["fact:seal"],
                "requires": {"location_available": "location:archive"},
            },
            "route:warning": {
                "fact_id": "fact:warden-warning",
                "carrier": {"kind": "npc", "id": "npc:warden"},
                "reveal_fact_ids": ["fact:warden-warning"],
                "requires": {"npc_status": ["npc:warden", "alive_present"]},
            },
        },
        "threats": {
            "threat:collapse": {"maximum": 3, "thresholds": [1, 3]},
        },
        "endings": {
            "ending:loss": {
                "terminal_class": "loss",
                "priority": 100,
                "when": {"clock_at_least": ["threat:collapse", 3]},
            },
            "ending:success": {
                "terminal_class": "success",
                "priority": 50,
                "when": {"fact_revealed": "fact:seal", "boss_defeated": True},
            },
        },
        "templates": {
            "enemy:raider": {"kind": "enemy", "hp": 7, "ac": 12, "speed": 6},
        },
        "terrain_transitions": {
            "terrain-transition:drop-brazier": {
                "feature_id": "feature:bridge-brazier",
                "from_state": "intact",
                "to_state": "toppled",
                "cells": [[5, 3]],
                "kind": "debris",
                "movement_cost": 2,
                "blocks_los": False,
            }
        },
        "consequence_templates": {
            "consequence:bridge-noise": {
                "clock_id": "threat:collapse",
                "public_cue": "The fallen brazier echoes through the ruins.",
            }
        },
        "locations": ["location:archive"],
        "gm_note": GM_CANARY,
    }
    definition["definition_hash"] = digest(definition)
    return definition


def starter_heroes() -> dict[str, dict[str, Any]]:
    return {
        "hero:guardian": {"class": "fighter", "level": 3, "role": "defender"},
        "hero:fury": {"class": "barbarian", "level": 3, "role": "striker"},
        "hero:shadow": {"class": "rogue", "level": 3, "role": "scout"},
        "hero:beacon": {"class": "cleric", "level": 3, "role": "healer"},
        "hero:arcanist": {"class": "wizard", "level": 3, "role": "controller"},
        "hero:voice": {"class": "bard", "level": 3, "role": "support"},
    }


def ruleset_bundle() -> dict[str, Any]:
    bundle = {
        "ruleset_id": "srd-5.2.1-mvp-1",
        "rules_engine_version": 1,
        "effect_templates": {
            "effect-template:hazard": {
                "kind": "hazard",
                "max_cells": 4,
                "duration_rounds": 2,
            },
            "effect-template:light": {
                "kind": "light",
                "max_cells": 16,
                "duration_rounds": 10,
            },
        },
    }
    bundle["bundle_hash"] = digest(bundle)
    return bundle


def resolve_death_save(entity: dict[str, Any], raw: int) -> None:
    """Apply the pinned SRD death-save result without hidden adjustment."""
    if entity.get("kind") != "hero" or entity.get("lifecycle") != "downed" or not 1 <= raw <= 20:
        raise Rejected("invalid_death_save")
    saves = entity.setdefault("death_saves", {"successes": 0, "failures": 0})
    if raw == 20:
        entity.update(hp=1, lifecycle="alive", death_saves={"successes": 0, "failures": 0})
        return
    if raw == 1:
        saves["failures"] += 2
    elif raw >= 10:
        saves["successes"] += 1
    else:
        saves["failures"] += 1
    if saves["failures"] >= 3:
        entity["lifecycle"] = "dead"
    elif saves["successes"] >= 3:
        entity["lifecycle"] = "stable"


def initial_state(definition: dict[str, Any]) -> dict[str, Any]:
    heroes = starter_heroes()
    ruleset = ruleset_bundle()
    entities: dict[str, dict[str, Any]] = {
        hero_id: {
            **profile,
            "kind": "hero",
            "position": [1, index + 1],
            "hp": 12,
            "hp_max": 12,
            "ac": 13,
            "speed": 6,
            "conditions": [],
            "lifecycle": "alive",
        }
        for index, (hero_id, profile) in enumerate(heroes.items())
    }
    entities.update(
        {
            "npc:warden": {
                "kind": "npc",
                "position": [3, 3],
                "status": "alive_present",
                "lifecycle": "alive",
                "hp": 4,
                "hp_max": 4,
            },
            "enemy:boss": {
                "kind": "enemy",
                "position": [7, 3],
                "hp": 10,
                "hp_max": 10,
                "ac": 12,
                "speed": 6,
                "conditions": [],
                "lifecycle": "alive",
            },
        }
    )
    return {
        "schema_version": 1,
        "campaign_definition_id": definition["campaign_id"],
        "campaign_definition_hash": definition["definition_hash"],
        "ruleset_id": ruleset["ruleset_id"],
        "rules_engine_version": ruleset["rules_engine_version"],
        "ruleset_bundle_hash": ruleset["bundle_hash"],
        "aggregate_version": 0,
        "world_revision": 0,
        "control_revision": 0,
        "run_state": "running",
        "turn": {
            "turn_id": None,
            "stage": "listening",
            "draft_version": 0,
            "plan_id": None,
            "plan_digest": None,
            "plan": None,
            "approval_nonce": None,
            "approved": False,
            "provider_attempt_id": None,
            "provider_attempt_status": None,
            "execution_attempt_id": None,
            "recovery_action": "none",
            "intent_summary": None,
            "approval_card": None,
        },
        "narrative": {
            "reveals": {},
            "engaged_routes": [],
            "npc_status": {"npc:warden": "alive_present"},
            "clocks": {"threat:collapse": 0},
            "consequence_ledger": [],
            "terminal_ending": None,
        },
        "tactical": {
            "board_id": "board:bridge",
            "width": 10,
            "height": 8,
            "walls": [[[4, 1], [4, 2]]],
            "terrain": {},
            "terrain_feature_state": {"feature:bridge-brazier": "intact"},
            "entities": entities,
            "effects": {},
            "combat": {
                "active": True,
                "mode": "side_phases",
                "round": 1,
                "phase": "players",
                "acted": [],
                "classic_order": [],
                "classic_index": 0,
            },
            "resources": {
                hero_id: {"action": 1, "bonus_action": 1, "reaction": 1, "movement": 6}
                for hero_id in heroes
            },
            "pending_rolls": {},
            "roll_ledger": {},
        },
        "presentation": {"public_atoms": [], "last_result": None},
    }


def validate_definition(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    facts = definition.get("facts", {})
    routes = definition.get("routes", {})
    locations = set(definition.get("locations", []))
    templates = definition.get("templates", {})
    transitions = definition.get("terrain_transitions", {})
    consequence_templates = definition.get("consequence_templates", {})
    for route_id, route in routes.items():
        fact_id = route.get("fact_id")
        if fact_id not in facts:
            errors.append(f"{route_id}:missing_fact:{fact_id}")
        for reveal_id in route.get("reveal_fact_ids", []):
            if reveal_id not in facts:
                errors.append(f"{route_id}:missing_reveal:{reveal_id}")
        if fact_id not in route.get("reveal_fact_ids", []):
            errors.append(f"{route_id}:conclusion_not_revealed:{fact_id}")
        carrier = route.get("carrier", {})
        if carrier.get("kind") == "location" and carrier.get("id") not in locations:
            errors.append(f"{route_id}:missing_location:{carrier.get('id')}")
        if carrier.get("kind") not in {"npc", "location", "object", "event"}:
            errors.append(f"{route_id}:invalid_carrier_kind")
    for fact_id, fact in facts.items():
        if not fact.get("mandatory"):
            continue
        fact_routes = [route for route in routes.values() if route.get("fact_id") == fact_id]
        if len(fact_routes) < 2:
            errors.append(f"{fact_id}:no_alternate_route")
        if fact_routes and all(route.get("carrier", {}).get("kind") == "npc" for route in fact_routes):
            errors.append(f"{fact_id}:no_durable_route")
    for template_id, template in templates.items():
        if template.get("kind") not in {"enemy", "npc", "object"}:
            errors.append(f"{template_id}:invalid_template_kind")
    for transition_id, transition in transitions.items():
        if not transition.get("feature_id") or transition.get("from_state") == transition.get("to_state"):
            errors.append(f"{transition_id}:invalid_terrain_transition")
        if not transition.get("cells"):
            errors.append(f"{transition_id}:missing_terrain_cells")
    for template_id, template in consequence_templates.items():
        if template.get("clock_id") not in definition.get("threats", {}):
            errors.append(f"{template_id}:missing_consequence_clock")
    if definition.get("definition_hash") != digest({k: v for k, v in definition.items() if k != "definition_hash"}):
        errors.append("definition_hash_mismatch")
    return errors


def line_clear(origin: list[int], destination: list[int], walls: list[list[list[int]]]) -> bool:
    if origin == destination:
        return True
    blocked = {tuple(point) for segment in walls for point in segment}
    x0, y0 = origin
    x1, y1 = destination
    steps = max(abs(x1 - x0), abs(y1 - y0))
    for step in range(1, steps):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        if (x, y) in blocked:
            return False
    return True


def route_eligible(state: dict[str, Any], definition: dict[str, Any], route_id: str) -> bool:
    route = definition["routes"][route_id]
    requirement = route.get("requires", {})
    if "npc_status" in requirement:
        npc_id, expected = requirement["npc_status"]
        if state["narrative"]["npc_status"].get(npc_id) != expected:
            return False
    if "location_available" in requirement:
        if requirement["location_available"] not in definition["locations"]:
            return False
    return True


def evaluate_ending(state: dict[str, Any], definition: dict[str, Any]) -> str | None:
    matches: list[tuple[int, str]] = []
    for ending_id, ending in definition["endings"].items():
        condition = ending["when"]
        matched = True
        if "clock_at_least" in condition:
            clock_id, threshold = condition["clock_at_least"]
            matched &= state["narrative"]["clocks"].get(clock_id, 0) >= threshold
        if "fact_revealed" in condition:
            matched &= condition["fact_revealed"] in state["narrative"]["reveals"]
        if condition.get("boss_defeated"):
            matched &= state["tactical"]["entities"]["enemy:boss"]["lifecycle"] == "defeated"
        if matched:
            matches.append((ending["priority"], ending_id))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        raise ValueError("ambiguous_terminal_ending")
    return matches[0][1]


class Rejected(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ResearchStore:
    def __init__(self, path: Path, *, rng: random.Random | None = None):
        self.path = path
        self.definition = campaign_definition()
        self.ruleset = ruleset_bundle()
        self.rng = rng or random.Random(3771101)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS room_aggregate (
                room_id TEXT PRIMARY KEY,
                aggregate_version INTEGER NOT NULL,
                world_revision INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_results (
                room_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                request_digest TEXT NOT NULL,
                result_json TEXT NOT NULL,
                result_hash TEXT NOT NULL,
                PRIMARY KEY(room_id, command_id)
            );
            CREATE TABLE IF NOT EXISTS domain_events (
                event_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                aggregate_version INTEGER NOT NULL,
                event_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outbox (
                event_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                aggregate_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS projection_batches (
                batch_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                aggregate_version INTEGER NOT NULL,
                table_json TEXT NOT NULL,
                scene_json TEXT NOT NULL,
                admin_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cursors (
                room_id TEXT NOT NULL,
                consumer_id TEXT NOT NULL,
                surface TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                PRIMARY KEY(room_id, consumer_id, surface)
            );
            """
        )
        if self.connection.execute("SELECT 1 FROM room_aggregate WHERE room_id='room:1'").fetchone() is None:
            state = initial_state(self.definition)
            payload = canonical(state)
            self.connection.execute(
                "INSERT INTO room_aggregate VALUES(?,?,?,?,?)",
                ("room:1", 0, 0, payload, digest(state)),
            )
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def state(self) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT state_json,state_hash FROM room_aggregate WHERE room_id='room:1'"
        ).fetchone()
        state = json.loads(row["state_json"])
        if digest(state) != row["state_hash"]:
            raise RuntimeError("aggregate_checksum_mismatch")
        return state

    def counts(self) -> dict[str, int]:
        return {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("command_results", "domain_events", "outbox", "projection_batches", "cursors")
        }

    def submit(
        self,
        request: dict[str, Any],
        authority: dict[str, Any],
        *,
        failpoint: str | None = None,
    ) -> dict[str, Any]:
        """R4 order after closed-schema/session transport admission."""
        allowed = {
            "schema_version",
            "command_id",
            "kind",
            "expected_aggregate_version",
            "turn_id",
            "draft_version",
            "approval_nonce",
            "args",
        }
        if (
            set(request) - allowed
            or request.get("schema_version") != 1
            or not isinstance(request.get("command_id"), str)
        ):
            raise Rejected("invalid_schema")
        request_digest = digest(request)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                "SELECT * FROM command_results WHERE room_id=? AND command_id=?",
                (authority.get("room_id"), request["command_id"]),
            ).fetchone()
            if existing:
                if existing["request_digest"] != request_digest:
                    self.connection.rollback()
                    return {
                        "status": "rejected",
                        "code": "command_id_conflict",
                        "command_id": request["command_id"],
                        "world_mutation_count": 0,
                        "events": [],
                    }
                result = json.loads(existing["result_json"])
                self.connection.rollback()
                return result

            if authority.get("room_id") != "room:1" or authority.get("surface") not in {"table", "internal"}:
                return self._store_rejection(request, request_digest, "unauthorized")
            kind = request["kind"]
            table_allowed = {
                "turn.approve",
                "action.standard_move",
                "roll.confirm",
                "phase.end_players",
                "projection.ack",
            }
            internal_allowed = {
                "turn.prepare",
                "turn.begin_adjudication",
                "turn.cancel_adjudication",
                "turn.execute",
                "phase.execute_world",
                "recovery.prepare_projection",
            }
            if (authority["surface"] == "table" and kind not in table_allowed) or (
                authority["surface"] == "internal" and kind not in internal_allowed
            ):
                return self._store_rejection(request, request_digest, "unauthorized")
            required_internal_actor = {
                "turn.prepare": "coordinator",
                "turn.begin_adjudication": "coordinator",
                "turn.cancel_adjudication": "coordinator",
                "turn.execute": "kernel",
                "phase.execute_world": "kernel",
                "recovery.prepare_projection": "projector",
            }
            if (
                authority["surface"] == "internal"
                and authority.get("actor_id") != required_internal_actor[kind]
            ):
                return self._store_rejection(request, request_digest, "unauthorized")

            state = self.state()
            if request["expected_aggregate_version"] != state["aggregate_version"]:
                return self._store_rejection(request, request_digest, "version_conflict")
            if state["narrative"]["terminal_ending"] is not None:
                return self._store_rejection(request, request_digest, "room_terminal")

            next_state = copy.deepcopy(state)
            events, world_changed = self._dispatch(next_state, request, authority)
            next_state["aggregate_version"] += 1
            if world_changed:
                next_state["world_revision"] += 1
                next_state["narrative"]["terminal_ending"] = evaluate_ending(next_state, self.definition)
            result = {
                "status": "committed",
                "code": "ok",
                "command_id": request["command_id"],
                "aggregate_version": next_state["aggregate_version"],
                "world_revision": next_state["world_revision"],
                "world_mutation_count": int(world_changed),
                "events": [event["type"] for event in events],
            }
            result_json = canonical(result)
            self.connection.execute(
                "INSERT INTO command_results VALUES(?,?,?,?,?)",
                ("room:1", request["command_id"], request_digest, result_json, digest(result)),
            )
            if failpoint == "after_result_before_event":
                raise RuntimeError("injected_crash_before_commit")
            event_id = f"domain:{request['command_id']}"
            self.connection.execute(
                "INSERT INTO domain_events VALUES(?,?,?,?,?)",
                (event_id, "room:1", request["command_id"], next_state["aggregate_version"], canonical(events)),
            )
            if failpoint == "after_event_before_state":
                raise RuntimeError("injected_crash_before_commit")
            state_json = canonical(next_state)
            self.connection.execute(
                "UPDATE room_aggregate SET aggregate_version=?,world_revision=?,state_json=?,state_hash=? WHERE room_id='room:1'",
                (
                    next_state["aggregate_version"],
                    next_state["world_revision"],
                    state_json,
                    digest(next_state),
                ),
            )
            if failpoint == "after_state_before_outbox":
                raise RuntimeError("injected_crash_before_commit")
            task = {
                "aggregate_version": next_state["aggregate_version"],
                "world_revision": next_state["world_revision"],
            }
            self.connection.execute(
                "INSERT INTO outbox VALUES(?,?,?,?,?,?,?)",
                (
                    f"projection-task:{next_state['aggregate_version']}",
                    "room:1",
                    "projection_task",
                    next_state["aggregate_version"],
                    canonical(task),
                    digest(task),
                    "pending",
                ),
            )
            if failpoint == "after_outbox_before_commit":
                raise RuntimeError("injected_crash_before_commit")
            self.connection.commit()
            if failpoint == "after_commit_before_return":
                raise RuntimeError("injected_crash_after_commit")
            return result
        except Rejected as error:
            if self.connection.in_transaction:
                self.connection.rollback()
            return self._store_rejection(request, request_digest, error.code)
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _store_rejection(self, request: dict[str, Any], request_digest: str, code: str) -> dict[str, Any]:
        result = {
            "status": "rejected",
            "code": code,
            "command_id": request["command_id"],
            "world_mutation_count": 0,
            "events": [],
        }
        self.connection.execute(
            "INSERT INTO command_results VALUES(?,?,?,?,?)",
            ("room:1", request["command_id"], request_digest, canonical(result), digest(result)),
        )
        self.connection.commit()
        return result

    def _dispatch(
        self,
        state: dict[str, Any],
        request: dict[str, Any],
        authority: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], bool]:
        kind = request["kind"]
        args = request.get("args", {})
        turn = state["turn"]
        tactical = state["tactical"]
        events: list[dict[str, Any]] = []

        if kind == "turn.begin_adjudication":
            if turn["stage"] not in {"listening", "drafting"}:
                raise Rejected("invalid_stage")
            if turn["stage"] == "drafting" and turn["provider_attempt_status"] == "running":
                raise Rejected("provider_attempt_active")
            provider_attempt_id = args.get("provider_attempt_id")
            safe_intent = args.get("safe_intent")
            if not isinstance(provider_attempt_id, str) or not isinstance(safe_intent, str):
                raise Rejected("invalid_provider_attempt")
            turn.update(
                turn_id=request["turn_id"],
                stage="drafting",
                draft_version=request["draft_version"],
                plan_id=None,
                plan_digest=None,
                plan=None,
                approval_nonce=None,
                approved=False,
                provider_attempt_id=provider_attempt_id,
                provider_attempt_status="running",
                execution_attempt_id=None,
                recovery_action="retry_provider",
                intent_summary=safe_intent,
                approval_card=None,
            )
            events.append({"type": "ProviderAttemptStarted", "provider_attempt_id": provider_attempt_id})
            return events, False

        if kind == "turn.cancel_adjudication":
            if (
                turn["stage"] != "drafting"
                or turn["provider_attempt_status"] != "running"
                or args.get("provider_attempt_id") != turn["provider_attempt_id"]
            ):
                raise Rejected("provider_attempt_inactive")
            turn.update(provider_attempt_status="cancelled", recovery_action="none")
            events.append({"type": "ProviderAttemptCancelled", "provider_attempt_id": turn["provider_attempt_id"]})
            return events, False

        if kind == "turn.prepare":
            plan = args.get("plan")
            if not isinstance(plan, dict):
                raise Rejected("invalid_plan")
            if plan.get("kind") == "unusual" and (
                turn["stage"] != "drafting"
                or turn["provider_attempt_status"] != "running"
                or plan.get("provider_attempt_id") != turn["provider_attempt_id"]
            ):
                raise Rejected("provider_attempt_mismatch")
            if plan.get("kind") == "standard" and turn["stage"] != "listening":
                raise Rejected("invalid_stage")
            self._validate_plan(state, plan, binding_request=request)
            safe_intent = args.get("safe_intent")
            if not isinstance(safe_intent, str) or not safe_intent.strip():
                raise Rejected("invalid_safe_intent")
            if plan["kind"] == "unusual" and safe_intent != turn["intent_summary"]:
                raise Rejected("plan_binding_mismatch")
            approval_nonce = args.get("approval_nonce")
            if not isinstance(approval_nonce, str) or len(approval_nonce) < 32:
                raise Rejected("invalid_approval")
            approval_card = self._build_approval_card(plan, approval_nonce, safe_intent)
            turn.update(
                turn_id=request["turn_id"],
                stage="awaiting_approval",
                draft_version=request["draft_version"],
                plan_id=plan["plan_id"],
                plan_digest=digest(plan),
                plan=plan,
                approval_nonce=approval_nonce,
                approved=False,
                provider_attempt_status=("completed" if plan["kind"] == "unusual" else None),
                execution_attempt_id=None,
                recovery_action="wait_for_approval",
                intent_summary=safe_intent,
                approval_card=approval_card,
            )
            events.append({"type": "PlanPrepared", "plan_id": plan["plan_id"]})
            return events, False

        if kind == "turn.approve":
            if turn["stage"] != "awaiting_approval":
                raise Rejected("invalid_stage")
            if request.get("turn_id") != turn["turn_id"] or request.get("draft_version") != turn["draft_version"]:
                raise Rejected("stale_draft")
            if request.get("approval_nonce") != turn["approval_nonce"]:
                raise Rejected("invalid_approval")
            turn.update(
                stage="executing",
                approved=True,
                approval_nonce=None,
                execution_attempt_id=f"attempt:{turn['turn_id']}:{turn['draft_version']}",
                recovery_action="retry_uncommitted_execution",
            )
            turn["approval_card"]["approval_nonce"] = None
            turn["approval_card"]["status"] = "approved"
            events.append({"type": "PlanApproved", "plan_digest": turn["plan_digest"]})
            return events, False

        if kind == "turn.execute":
            if turn["stage"] != "executing" or not turn["approved"]:
                raise Rejected("invalid_stage")
            if request.get("turn_id") != turn["turn_id"]:
                raise Rejected("wrong_turn")
            self._apply_plan(
                state,
                turn["plan"],
                events,
                command_id=request["command_id"],
                resulting_world_revision=state["world_revision"] + 1,
            )
            has_pending_roll = any(
                pending["status"] == "awaiting_confirmation"
                for pending in tactical["pending_rolls"].values()
            )
            turn.update(
                stage="awaiting_roll" if has_pending_roll else "presenting",
                recovery_action="wait_for_roll" if has_pending_roll else "resume_projection",
            )
            public_atoms = self._render_public_atoms(events)
            state["presentation"]["last_result"] = public_atoms[-1] if public_atoms else None
            state["presentation"]["public_atoms"] = public_atoms
            events.append({"type": "PlanExecuted", "plan_digest": turn["plan_digest"]})
            return events, True

        if kind == "projection.ack":
            batch_id = args.get("batch_id")
            consumer_id = args.get("consumer_id")
            cursor = self.connection.execute(
                "SELECT batch_id FROM cursors WHERE room_id='room:1' AND consumer_id=? AND surface='table'",
                (consumer_id,),
            ).fetchone()
            if cursor is None or cursor["batch_id"] != batch_id:
                raise Rejected("projection_not_rendered")
            if turn["stage"] == "presenting":
                turn.update(
                    turn_id=None,
                    stage="listening",
                    draft_version=0,
                    plan_id=None,
                    plan_digest=None,
                    plan=None,
                    approval_nonce=None,
                    approved=False,
                    provider_attempt_id=None,
                    provider_attempt_status=None,
                    execution_attempt_id=None,
                    recovery_action="none",
                    intent_summary=None,
                    approval_card=None,
                )
            elif turn["stage"] == "awaiting_roll":
                turn["recovery_action"] = "wait_for_roll"
            else:
                raise Rejected("invalid_stage")
            events.append({"type": "ProjectionAcknowledged", "batch_id": batch_id})
            return events, False

        if kind == "action.standard_move":
            actor_id = authority.get("actor_id")
            destination = args.get("destination")
            standard_plan = {
                "plan_id": f"plan:{request['command_id']}",
                "kind": "standard",
                "campaign_definition_hash": state["campaign_definition_hash"],
                "ruleset_id": state["ruleset_id"],
                "rules_engine_version": state["rules_engine_version"],
                "ruleset_bundle_hash": state["ruleset_bundle_hash"],
                "turn_id": f"turn:{request['command_id']}",
                "draft_version": 1,
                "expected_aggregate_version": request["expected_aggregate_version"],
                "provider_attempt_id": None,
                "operations": [
                    {
                        "op": "move_entity",
                        "entity_id": actor_id,
                        "destination": destination,
                    }
                ],
            }
            self._apply_plan(
                state,
                standard_plan,
                events,
                command_id=request["command_id"],
                resulting_world_revision=state["world_revision"] + 1,
            )
            return events, True

        if kind == "roll.confirm":
            roll_id = args.get("roll_id")
            pending = tactical["pending_rolls"].get(roll_id)
            if not pending or pending["status"] != "awaiting_confirmation":
                raise Rejected("no_pending_roll")
            if pending["actor_id"] != authority.get("actor_id"):
                raise Rejected("wrong_actor")
            raw = args.get("raw")
            if not isinstance(raw, int) or not 1 <= raw <= pending["sides"]:
                raise Rejected("invalid_roll")
            total = raw + pending["modifier"]
            record = {
                **pending,
                "raw": raw,
                "total": total,
                "status": "confirmed",
                "visibility": "public",
                "authorized_effects": [],
                "consumed_effect_ids": [],
            }
            if total >= pending["target"]:
                record["authorized_effects"].append(
                    {
                        "effect_id": f"{roll_id}:damage",
                        "op": "apply_damage",
                        "target_id": pending["target_id"],
                        "amount": pending["damage"],
                        "damage_type": "slashing",
                    }
                )
            tactical["roll_ledger"][roll_id] = record
            pending["status"] = "consumed"
            if total >= pending["target"]:
                self._apply_operation(
                    state,
                    {
                        "op": "apply_damage",
                        "target_id": pending["target_id"],
                        "amount": pending["damage"],
                        "damage_type": "slashing",
                        "resolution_id": roll_id,
                        "resolution_effect_id": f"{roll_id}:damage",
                    },
                    events,
                )
            tactical["combat"]["acted"].append(pending["actor_id"])
            turn.update(stage="presenting", recovery_action="resume_projection")
            events.append({"type": "PhysicalRollConfirmed", "roll_id": roll_id, "raw": raw, "total": total})
            return events, True

        if kind == "phase.end_players":
            combat = tactical["combat"]
            if combat["phase"] != "players":
                raise Rejected("invalid_phase")
            if combat["mode"] == "side_phases":
                combat["phase"] = "world"
            else:
                active_actor = combat["classic_order"][combat["classic_index"]]
                if authority.get("actor_id") != active_actor or active_actor not in starter_heroes():
                    raise Rejected("wrong_initiative_actor")
                if active_actor not in combat["acted"]:
                    combat["acted"].append(active_actor)
                self._advance_classic_cursor(tactical)
            events.append({"type": "CombatPhaseAdvanced", "phase": combat["phase"]})
            return events, True

        if kind == "phase.execute_world":
            combat = tactical["combat"]
            if combat["phase"] != "world":
                raise Rejected("invalid_phase")
            if combat["mode"] == "classic_initiative":
                active_actor = combat["classic_order"][combat["classic_index"]]
                if active_actor != "enemy:boss":
                    raise Rejected("wrong_initiative_actor")
            raw = self.rng.randint(1, 20)
            roll_id = (
                f"enemy-roll:r{combat['round']}:i{combat['classic_index']}"
                if combat["mode"] == "classic_initiative"
                else f"enemy-roll:r{combat['round']}"
            )
            total = raw + 3
            tactical["roll_ledger"][roll_id] = {
                "roll_id": roll_id,
                "actor_id": "enemy:boss",
                "raw": raw,
                "modifier": 3,
                "total": total,
                "visibility": "public",
                "status": "resolved",
                "authorized_effects": (
                    [
                        {
                            "effect_id": f"{roll_id}:damage",
                            "op": "apply_damage",
                            "target_id": "hero:guardian",
                            "amount": 3,
                            "damage_type": "slashing",
                        }
                    ]
                    if total >= tactical["entities"]["hero:guardian"]["ac"]
                    else []
                ),
                "consumed_effect_ids": [],
            }
            if total >= tactical["entities"]["hero:guardian"]["ac"]:
                self._apply_operation(
                    state,
                    {
                        "op": "apply_damage",
                        "target_id": "hero:guardian",
                        "amount": 3,
                        "damage_type": "slashing",
                        "resolution_id": roll_id,
                        "resolution_effect_id": f"{roll_id}:damage",
                    },
                    events,
                )
            if combat["mode"] == "side_phases":
                combat.update(phase="players", round=combat["round"] + 1, acted=[])
                self._refresh_round_resources(tactical)
            else:
                self._advance_classic_cursor(tactical)
            events.append({"type": "EnemyRollPublished", "roll_id": roll_id, "raw": raw, "total": total})
            events.append({"type": "CombatPhaseAdvanced", "phase": combat["phase"]})
            return events, True

        if kind == "recovery.prepare_projection":
            raise Rejected("not_domain_command")
        raise Rejected("unknown_command")

    @staticmethod
    def _refresh_round_resources(tactical: dict[str, Any]) -> None:
        for hero_id in starter_heroes():
            tactical["resources"][hero_id].update(action=1, bonus_action=1, reaction=1, movement=6)

    def _advance_classic_cursor(self, tactical: dict[str, Any]) -> None:
        combat = tactical["combat"]
        order = combat["classic_order"]
        if not order:
            raise Rejected("invalid_initiative_order")
        combat["classic_index"] += 1
        if combat["classic_index"] == len(order):
            combat["classic_index"] = 0
            combat["round"] += 1
            combat["acted"] = []
            self._refresh_round_resources(tactical)
        next_actor = order[combat["classic_index"]]
        combat["phase"] = "world" if next_actor == "enemy:boss" else "players"

    def _validate_plan(
        self,
        state: dict[str, Any],
        plan: Any,
        *,
        binding_request: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(plan, dict) or set(plan) != {
            "plan_id",
            "kind",
            "campaign_definition_hash",
            "ruleset_id",
            "rules_engine_version",
            "ruleset_bundle_hash",
            "turn_id",
            "draft_version",
            "expected_aggregate_version",
            "provider_attempt_id",
            "operations",
        }:
            raise Rejected("invalid_plan")
        if plan["kind"] not in {"standard", "unusual"}:
            raise Rejected("invalid_plan")
        if (
            plan["campaign_definition_hash"] != state["campaign_definition_hash"]
            or plan["ruleset_id"] != state["ruleset_id"]
            or plan["rules_engine_version"] != state["rules_engine_version"]
            or plan["ruleset_bundle_hash"] != state["ruleset_bundle_hash"]
        ):
            raise Rejected("plan_binding_mismatch")
        if plan["kind"] == "unusual" and not isinstance(plan["provider_attempt_id"], str):
            raise Rejected("plan_binding_mismatch")
        if plan["kind"] == "standard" and plan["provider_attempt_id"] is not None:
            raise Rejected("plan_binding_mismatch")
        if binding_request is not None and (
            plan["turn_id"] != binding_request.get("turn_id")
            or plan["draft_version"] != binding_request.get("draft_version")
            or plan["expected_aggregate_version"] != binding_request.get("expected_aggregate_version")
        ):
            raise Rejected("plan_binding_mismatch")
        if not isinstance(plan["operations"], list) or not 1 <= len(plan["operations"]) <= 16:
            raise Rejected("invalid_plan")
        trial = copy.deepcopy(state)
        trial_events: list[dict[str, Any]] = []
        for operation in plan["operations"]:
            self._apply_operation(trial, operation, trial_events)

    def _apply_plan(
        self,
        state: dict[str, Any],
        plan: dict[str, Any],
        events: list[dict[str, Any]],
        *,
        command_id: str,
        resulting_world_revision: int,
    ) -> None:
        self._validate_plan(state, plan)
        for operation in plan["operations"]:
            self._apply_operation(
                state,
                operation,
                events,
                command_id=command_id,
                resulting_world_revision=resulting_world_revision,
            )

    def _render_public_atoms(self, events: list[dict[str, Any]]) -> list[str]:
        atoms: list[str] = []
        for event in events:
            event_type = event["type"]
            if event_type == "FactsRevealed":
                atoms.extend(
                    self.definition["facts"][fact_id]["public_fact"]
                    for fact_id in event["fact_ids"]
                )
            elif event_type == "TerrainChanged":
                atoms.append("The battlefield changes.")
            elif event_type == "PhysicalRollRequested":
                atoms.append("A physical roll is required.")
            elif event_type == "CombatModeSelected":
                atoms.append("The combat order is set.")
            elif event_type == "DamageApplied":
                atoms.append("The attack deals damage.")
        return atoms

    def _build_approval_card(
        self,
        plan: dict[str, Any],
        approval_nonce: str,
        safe_intent: str,
    ) -> dict[str, Any]:
        visible_effects: list[str] = []
        declared_stakes: list[str] = []
        declared_check: dict[str, Any] | None = None
        for operation in plan["operations"]:
            op = operation["op"]
            if op == "set_terrain_feature":
                visible_effects.append("The authored terrain feature may change.")
            elif op == "reveal_fact_via_route":
                visible_effects.append("A clue may be discovered.")
            elif op == "open_physical_roll":
                declared_check = {
                    "kind": operation["kind"],
                    "die": f"d{operation['sides']}",
                    "modifier": operation["modifier"],
                    "target": operation["target"],
                }
            elif op == "schedule_consequence":
                declared_stakes.append(
                    self.definition["consequence_templates"][operation["template_id"]]["public_cue"]
                )
        return {
            "turn_id": plan["turn_id"],
            "draft_version": plan["draft_version"],
            "plan_digest": digest(plan),
            "approval_nonce": approval_nonce,
            "status": "awaiting_approval",
            "intent_summary": safe_intent,
            "declared_costs": ["action"],
            "declared_check": declared_check,
            "declared_stakes": declared_stakes,
            "visible_effects": visible_effects,
        }

    @staticmethod
    def _consume_resolution_effect(
        tactical: dict[str, Any],
        operation: dict[str, Any],
    ) -> None:
        resolution = tactical["roll_ledger"].get(operation["resolution_id"])
        if resolution is None or resolution.get("status") not in {"confirmed", "resolved"}:
            raise Rejected("invalid_resolution")
        effect_id = operation["resolution_effect_id"]
        if effect_id in resolution.get("consumed_effect_ids", []):
            raise Rejected("resolution_effect_consumed")
        expected = next(
            (
                effect
                for effect in resolution.get("authorized_effects", [])
                if effect.get("effect_id") == effect_id
            ),
            None,
        )
        received = {
            key: value
            for key, value in operation.items()
            if key not in {"resolution_id", "resolution_effect_id"}
        }
        if expected is None or {
            key: value for key, value in expected.items() if key != "effect_id"
        } != received:
            raise Rejected("resolution_effect_mismatch")
        resolution.setdefault("consumed_effect_ids", []).append(effect_id)

    def _apply_operation(
        self,
        state: dict[str, Any],
        operation: dict[str, Any],
        events: list[dict[str, Any]],
        *,
        command_id: str = "command:validation",
        resulting_world_revision: int | None = None,
    ) -> None:
        tactical = state["tactical"]
        narrative = state["narrative"]
        op = operation.get("op")
        operation_shapes: dict[str, tuple[set[str], set[str]]] = {
            "move_entity": ({"op", "entity_id", "destination"}, {"op", "entity_id", "destination"}),
            "apply_damage": (
                {"op", "target_id", "amount", "damage_type", "resolution_id", "resolution_effect_id"},
                {"op", "target_id", "amount", "damage_type", "resolution_id", "resolution_effect_id"},
            ),
            "apply_healing": (
                {"op", "target_id", "amount", "resolution_id", "resolution_effect_id"},
                {"op", "target_id", "amount", "resolution_id", "resolution_effect_id"},
            ),
            "set_condition": (
                {"op", "target_id", "condition", "active", "resolution_id", "resolution_effect_id"},
                {"op", "target_id", "condition", "active", "resolution_id", "resolution_effect_id"},
            ),
            "spend_resource": ({"op", "actor_id", "resource", "amount"}, {"op", "actor_id", "resource", "amount"}),
            "create_effect": ({"op", "effect_id", "template_id", "cells"}, {"op", "effect_id", "template_id", "cells"}),
            "set_terrain_feature": ({"op", "transition_id"}, {"op", "transition_id"}),
            "spawn_from_template": ({"op", "entity_id", "template_id", "position"}, {"op", "entity_id", "template_id", "position"}),
            "despawn_entity": ({"op", "entity_id", "reason"}, {"op", "entity_id", "reason"}),
            "set_npc_status": ({"op", "npc_id", "status"}, {"op", "npc_id", "status"}),
            "reveal_fact_via_route": ({"op", "route_id"}, {"op", "route_id"}),
            "advance_clock": ({"op", "clock_id", "amount"}, {"op", "clock_id", "amount"}),
            "schedule_consequence": ({"op", "template_id"}, {"op", "template_id"}),
            "open_physical_roll": (
                {"op", "roll_id", "actor_id", "kind", "sides", "modifier", "target", "target_id"},
                {"op", "roll_id", "actor_id", "kind", "sides", "modifier", "target", "target_id", "damage"},
            ),
            "advance_combat_mode": ({"op", "mode"}, {"op", "mode", "order"}),
        }
        shape = operation_shapes.get(op)
        if shape is None:
            raise Rejected("unknown_operation")
        required, allowed = shape
        if not required <= set(operation) <= allowed:
            raise Rejected("invalid_operation_schema")
        if op == "move_entity":
            entity = tactical["entities"].get(operation.get("entity_id"))
            destination = operation.get("destination")
            if entity is None or not isinstance(destination, list) or len(destination) != 2:
                raise Rejected("invalid_reference")
            origin = entity["position"]
            distance = max(abs(destination[0] - origin[0]), abs(destination[1] - origin[1]))
            resources = tactical["resources"].get(operation["entity_id"])
            combat = tactical["combat"]
            if combat["phase"] != "players" or operation["entity_id"] in combat["acted"]:
                raise Rejected("not_actor_turn")
            if combat["mode"] == "classic_initiative" and (
                not combat["classic_order"]
                or combat["classic_order"][combat["classic_index"]] != operation["entity_id"]
            ):
                raise Rejected("wrong_initiative_actor")
            if resources is None or distance > resources["movement"]:
                raise Rejected("movement_budget")
            if not (0 <= destination[0] < tactical["width"] and 0 <= destination[1] < tactical["height"]):
                raise Rejected("off_board")
            if not line_clear(origin, destination, tactical["walls"]):
                raise Rejected("blocked_path")
            occupied = {
                tuple(item["position"])
                for entity_id, item in tactical["entities"].items()
                if entity_id != operation["entity_id"]
                and item.get("position") is not None
                and item.get("lifecycle") != "removed"
            }
            if tuple(destination) in occupied:
                raise Rejected("occupied")
            entity["position"] = destination
            resources["movement"] -= distance
            events.append(
                {
                    "type": "EntityMoved",
                    "entity_id": operation["entity_id"],
                    "destination": destination,
                    "movement_spent": distance,
                }
            )
            return
        if op == "apply_damage":
            self._consume_resolution_effect(tactical, operation)
            target = tactical["entities"].get(operation.get("target_id"))
            amount = operation.get("amount")
            if target is None or not isinstance(amount, int) or amount <= 0:
                raise Rejected("invalid_damage")
            before = target["hp"]
            target["hp"] = max(0, before - amount)
            if target["hp"] == 0:
                if target["kind"] == "hero":
                    target["lifecycle"] = "downed"
                    target["death_saves"] = {"successes": 0, "failures": 0}
                else:
                    target["lifecycle"] = "defeated"
            events.append({"type": "DamageApplied", "target_id": operation["target_id"], "amount": amount})
            return
        if op == "apply_healing":
            self._consume_resolution_effect(tactical, operation)
            target = tactical["entities"].get(operation.get("target_id"))
            amount = operation.get("amount")
            if target is None or not isinstance(amount, int) or amount <= 0:
                raise Rejected("invalid_healing")
            target["hp"] = min(target["hp_max"], target["hp"] + amount)
            if target.get("lifecycle") == "downed" and target["hp"] > 0:
                target["lifecycle"] = "alive"
                target.pop("death_saves", None)
            events.append({"type": "HealingApplied", "target_id": operation["target_id"]})
            return
        if op == "set_condition":
            self._consume_resolution_effect(tactical, operation)
            target = tactical["entities"].get(operation.get("target_id"))
            condition = operation.get("condition")
            active = operation.get("active")
            if target is None or condition not in {"prone", "grappled", "restrained", "poisoned", "unconscious"}:
                raise Rejected("invalid_condition")
            conditions = target.setdefault("conditions", [])
            if active and condition not in conditions:
                conditions.append(condition)
            if not active and condition in conditions:
                conditions.remove(condition)
            events.append({"type": "ConditionChanged", "target_id": operation["target_id"]})
            return
        if op == "spend_resource":
            actor_id = operation.get("actor_id")
            resource = operation.get("resource")
            amount = operation.get("amount")
            pool = tactical["resources"].get(actor_id)
            if pool is None or resource not in pool or not isinstance(amount, int) or amount <= 0 or pool[resource] < amount:
                raise Rejected("insufficient_resource")
            pool[resource] -= amount
            events.append({"type": "ResourceSpent", "actor_id": actor_id, "resource": resource})
            return
        if op == "create_effect":
            effect_id = operation.get("effect_id")
            template = self.ruleset["effect_templates"].get(operation.get("template_id"))
            cells = operation.get("cells")
            if (
                effect_id in tactical["effects"]
                or template is None
                or not isinstance(cells, list)
                or not 1 <= len(cells) <= template["max_cells"]
            ):
                raise Rejected("invalid_effect")
            tactical["effects"][effect_id] = {
                "kind": template["kind"],
                "cells": cells,
                "duration_rounds": template["duration_rounds"],
                "active": True,
            }
            events.append({"type": "EffectCreated", "effect_id": effect_id})
            return
        if op == "set_terrain_feature":
            transition_id = operation.get("transition_id")
            transition = self.definition["terrain_transitions"].get(transition_id)
            if transition is None:
                raise Rejected("invalid_terrain")
            feature_id = transition["feature_id"]
            if tactical["terrain_feature_state"].get(feature_id) != transition["from_state"]:
                raise Rejected("invalid_terrain_transition")
            cells = transition["cells"]
            for cell in cells:
                tactical["terrain"][f"{cell[0]},{cell[1]}"] = {
                    "kind": transition["kind"],
                    "movement_cost": transition["movement_cost"],
                    "blocks_los": transition["blocks_los"],
                }
            tactical["terrain_feature_state"][feature_id] = transition["to_state"]
            events.append(
                {
                    "type": "TerrainChanged",
                    "transition_id": transition_id,
                    "feature_id": feature_id,
                    "cell_count": len(cells),
                }
            )
            return
        if op == "spawn_from_template":
            template = self.definition["templates"].get(operation.get("template_id"))
            entity_id = operation.get("entity_id")
            if template is None or entity_id in tactical["entities"]:
                raise Rejected("invalid_spawn")
            tactical["entities"][entity_id] = {**copy.deepcopy(template), "position": operation["position"], "hp_max": template["hp"], "lifecycle": "alive", "conditions": []}
            events.append({"type": "EntitySpawned", "entity_id": entity_id})
            return
        if op == "despawn_entity":
            target = tactical["entities"].get(operation.get("entity_id"))
            if target is None or target.get("kind") == "hero":
                raise Rejected("invalid_despawn")
            target["lifecycle"] = "removed"
            target["position"] = None
            events.append({"type": "EntityDespawned", "entity_id": operation["entity_id"]})
            return
        if op == "set_npc_status":
            npc_id = operation.get("npc_id")
            status = operation.get("status")
            if npc_id not in narrative["npc_status"] or status not in {"alive_present", "alive_absent", "dead"}:
                raise Rejected("invalid_npc_state")
            narrative["npc_status"][npc_id] = status
            tactical["entities"][npc_id]["status"] = status
            events.append({"type": "NpcStatusChanged", "npc_id": npc_id, "status": status})
            return
        if op == "reveal_fact_via_route":
            route_id = operation.get("route_id")
            route = self.definition["routes"].get(route_id)
            if route is None or not route_eligible(state, self.definition, route_id):
                raise Rejected("route_ineligible")
            if route_id in narrative["engaged_routes"]:
                raise Rejected("route_already_used")
            for fact_id in route["reveal_fact_ids"]:
                narrative["reveals"][fact_id] = {
                    "route_id": route_id,
                    "audience": "room_players",
                    "command_id": command_id,
                    "world_revision": (
                        state["world_revision"] + 1
                        if resulting_world_revision is None
                        else resulting_world_revision
                    ),
                }
            narrative["engaged_routes"].append(route_id)
            events.append({"type": "FactsRevealed", "route_id": route_id, "fact_ids": route["reveal_fact_ids"]})
            return
        if op == "advance_clock":
            clock_id = operation.get("clock_id")
            amount = operation.get("amount")
            clock = self.definition["threats"].get(clock_id)
            if clock is None or not isinstance(amount, int) or amount <= 0:
                raise Rejected("invalid_clock")
            narrative["clocks"][clock_id] = min(clock["maximum"], narrative["clocks"][clock_id] + amount)
            events.append({"type": "ThreatClockAdvanced", "clock_id": clock_id})
            return
        if op == "schedule_consequence":
            template_id = operation.get("template_id")
            if template_id not in self.definition["consequence_templates"]:
                raise Rejected("invalid_consequence")
            instance_id = f"{template_id}:cause:{command_id}"
            if instance_id not in narrative["consequence_ledger"]:
                narrative["consequence_ledger"].append(instance_id)
                events.append(
                    {
                        "type": "ConsequenceScheduled",
                        "template_id": template_id,
                        "instance_id": instance_id,
                    }
                )
            return
        if op == "open_physical_roll":
            roll_id = operation.get("roll_id")
            actor_id = operation.get("actor_id")
            if roll_id in tactical["pending_rolls"] or actor_id not in starter_heroes():
                raise Rejected("invalid_pending_roll")
            tactical["pending_rolls"][roll_id] = {
                "roll_id": roll_id,
                "actor_id": actor_id,
                "kind": operation.get("kind", "attack"),
                "sides": operation.get("sides", 20),
                "modifier": operation.get("modifier", 0),
                "target": operation.get("target", 10),
                "target_id": operation.get("target_id"),
                "damage": operation.get("damage", 1),
                "status": "awaiting_confirmation",
            }
            events.append({"type": "PhysicalRollRequested", "roll_id": roll_id})
            return
        if op == "advance_combat_mode":
            mode = operation.get("mode")
            if mode not in {"side_phases", "classic_initiative"} or tactical["combat"]["round"] != 1 or tactical["combat"]["acted"]:
                raise Rejected("combat_mode_locked")
            tactical["combat"]["mode"] = mode
            if mode == "classic_initiative":
                order = operation.get("order")
                if not isinstance(order, list) or set(order) != set(starter_heroes()) | {"enemy:boss"}:
                    raise Rejected("invalid_initiative_order")
                tactical["combat"]["classic_order"] = order
            events.append({"type": "CombatModeSelected", "mode": mode})
            return
        raise Rejected("unknown_operation")

    @staticmethod
    def _validate_projection_shape(batch: dict[str, Any]) -> None:
        def exact(value: dict[str, Any], keys: set[str]) -> None:
            if not isinstance(value, dict) or set(value) != keys:
                raise Rejected("projection_schema_failure")

        exact(batch, {"table", "scene", "admin"})
        table = batch["table"]
        scene = batch["scene"]
        admin = batch["admin"]
        exact(
            table,
            {
                "schema",
                "aggregate_version",
                "world_revision",
                "board",
                "combat",
                "pending_rolls",
                "public_rolls",
                "revealed_facts",
                "last_result",
                "approval_card",
                "legal_action_hints",
                "resources",
                "public_events",
            },
        )
        exact(table["board"], {"board_id", "width", "height", "terrain", "entities", "effects"})
        exact(
            table["combat"],
            {"active", "mode", "round", "phase", "acted", "classic_order", "classic_index"},
        )
        for terrain in table["board"]["terrain"].values():
            exact(terrain, {"kind", "movement_cost", "blocks_los"})
        for entity in table["board"]["entities"].values():
            allowed = {"kind", "position", "hp", "hp_max", "conditions", "lifecycle", "status", "role"}
            if not {"kind", "position", "lifecycle"} <= set(entity) <= allowed:
                raise Rejected("projection_schema_failure")
        for effect in table["board"]["effects"].values():
            exact(effect, {"kind", "cells", "duration_rounds", "active"})
        for pending in table["pending_rolls"].values():
            exact(pending, {"roll_id", "actor_id", "kind", "sides", "modifier", "target", "status"})
        for roll in table["public_rolls"].values():
            exact(roll, {"actor_id", "raw", "modifier", "total"})
        approval_card = table["approval_card"]
        if approval_card is not None:
            exact(
                approval_card,
                {
                    "turn_id",
                    "draft_version",
                    "plan_digest",
                    "approval_nonce",
                    "status",
                    "intent_summary",
                    "declared_costs",
                    "declared_check",
                    "declared_stakes",
                    "visible_effects",
                },
            )
            if approval_card["declared_check"] is not None:
                exact(approval_card["declared_check"], {"kind", "die", "modifier", "target"})
        for resources in table["resources"].values():
            if not set(resources) <= {"action", "bonus_action", "reaction", "movement"}:
                raise Rejected("projection_schema_failure")
        exact(
            scene,
            {"schema", "aggregate_version", "world_revision", "public_atoms", "revealed_facts", "public_rolls"},
        )
        exact(
            admin,
            {"schema", "aggregate_version", "world_revision", "run_state", "coordinator", "projection_health"},
        )
        exact(admin["coordinator"], {"stage", "recovery_action", "turn_id"})

    @staticmethod
    def _validate_projection_family(family: dict[str, Any]) -> None:
        if set(family) != {
            "projection_batch_id",
            "aggregate_version",
            "world_revision",
            "table",
            "scene",
            "admin",
        }:
            raise Rejected("projection_family_mismatch")
        expected = (family["aggregate_version"], family["world_revision"])
        for surface in ("table", "scene", "admin"):
            projection = family[surface]
            if (projection["aggregate_version"], projection["world_revision"]) != expected:
                raise Rejected("projection_family_mismatch")

    def build_projection_batch(
        self,
        *,
        inject_secret: bool = False,
        inject_unknown: bool = False,
    ) -> dict[str, Any]:
        state = self.state()
        revealed = {
            fact_id: self.definition["facts"][fact_id]["public_fact"]
            for fact_id in state["narrative"]["reveals"]
        }
        visible_entities = {
            entity_id: {
                key: value
                for key, value in entity.items()
                if key in {"kind", "position", "hp", "hp_max", "conditions", "lifecycle", "status", "role"}
            }
            for entity_id, entity in state["tactical"]["entities"].items()
            if entity.get("lifecycle") != "removed"
        }
        public_rolls = {
            roll_id: {key: record[key] for key in ("actor_id", "raw", "modifier", "total")}
            for roll_id, record in state["tactical"]["roll_ledger"].items()
            if record.get("visibility") == "public" or record.get("status") == "confirmed"
        }
        pending_rolls = {
            roll_id: {
                key: record[key]
                for key in ("roll_id", "actor_id", "kind", "sides", "modifier", "target", "status")
            }
            for roll_id, record in state["tactical"]["pending_rolls"].items()
            if record.get("status") == "awaiting_confirmation"
        }
        public_resources = {
            actor_id: {
                key: value
                for key, value in resources.items()
                if key in {"action", "bonus_action", "reaction", "movement"}
            }
            for actor_id, resources in state["tactical"]["resources"].items()
            if actor_id in starter_heroes()
        }
        legal_action_hints = (
            ["approve", "redraft"]
            if state["turn"]["stage"] == "awaiting_approval"
            else ["move", "action", "master"]
        )
        table = {
            "schema": "table.v1",
            "aggregate_version": state["aggregate_version"],
            "world_revision": state["world_revision"],
            "board": {
                "board_id": state["tactical"]["board_id"],
                "width": state["tactical"]["width"],
                "height": state["tactical"]["height"],
                "terrain": state["tactical"]["terrain"],
                "entities": visible_entities,
                "effects": state["tactical"]["effects"],
            },
            "combat": state["tactical"]["combat"],
            "pending_rolls": pending_rolls,
            "public_rolls": public_rolls,
            "revealed_facts": revealed,
            "last_result": state["presentation"]["last_result"],
            "approval_card": copy.deepcopy(state["turn"]["approval_card"]),
            "legal_action_hints": legal_action_hints,
            "resources": public_resources,
            "public_events": copy.deepcopy(state["presentation"]["public_atoms"]),
        }
        scene = {
            "schema": "scene.v1",
            "aggregate_version": state["aggregate_version"],
            "world_revision": state["world_revision"],
            "public_atoms": state["presentation"]["public_atoms"],
            "revealed_facts": revealed,
            "public_rolls": public_rolls,
        }
        admin = {
            "schema": "admin.v1",
            "aggregate_version": state["aggregate_version"],
            "world_revision": state["world_revision"],
            "run_state": state["run_state"],
            "coordinator": {
                "stage": state["turn"]["stage"],
                "recovery_action": state["turn"]["recovery_action"],
                "turn_id": state["turn"]["turn_id"],
            },
            "projection_health": "ok",
        }
        if inject_secret:
            scene["public_atoms"].append(self.definition["facts"]["fact:seal"]["truth"])
        if inject_unknown:
            scene["unsafe"] = "apparently harmless new field"
        batch_payload = {"table": table, "scene": scene, "admin": admin}
        self._validate_projection_shape(batch_payload)
        serialized = canonical(batch_payload)
        if SECRET_CANARY in serialized or GM_CANARY in serialized:
            raise Rejected("secret_projection_failure")
        batch_id = f"batch:{state['aggregate_version']}"
        family = {
            "projection_batch_id": batch_id,
            "aggregate_version": state["aggregate_version"],
            "world_revision": state["world_revision"],
            **batch_payload,
        }
        self._validate_projection_family(family)
        self.connection.execute("BEGIN IMMEDIATE")
        self.connection.execute(
            "INSERT OR IGNORE INTO projection_batches VALUES(?,?,?,?,?,?,?)",
            (
                batch_id,
                "room:1",
                state["aggregate_version"],
                canonical(table),
                canonical(scene),
                canonical(admin),
                digest(batch_payload),
            ),
        )
        self.connection.execute(
            "UPDATE outbox SET status='done' WHERE kind='projection_task' AND aggregate_version<=?",
            (state["aggregate_version"],),
        )
        self.connection.commit()
        return family

    def reconnect_snapshot(self) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM projection_batches WHERE room_id='room:1' ORDER BY aggregate_version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise Rejected("projection_unavailable")
        table = json.loads(row["table_json"])
        family = {
            "projection_batch_id": row["batch_id"],
            "aggregate_version": row["aggregate_version"],
            "world_revision": table["world_revision"],
            "table": table,
            "scene": json.loads(row["scene_json"]),
            "admin": json.loads(row["admin_json"]),
        }
        self._validate_projection_family(family)
        self._validate_projection_shape({key: family[key] for key in ("table", "scene", "admin")})
        return family

    def ack_projection(self, consumer_id: str, surface: str, batch_id: str, *, render_ok: bool) -> None:
        if surface not in {"table", "scene", "admin"} or not render_ok:
            return
        if self.connection.execute("SELECT 1 FROM projection_batches WHERE batch_id=?", (batch_id,)).fetchone() is None:
            raise Rejected("unknown_batch")
        self.connection.execute(
            "INSERT INTO cursors VALUES(?,?,?,?) ON CONFLICT(room_id,consumer_id,surface) DO UPDATE SET batch_id=excluded.batch_id",
            ("room:1", consumer_id, surface, batch_id),
        )
        self.connection.commit()


def command(
    command_id: str,
    kind: str,
    version: int,
    *,
    args: dict[str, Any] | None = None,
    turn_id: str | None = None,
    draft_version: int | None = None,
    approval_nonce: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "command_id": command_id,
        "kind": kind,
        "expected_aggregate_version": version,
        "args": args or {},
    }
    if turn_id is not None:
        result["turn_id"] = turn_id
    if draft_version is not None:
        result["draft_version"] = draft_version
    if approval_nonce is not None:
        result["approval_nonce"] = approval_nonce
    return result


def run_probe(root: Path) -> dict[str, Any]:
    definition = campaign_definition()
    assertions: dict[str, bool] = {}
    assertions["definition_valid"] = validate_definition(definition) == []
    broken = copy.deepcopy(definition)
    broken["routes"]["route:archive"]["reveal_fact_ids"] = []
    broken["definition_hash"] = digest({k: v for k, v in broken.items() if k != "definition_hash"})
    assertions["definition_linter_rejects_dangling_conclusion"] = any(
        "conclusion_not_revealed" in item for item in validate_definition(broken)
    )
    broken_routes = copy.deepcopy(definition)
    del broken_routes["routes"]["route:archive"]
    broken_routes["definition_hash"] = digest({k: v for k, v in broken_routes.items() if k != "definition_hash"})
    assertions["definition_linter_requires_durable_alternate"] = any(
        "no_durable_route" in item or "no_alternate_route" in item
        for item in validate_definition(broken_routes)
    )
    assertions["six_level_three_heroes"] = len(starter_heroes()) == 6 and all(
        hero["level"] == 3 for hero in starter_heroes().values()
    )
    death_cases = {
        "natural_one": {"raw": 1, "saves": {"successes": 0, "failures": 1}, "lifecycle": "dead", "hp": 0},
        "natural_twenty": {"raw": 20, "saves": {"successes": 0, "failures": 0}, "lifecycle": "alive", "hp": 1},
        "third_success": {"raw": 10, "saves": {"successes": 2, "failures": 0}, "lifecycle": "stable", "hp": 0},
        "third_failure": {"raw": 9, "saves": {"successes": 0, "failures": 2}, "lifecycle": "dead", "hp": 0},
    }
    death_results: dict[str, dict[str, Any]] = {}
    for case, expected in death_cases.items():
        hero = {
            "kind": "hero",
            "lifecycle": "downed",
            "hp": 0,
            "death_saves": copy.deepcopy(expected["saves"]),
        }
        resolve_death_save(hero, expected["raw"])
        death_results[case] = hero
    assertions["death_save_edges_are_deterministic"] = all(
        death_results[case]["lifecycle"] == expected["lifecycle"]
        and death_results[case]["hp"] == expected["hp"]
        for case, expected in death_cases.items()
    )

    standard = ResearchStore(root / "standard.sqlite")
    standard_result = standard.submit(
        command(
            "cmd:standard-move:1",
            "action.standard_move",
            0,
            args={"destination": [2, 1]},
        ),
        {"room_id": "room:1", "surface": "table", "actor_id": "hero:guardian"},
    )
    standard_state = standard.state()
    assertions["standard_action_uses_typed_kernel"] = (
        standard_result["world_mutation_count"] == 1
        and standard_state["tactical"]["entities"]["hero:guardian"]["position"] == [2, 1]
        and standard_state["tactical"]["resources"]["hero:guardian"]["movement"] == 5
        and standard_result["events"] == ["EntityMoved"]
    )
    standard.close()

    resolution = ResearchStore(root / "resolution.sqlite")
    resolution_state = initial_state(definition)
    resolution_state["tactical"]["roll_ledger"]["roll:binding"] = {
        "roll_id": "roll:binding",
        "actor_id": "hero:guardian",
        "raw": 17,
        "modifier": 5,
        "total": 22,
        "visibility": "public",
        "status": "confirmed",
        "authorized_effects": [
            {
                "effect_id": "effect:binding:damage",
                "op": "apply_damage",
                "target_id": "enemy:boss",
                "amount": 4,
                "damage_type": "slashing",
            }
        ],
        "consumed_effect_ids": [],
    }
    exact_effect = {
        "op": "apply_damage",
        "target_id": "enemy:boss",
        "amount": 4,
        "damage_type": "slashing",
        "resolution_id": "roll:binding",
        "resolution_effect_id": "effect:binding:damage",
    }
    negative_resolution_codes: list[str] = []
    for mutation in ({"target_id": "hero:guardian"}, {"amount": 40}):
        candidate_state = copy.deepcopy(resolution_state)
        try:
            resolution._apply_operation(candidate_state, {**exact_effect, **mutation}, [])
        except Rejected as error:
            negative_resolution_codes.append(error.code)
        if candidate_state != resolution_state:
            negative_resolution_codes.append("mutated")
    failed_state = copy.deepcopy(resolution_state)
    failed_state["tactical"]["roll_ledger"]["roll:binding"]["authorized_effects"] = []
    try:
        resolution._apply_operation(failed_state, exact_effect, [])
    except Rejected as error:
        negative_resolution_codes.append(error.code)
    exact_state = copy.deepcopy(resolution_state)
    resolution._apply_operation(exact_state, exact_effect, [])
    after_exact = copy.deepcopy(exact_state)
    try:
        resolution._apply_operation(exact_state, exact_effect, [])
    except Rejected as error:
        negative_resolution_codes.append(error.code)
    assertions["roll_effect_is_exactly_bound_and_consumed_once"] = (
        negative_resolution_codes
        == [
            "resolution_effect_mismatch",
            "resolution_effect_mismatch",
            "resolution_effect_mismatch",
            "resolution_effect_consumed",
        ]
        and after_exact["tactical"]["entities"]["enemy:boss"]["hp"] == 6
        and exact_state == after_exact
    )
    resolution.close()

    cancelled = ResearchStore(root / "cancelled-provider.sqlite")
    cancelled_authority = {"room_id": "room:1", "surface": "internal", "actor_id": "coordinator"}
    cancelled.submit(
        command(
            "cmd:cancelled:begin",
            "turn.begin_adjudication",
            0,
            turn_id="turn:cancelled",
            draft_version=1,
            args={
                "provider_attempt_id": "provider-attempt:cancelled:1",
                "safe_intent": "Inspect the bridge mechanism.",
            },
        ),
        cancelled_authority,
    )
    cancelled.submit(
        command(
            "cmd:cancelled:cancel",
            "turn.cancel_adjudication",
            1,
            turn_id="turn:cancelled",
            draft_version=1,
            args={"provider_attempt_id": "provider-attempt:cancelled:1"},
        ),
        cancelled_authority,
    )
    cancelled_plan = {
        "plan_id": "plan:cancelled",
        "kind": "unusual",
        "campaign_definition_hash": cancelled.state()["campaign_definition_hash"],
        "ruleset_id": cancelled.state()["ruleset_id"],
        "rules_engine_version": cancelled.state()["rules_engine_version"],
        "ruleset_bundle_hash": cancelled.state()["ruleset_bundle_hash"],
        "turn_id": "turn:cancelled",
        "draft_version": 1,
        "expected_aggregate_version": 2,
        "provider_attempt_id": "provider-attempt:cancelled:1",
        "operations": [{"op": "reveal_fact_via_route", "route_id": "route:archive"}],
    }
    cancelled_prepare = command(
        "cmd:cancelled:late",
        "turn.prepare",
        2,
        turn_id="turn:cancelled",
        draft_version=1,
        args={
            "plan": cancelled_plan,
            "approval_nonce": "z" * 32,
            "safe_intent": "Inspect the bridge mechanism.",
        },
    )
    cancelled_result = cancelled.submit(cancelled_prepare, cancelled_authority)
    assertions["cancelled_provider_attempt_cannot_prepare"] = (
        cancelled_result["code"] == "provider_attempt_mismatch"
        and cancelled.submit(cancelled_prepare, cancelled_authority) == cancelled_result
        and cancelled.state()["aggregate_version"] == 2
    )
    cancelled.close()

    path = root / "core-probe.sqlite"
    store = ResearchStore(path, rng=random.Random(7))
    table = {"room_id": "room:1", "surface": "table", "actor_id": "hero:guardian"}
    internal = {"room_id": "room:1", "surface": "internal", "actor_id": "kernel"}
    coordinator = {"room_id": "room:1", "surface": "internal", "actor_id": "coordinator"}
    scene = {"room_id": "room:1", "surface": "scene", "actor_id": "none"}
    assertions["definition_hash_pins_room_run"] = (
        store.state()["campaign_definition_hash"] == definition["definition_hash"]
    )
    assertions["ruleset_hash_pins_room_run"] = (
        store.state()["ruleset_bundle_hash"] == ruleset_bundle()["bundle_hash"]
    )

    safe_intent = "Drop the brazier to block the bridge and inspect the archive seal."
    begin_adjudication = command(
        "cmd:provider-begin:1",
        "turn.begin_adjudication",
        0,
        turn_id="turn:1",
        draft_version=1,
        args={
            "provider_attempt_id": "provider-attempt:turn-1:1",
            "safe_intent": safe_intent,
        },
    )
    begun = store.submit(begin_adjudication, coordinator)
    assertions["provider_attempt_persisted_before_candidate"] = (
        begun["world_mutation_count"] == 0
        and store.state()["turn"]["provider_attempt_status"] == "running"
        and store.state()["turn"]["stage"] == "drafting"
    )

    unusual_plan = {
        "plan_id": "plan:bridge-trick",
        "kind": "unusual",
        "campaign_definition_hash": definition["definition_hash"],
        "ruleset_id": "srd-5.2.1-mvp-1",
        "rules_engine_version": 1,
        "ruleset_bundle_hash": store.state()["ruleset_bundle_hash"],
        "turn_id": "turn:1",
        "draft_version": 1,
        "expected_aggregate_version": store.state()["aggregate_version"],
        "provider_attempt_id": "provider-attempt:turn-1:1",
        "operations": [
            {
                "op": "set_terrain_feature",
                "transition_id": "terrain-transition:drop-brazier",
            },
            {"op": "reveal_fact_via_route", "route_id": "route:archive"},
            {"op": "advance_clock", "clock_id": "threat:collapse", "amount": 1},
            {
                "op": "schedule_consequence",
                "template_id": "consequence:bridge-noise",
            },
        ],
    }
    assertions["candidate_plan_has_no_public_prose"] = not {
        "public_summary",
        "public_atoms",
        "narration",
    }.intersection(unusual_plan)
    prepare = command(
        "cmd:prepare:1",
        "turn.prepare",
        store.state()["aggregate_version"],
        turn_id="turn:1",
        draft_version=1,
        args={"plan": unusual_plan, "approval_nonce": "n" * 32, "safe_intent": safe_intent},
    )
    stale_provider_plan = copy.deepcopy(unusual_plan)
    stale_provider_plan["provider_attempt_id"] = "provider-attempt:turn-1:stale"
    stale_provider = command(
        "cmd:prepare:stale-provider",
        "turn.prepare",
        store.state()["aggregate_version"],
        turn_id="turn:1",
        draft_version=1,
        args={
            "plan": stale_provider_plan,
            "approval_nonce": "p" * 32,
            "safe_intent": safe_intent,
        },
    )
    stale_provider_result = store.submit(stale_provider, coordinator)
    assertions["stale_provider_attempt_is_durable_rejection"] = (
        stale_provider_result["code"] == "provider_attempt_mismatch"
        and store.submit(stale_provider, coordinator) == stale_provider_result
        and store.state()["turn"]["provider_attempt_status"] == "running"
    )
    table_plan = copy.deepcopy(prepare)
    table_plan["command_id"] = "cmd:table-plan:1"
    assertions["table_cannot_submit_candidate_plan"] = (
        store.submit(table_plan, table)["code"] == "unauthorized"
        and store.state()["aggregate_version"] == 1
    )
    prepared = store.submit(prepare, coordinator)
    assertions["prepare_has_zero_world_mutation"] = prepared["world_mutation_count"] == 0
    approval_batch = store.build_projection_batch()
    projected_card = approval_batch["table"]["approval_card"]
    assertions["approval_card_binds_plan_without_secrets"] = (
        projected_card["plan_digest"] == digest(unusual_plan)
        and projected_card["approval_nonce"] == "n" * 32
        and projected_card["status"] == "awaiting_approval"
        and set(approval_batch["table"]["legal_action_hints"]) == {"approve", "redraft"}
        and SECRET_CANARY not in canonical(projected_card)
        and GM_CANARY not in canonical(projected_card)
        and "operations" not in projected_card
    )
    duplicate_prepare = store.submit(prepare, coordinator)
    assertions["exact_duplicate_returns_stored_result"] = duplicate_prepare == prepared
    other_actor = {"room_id": "room:1", "surface": "internal", "actor_id": "revoked-provider"}
    assertions["dedupe_precedes_dynamic_actor_checks"] = store.submit(prepare, other_actor) == prepared
    conflicting = copy.deepcopy(prepare)
    conflicting["args"]["plan"]["operations"][0]["transition_id"] = "terrain-transition:other"
    assertions["conflicting_id_zero_mutation"] = (
        store.submit(conflicting, table)["code"] == "command_id_conflict"
        and store.state()["world_revision"] == 0
    )
    denied = command("cmd:scene:1", "turn.prepare", 1, args={})
    assertions["scene_cannot_mutate"] = store.submit(denied, scene)["code"] == "unauthorized"

    stale_approve = command(
        "cmd:approve:stale",
        "turn.approve",
        store.state()["aggregate_version"] + 1,
        turn_id="turn:1",
        draft_version=1,
        approval_nonce="n" * 32,
    )
    assertions["stale_version_is_durable_rejection"] = store.submit(stale_approve, table)["code"] == "version_conflict"
    invalid_nonce = command(
        "cmd:approve:invalid-nonce",
        "turn.approve",
        store.state()["aggregate_version"],
        turn_id="turn:1",
        draft_version=1,
        approval_nonce="x" * 32,
    )
    invalid_nonce_result = store.submit(invalid_nonce, table)
    invalid_nonce_conflict = copy.deepcopy(invalid_nonce)
    invalid_nonce_conflict["approval_nonce"] = "y" * 32
    assertions["invalid_nonce_is_durable_and_deduped"] = (
        invalid_nonce_result["code"] == "invalid_approval"
        and store.submit(invalid_nonce, table) == invalid_nonce_result
        and store.submit(invalid_nonce_conflict, table)["code"] == "command_id_conflict"
        and store.state()["world_revision"] == 0
    )
    approve = command(
        "cmd:approve:1",
        "turn.approve",
        store.state()["aggregate_version"],
        turn_id="turn:1",
        draft_version=1,
        approval_nonce="n" * 32,
    )
    approved = store.submit(approve, table)
    assertions["approval_has_zero_world_mutation"] = approved["world_mutation_count"] == 0
    assertions["approval_enqueues_projection_without_world_revision"] = (
        approved["world_revision"] == 0 and store.counts()["outbox"] == 3
    )
    assertions["approval_binds_stored_plan_digest"] = (
        store.state()["turn"]["plan_digest"] == digest(unusual_plan)
        and store.state()["turn"]["approval_nonce"] is None
    )
    execute = command(
        "cmd:execute:1",
        "turn.execute",
        store.state()["aggregate_version"],
        turn_id="turn:1",
    )
    before_crash = store.state()
    before_crash_counts = store.counts()
    crash_boundaries_clean = True
    for failpoint in (
        "after_result_before_event",
        "after_event_before_state",
        "after_state_before_outbox",
        "after_outbox_before_commit",
    ):
        try:
            store.submit(execute, internal, failpoint=failpoint)
            crash_boundaries_clean = False
        except RuntimeError as error:
            crash_boundaries_clean = crash_boundaries_clean and (
                str(error) == "injected_crash_before_commit"
                and store.state() == before_crash
                and store.counts() == before_crash_counts
            )
    assertions["all_precommit_boundaries_roll_back_everything"] = crash_boundaries_clean
    executed = store.submit(execute, internal)
    state_after_execute = store.state()
    assertions["unusual_plan_commits_once"] = (
        executed["world_mutation_count"] == 1
        and state_after_execute["tactical"]["terrain"]["5,3"]["kind"] == "debris"
        and state_after_execute["narrative"]["reveals"]["fact:seal"]["route_id"] == "route:archive"
        and state_after_execute["narrative"]["consequence_ledger"]
        == ["consequence:bridge-noise:cause:cmd:execute:1"]
    )
    assertions["late_duplicate_execute_does_not_repeat"] = (
        store.submit(execute, internal) == executed
        and store.state()["narrative"]["clocks"]["threat:collapse"] == 1
        and store.state()["narrative"]["consequence_ledger"]
        == ["consequence:bridge-noise:cause:cmd:execute:1"]
    )
    first_batch = store.build_projection_batch()
    store.ack_projection("table:first", "table", first_batch["projection_batch_id"], render_ok=True)
    store.submit(
        command(
            "cmd:projection-ack:1",
            "projection.ack",
            store.state()["aggregate_version"],
            args={"batch_id": first_batch["projection_batch_id"], "consumer_id": "table:first"},
        ),
        table,
    )
    try:
        store.submit(
            command(
                "cmd:postcommit:1",
                "phase.end_players",
                store.state()["aggregate_version"],
            ),
            table,
            failpoint="after_commit_before_return",
        )
    except RuntimeError as error:
        postcommit_version = store.state()["aggregate_version"]
        replay = store.submit(
            command("cmd:postcommit:1", "phase.end_players", postcommit_version - 1),
            table,
        )
        assertions["crash_after_commit_recovers_stored_result"] = (
            str(error) == "injected_crash_after_commit"
            and replay["aggregate_version"] == postcommit_version
            and store.state()["tactical"]["combat"]["phase"] == "world"
        )

    world_result = store.submit(
        command(
            "cmd:world:1",
            "phase.execute_world",
            store.state()["aggregate_version"],
        ),
        internal,
    )
    world_state = store.state()
    enemy_roll = world_state["tactical"]["roll_ledger"]["enemy-roll:r1"]
    assertions["enemy_roll_is_public_and_persisted"] = (
        world_result["world_mutation_count"] == 1
        and enemy_roll["visibility"] == "public"
        and all(key in enemy_roll for key in ("raw", "modifier", "total"))
    )

    # A second turn requests a physical player roll; only confirmation can resolve it.
    version = store.state()["aggregate_version"]
    roll_plan = {
        "plan_id": "plan:physical-roll",
        "kind": "standard",
        "campaign_definition_hash": definition["definition_hash"],
        "ruleset_id": "srd-5.2.1-mvp-1",
        "rules_engine_version": 1,
        "ruleset_bundle_hash": store.state()["ruleset_bundle_hash"],
        "turn_id": "turn:2",
        "draft_version": 1,
        "expected_aggregate_version": version,
        "provider_attempt_id": None,
        "operations": [
            {
                "op": "open_physical_roll",
                "roll_id": "roll:hero:1",
                "actor_id": "hero:guardian",
                "kind": "attack",
                "sides": 20,
                "modifier": 5,
                "target": 12,
                "target_id": "enemy:boss",
                "damage": 4,
            }
        ],
    }
    store.submit(
        command(
            "cmd:prepare:2",
            "turn.prepare",
            version,
            turn_id="turn:2",
            draft_version=1,
            args={"plan": roll_plan, "approval_nonce": "r" * 32, "safe_intent": "Strike the boss."},
        ),
        coordinator,
    )
    version = store.state()["aggregate_version"]
    store.submit(
        command(
            "cmd:approve:2",
            "turn.approve",
            version,
            turn_id="turn:2",
            draft_version=1,
            approval_nonce="r" * 32,
        ),
        table,
    )
    version = store.state()["aggregate_version"]
    store.submit(command("cmd:execute:2", "turn.execute", version, turn_id="turn:2"), internal)
    hp_before_roll = store.state()["tactical"]["entities"]["enemy:boss"]["hp"]
    assertions["pending_roll_does_not_apply_outcome"] = hp_before_roll == 10
    roll_batch = store.build_projection_batch()
    store.ack_projection("table:roll", "table", roll_batch["projection_batch_id"], render_ok=True)
    store.submit(
        command(
            "cmd:projection-ack:2",
            "projection.ack",
            store.state()["aggregate_version"],
            args={"batch_id": roll_batch["projection_batch_id"], "consumer_id": "table:roll"},
        ),
        table,
    )
    version = store.state()["aggregate_version"]
    roll_request = command(
        "cmd:roll:1",
        "roll.confirm",
        version,
        args={"roll_id": "roll:hero:1", "raw": 17},
    )
    roll_result = store.submit(roll_request, table)
    assertions["physical_roll_consumed_exactly_once"] = (
        store.state()["tactical"]["entities"]["enemy:boss"]["hp"] == 6
        and store.submit(roll_request, table) == roll_result
        and store.state()["tactical"]["pending_rolls"]["roll:hero:1"]["status"] == "consumed"
    )

    # NPC death disables one route while the authored durable route stays eligible.
    branch_state = store.state()
    branch_state["narrative"]["npc_status"]["npc:warden"] = "dead"
    assertions["npc_death_preserves_alternate_route"] = (
        not route_eligible(branch_state, definition, "route:warden")
        and route_eligible(branch_state, definition, "route:archive")
    )
    branch_state["narrative"]["npc_status"]["npc:warden"] = "alive_absent"
    assertions["alive_absent_is_not_dead_or_present"] = (
        not route_eligible(branch_state, definition, "route:warden")
        and branch_state["narrative"]["npc_status"]["npc:warden"] == "alive_absent"
    )

    batch = store.build_projection_batch()
    projection_text = canonical(batch)
    assertions["three_projections_share_one_safe_version"] = (
        len({batch[surface]["aggregate_version"] for surface in ("table", "scene", "admin")}) == 1
        and SECRET_CANARY not in projection_text
        and GM_CANARY not in projection_text
        and batch["table"]["revealed_facts"]["fact:seal"] == "The bronze seal identifies a traitor."
    )
    mixed_family = copy.deepcopy(batch)
    mixed_family["scene"]["aggregate_version"] -= 1
    try:
        store._validate_projection_family(mixed_family)
    except Rejected as error:
        assertions["mixed_projection_family_is_rejected"] = error.code == "projection_family_mismatch"
    reconnect_cursor_count = store.counts()["cursors"]
    reconnect_family = store.reconnect_snapshot()
    assertions["reconnect_gets_latest_safe_snapshot_without_cursor_advance"] = (
        reconnect_family == batch
        and store.counts()["cursors"] == reconnect_cursor_count
        and SECRET_CANARY not in canonical(reconnect_family)
        and GM_CANARY not in canonical(reconnect_family)
    )
    assertions["narrator_input_is_safe_atoms_only"] = (
        set(batch["scene"]) == {
            "schema",
            "aggregate_version",
            "world_revision",
            "public_atoms",
            "revealed_facts",
            "public_rolls",
        }
        and SECRET_CANARY not in canonical(batch["scene"])
    )
    assertions["admin_projection_is_operational_only"] = set(batch["admin"]) == {
        "schema",
        "aggregate_version",
        "world_revision",
        "run_state",
        "coordinator",
        "projection_health",
    }
    before_projection_count = store.counts()["projection_batches"]
    try:
        store.build_projection_batch(inject_secret=True)
    except Rejected as error:
        assertions["secret_projection_fails_closed"] = (
            error.code == "secret_projection_failure"
            and store.counts()["projection_batches"] == before_projection_count
        )
    try:
        store.build_projection_batch(inject_unknown=True)
    except Rejected as error:
        assertions["unknown_projection_field_fails_closed"] = (
            error.code == "projection_schema_failure"
            and store.counts()["projection_batches"] == before_projection_count
        )
    cursor_count_before = store.counts()["cursors"]
    store.ack_projection("table:primary", "table", batch["projection_batch_id"], render_ok=False)
    assertions["render_failure_does_not_advance_cursor"] = (
        store.counts()["cursors"] == cursor_count_before
    )
    store.ack_projection("table:primary", "table", batch["projection_batch_id"], render_ok=True)
    cursor = store.connection.execute(
        "SELECT batch_id FROM cursors WHERE consumer_id='table:primary' AND surface='table'"
    ).fetchone()[0]
    assertions["cursor_advances_only_after_render"] = cursor == batch["projection_batch_id"]

    # Side phases and classic initiative share the aggregate but mode locks at encounter start.
    fresh = ResearchStore(root / "classic.sqlite")
    classic_plan = {
        "plan_id": "plan:classic",
        "kind": "standard",
        "campaign_definition_hash": fresh.state()["campaign_definition_hash"],
        "ruleset_id": "srd-5.2.1-mvp-1",
        "rules_engine_version": 1,
        "ruleset_bundle_hash": fresh.state()["ruleset_bundle_hash"],
        "turn_id": "turn:classic",
        "draft_version": 1,
        "expected_aggregate_version": 0,
        "provider_attempt_id": None,
        "operations": [
            {
                "op": "advance_combat_mode",
                "mode": "classic_initiative",
                "order": [*starter_heroes(), "enemy:boss"],
            }
        ],
    }
    fresh.submit(
        command(
            "cmd:classic:prepare",
            "turn.prepare",
            0,
            turn_id="turn:classic",
            draft_version=1,
            args={"plan": classic_plan, "approval_nonce": "c" * 32, "safe_intent": "Begin combat."},
        ),
        coordinator,
    )
    fresh.submit(
        command(
            "cmd:classic:approve",
            "turn.approve",
            1,
            turn_id="turn:classic",
            draft_version=1,
            approval_nonce="c" * 32,
        ),
        table,
    )
    fresh.submit(command("cmd:classic:execute", "turn.execute", 2, turn_id="turn:classic"), internal)
    classic_batch = fresh.build_projection_batch()
    fresh.ack_projection("table:classic", "table", classic_batch["projection_batch_id"], render_ok=True)
    fresh.submit(
        command(
            "cmd:classic:projection-ack",
            "projection.ack",
            fresh.state()["aggregate_version"],
            args={"batch_id": classic_batch["projection_batch_id"], "consumer_id": "table:classic"},
        ),
        table,
    )
    wrong_classic = fresh.submit(
        command(
            "cmd:classic:wrong-actor",
            "action.standard_move",
            fresh.state()["aggregate_version"],
            args={"destination": [2, 2]},
        ),
        {"room_id": "room:1", "surface": "table", "actor_id": "hero:fury"},
    )
    fresh.submit(
        command(
            "cmd:classic:guardian-move",
            "action.standard_move",
            fresh.state()["aggregate_version"],
            args={"destination": [2, 1]},
        ),
        table,
    )
    fresh.submit(
        command("cmd:classic:end:guardian", "phase.end_players", fresh.state()["aggregate_version"]),
        table,
    )
    fresh.submit(
        command(
            "cmd:classic:fury-move",
            "action.standard_move",
            fresh.state()["aggregate_version"],
            args={"destination": [2, 2]},
        ),
        {"room_id": "room:1", "surface": "table", "actor_id": "hero:fury"},
    )
    for hero_id in list(starter_heroes())[1:]:
        fresh.submit(
            command(
                f"cmd:classic:end:{hero_id}",
                "phase.end_players",
                fresh.state()["aggregate_version"],
            ),
            {"room_id": "room:1", "surface": "table", "actor_id": hero_id},
        )
    classic_before_world = fresh.state()
    fresh.submit(
        command("cmd:classic:world", "phase.execute_world", classic_before_world["aggregate_version"]),
        internal,
    )
    classic_after_world = fresh.state()
    assertions["classic_fallback_uses_same_aggregate"] = (
        fresh.state()["tactical"]["combat"]["mode"] == "classic_initiative"
        and len(fresh.state()["tactical"]["combat"]["classic_order"]) == 7
        and wrong_classic["code"] == "wrong_initiative_actor"
        and classic_before_world["tactical"]["combat"]["phase"] == "world"
        and classic_before_world["tactical"]["combat"]["classic_index"] == 6
        and classic_after_world["tactical"]["combat"]["phase"] == "players"
        and classic_after_world["tactical"]["combat"]["classic_index"] == 0
        and classic_after_world["tactical"]["combat"]["round"] == 2
    )
    fresh.close()

    # Invalid/unknown operation is tested on a fresh store so stage preconditions cannot mask it.
    invalid = ResearchStore(root / "invalid.sqlite")
    invalid_plan = {
        "plan_id": "plan:invalid",
        "kind": "unusual",
        "campaign_definition_hash": invalid.state()["campaign_definition_hash"],
        "ruleset_id": "srd-5.2.1-mvp-1",
        "rules_engine_version": 1,
        "ruleset_bundle_hash": invalid.state()["ruleset_bundle_hash"],
        "turn_id": "turn:invalid",
        "draft_version": 1,
        "expected_aggregate_version": 1,
        "provider_attempt_id": "provider-attempt:invalid:1",
        "operations": [{"op": "json_patch", "path": "/narrative/reveals", "value": SECRET_CANARY}],
    }
    invalid.submit(
        command(
            "cmd:invalid:begin",
            "turn.begin_adjudication",
            0,
            turn_id="turn:invalid",
            draft_version=1,
            args={"provider_attempt_id": "provider-attempt:invalid:1", "safe_intent": "Patch the world."},
        ),
        coordinator,
    )
    invalid_before = invalid.state()
    invalid_request = command(
        "cmd:invalid",
        "turn.prepare",
        1,
        turn_id="turn:invalid",
        draft_version=1,
        args={"plan": invalid_plan, "approval_nonce": "i" * 32, "safe_intent": "Patch the world."},
    )
    invalid_result = invalid.submit(invalid_request, coordinator)
    invalid_conflict = copy.deepcopy(invalid_request)
    invalid_conflict["args"]["plan"]["operations"][0]["path"] = "/narrative/clocks"
    assertions["unknown_ai_operation_zero_mutation"] = (
        invalid_result["code"] == "unknown_operation"
        and invalid.submit(invalid_request, coordinator) == invalid_result
        and invalid.submit(invalid_conflict, coordinator)["code"] == "command_id_conflict"
        and invalid.state() == invalid_before
    )
    forged_consequence_plan = copy.deepcopy(invalid_plan)
    forged_consequence_plan.update(plan_id="plan:forged-consequence")
    forged_consequence_plan["operations"] = [
        {
            "op": "schedule_consequence",
            "template_id": "consequence:bridge-noise",
            "instance_id": "attacker-chosen-instance",
        }
    ]
    forged_consequence = command(
        "cmd:forged-consequence",
        "turn.prepare",
        1,
        turn_id="turn:invalid",
        draft_version=1,
        args={
            "plan": forged_consequence_plan,
            "approval_nonce": "f" * 32,
            "safe_intent": "Patch the world.",
        },
    )
    forged_result = invalid.submit(forged_consequence, coordinator)
    assertions["consequence_instance_identity_is_server_derived"] = (
        forged_result["code"] == "invalid_operation_schema"
        and invalid.submit(forged_consequence, coordinator) == forged_result
        and invalid.state() == invalid_before
    )
    invalid.close()

    # Explicit simultaneous-ending policy: loss priority wins; equal priority is invalid.
    ending_state = store.state()
    ending_state["narrative"]["clocks"]["threat:collapse"] = 3
    ending_state["tactical"]["entities"]["enemy:boss"]["lifecycle"] = "defeated"
    assertions["simultaneous_endings_use_authored_priority"] = evaluate_ending(ending_state, definition) == "ending:loss"
    ambiguous = copy.deepcopy(definition)
    ambiguous["endings"]["ending:success"]["priority"] = 100
    try:
        evaluate_ending(ending_state, ambiguous)
    except ValueError as error:
        assertions["equal_priority_terminal_is_authoring_error"] = str(error) == "ambiguous_terminal_ending"

    final_state = store.state()
    final_counts = store.counts()
    store.close()
    failed = sorted(name for name, passed in assertions.items() if not passed)
    return {
        "probe_kind": "synthetic_research_not_product",
        "seed": 3771101,
        "assertion_count": len(assertions),
        "passed": len(assertions) - len(failed),
        "failed": failed,
        "oracle": "PASS" if not failed else "FAIL",
        "assertions": assertions,
        "final_aggregate_version": final_state["aggregate_version"],
        "final_world_revision": final_state["world_revision"],
        "final_state_hash": digest(final_state),
        "final_counts": final_counts,
        "secret_canary_absent_from_projection": assertions.get("three_projections_share_one_safe_version", False),
    }


def main() -> int:
    if len(sys.argv) == 2:
        root = Path(sys.argv[1]).resolve()
        root.mkdir(parents=True, exist_ok=True)
        result = run_probe(root)
    else:
        with tempfile.TemporaryDirectory(prefix="core-research-probe-") as temp:
            result = run_probe(Path(temp))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["oracle"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
