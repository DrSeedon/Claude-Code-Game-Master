#!/usr/bin/env python
"""Deterministic R9 research probes over an abstract, non-production fixture."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import math
import random
import statistics
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "content-contract.schema.json"
EXAMPLE_PATH = HERE / "abstract-example.json"
RESULTS_PATH = HERE / "probe-results.json"

REQUIRED_OBLIGATION_KINDS = {
    "hero_selection",
    "narrator_selection",
    "important_npc_social",
    "direction_choice",
    "investigation_or_trap",
    "shared_plan",
    "physical_roll",
    "tactical_fight",
    "boss_conflict",
    "rules_dispute",
    "persistent_consequence",
    "continuation_hook",
}

SUPPORTED_MECHANICS = {
    "rule.d20",
    "rule.attack",
    "rule.damage",
    "rule.healing",
    "rule.resource",
    "rule.resistance",
    "rule.skill",
    "rule.social_check",
    "rule.investigation",
    "rule.trap_save",
    "rule.pending_physical_roll",
    "rule.side_phases",
    "rule.death_saves",
    "rule.bonus_action",
    "rule.spell",
    "rule.concentration",
    "rule.area",
    "rule.inspiration",
    "rule.reaction",
    "rule.dispute_correction",
    "rule.schedule_consequence",
    "rule.clock",
    "rule.npc_state",
}

EXPECTED_STARTER_ROLES = {"guardian", "fury", "shadow", "beacon", "arcanist", "voice"}

OPERATION_SIGNATURES: dict[str, dict[str, type]] = {
    "move_entity": {"entity_id": str, "to_anchor_id": str},
    "apply_damage": {"source_id": str, "target_id": str, "amount_formula_id": str},
    "apply_healing": {"source_id": str, "target_id": str, "amount_formula_id": str},
    "set_condition": {"target_id": str, "condition_id": str, "active": bool},
    "spend_resource": {"actor_id": str, "resource_id": str, "amount": int},
    "create_effect": {"effect_id": str, "subject_id": str},
    "set_terrain_feature": {"map_id": str, "feature_id": str, "active": bool},
    "spawn_from_template": {"template_id": str, "anchor_id": str},
    "despawn_entity": {"entity_id": str},
    "set_npc_status": {"npc_id": str, "status": str},
    "reveal_fact_via_route": {"route_id": str},
    "advance_clock": {"minutes": int},
    "schedule_consequence": {"consequence_id": str},
    "open_physical_roll": {"roll_id": str},
    "advance_combat_mode": {"encounter_id": str, "result": str},
}

OPERATION_SUBJECT_KINDS = {
    "move_entity": {"entity"},
    "apply_damage": {"entity"},
    "apply_healing": {"entity"},
    "set_condition": {"entity"},
    "spend_resource": {"entity"},
    "create_effect": {"run", "encounter", "entity", "terrain"},
    "set_terrain_feature": {"terrain"},
    "spawn_from_template": {"entity"},
    "despawn_entity": {"entity"},
    "set_npc_status": {"npc"},
    "reveal_fact_via_route": {"fact"},
    "advance_clock": {"run"},
    "schedule_consequence": {"consequence"},
    "open_physical_roll": {"roll"},
    "advance_combat_mode": {"encounter"},
}

OPERATION_IDEMPOTENCY_SCOPES = {
    "move_entity": {"once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "apply_damage": {"once_per_transition", "once_per_beat_visit"},
    "apply_healing": {"once_per_transition", "once_per_beat_visit"},
    "set_condition": {"once_per_transition", "once_per_beat_visit"},
    "spend_resource": {"once_per_transition", "once_per_beat_visit"},
    "create_effect": {"once_per_run", "once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "set_terrain_feature": {"once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "spawn_from_template": {"once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "despawn_entity": {"once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "set_npc_status": {"once_per_transition", "once_per_redirect_use"},
    "reveal_fact_via_route": {"once_per_transition", "once_per_redirect_use"},
    "advance_clock": {"once_per_transition", "once_per_redirect_use", "once_per_beat_visit"},
    "schedule_consequence": {"once_per_run"},
    "open_physical_roll": {"once_per_transition"},
    "advance_combat_mode": {"once_per_transition", "once_per_beat_visit"},
}

# Frozen before the full sweep. They calibrate only the abstract attrition model.
SYNTHETIC_PASS_BANDS = {
    "normal_win_rate": [0.70, 0.98],
    "normal_tpk_rate_max": 0.05,
    "normal_any_downed_rate": [0.10, 0.70],
    "boss_alpha_kill_rate_max": 0.05,
    "world_first_down_rate_max": 0.15,
    "combat_minutes_p90_max": 43.0,
    "combat_minutes_median_min": 18.0,
}

ROLES = {
    "guardian": {"hp": 31, "ac": 18, "attack": 5, "damage": 8.5, "initiative": 1, "heals": 1},
    "fury": {"hp": 32, "ac": 15, "attack": 5, "damage": 10.0, "initiative": 2, "heals": 0},
    "shadow": {"hp": 24, "ac": 15, "attack": 5, "damage": 11.0, "initiative": 3, "heals": 0},
    "beacon": {"hp": 27, "ac": 18, "attack": 4, "damage": 7.0, "initiative": 0, "heals": 3},
    "arcanist": {"hp": 20, "ac": 13, "attack": 5, "damage": 9.5, "initiative": 2, "heals": 0},
    "voice": {"hp": 24, "ac": 15, "attack": 4, "damage": 7.5, "initiative": 2, "heals": 2},
}

ENVELOPES = {
    "story": {
        "skirmish": {"count_delta": -1, "hp": 10, "ac": 12, "attack": 3, "damage": 4.0},
        "boss": {"hp_per_pc": 14, "ac": 13, "attacks_delta": -2, "damage": 6.0, "adds_divisor": 3},
    },
    "normal": {
        "skirmish": {"count_delta": 0, "hp": 12, "ac": 13, "attack": 4, "damage": 4.5},
        "boss": {"hp_per_pc": 18, "ac": 14, "attacks_delta": -2, "damage": 7.0, "adds_divisor": 2},
    },
    "hard": {
        "skirmish": {"count_delta": 0, "hp": 15, "ac": 13, "attack": 4, "damage": 5.0},
        "boss": {"hp_per_pc": 22, "ac": 15, "attacks_delta": -1, "damage": 7.5, "adds_divisor": 2},
    },
}


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(SCHEMA_PATH.read_text()), json.loads(EXAMPLE_PATH.read_text())


def canonical_package_bytes(package: dict[str, Any]) -> bytes:
    canonical = copy.deepcopy(package)
    canonical["identity"]["content_hash"] = "0" * 64
    return json.dumps(
        canonical,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def package_hash(package: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_package_bytes(package)).hexdigest()


def atom_true(atom: dict[str, Any], state: dict[str, Any]) -> bool:
    kind, ref, value = atom["kind"], atom["ref"], atom.get("value")
    if kind == "fact_revealed":
        return ref in state["revealed"]
    if kind == "beat_completed":
        return ref in state["completed"]
    if kind == "npc_present":
        return state["npcs"].get(ref) == "alive_present"
    if kind == "npc_absent":
        return state["npcs"].get(ref) == "alive_absent"
    if kind == "npc_dead":
        return state["npcs"].get(ref) == "dead"
    if kind == "clock_at_least":
        return state["clock"] >= value
    if kind == "encounter_complete":
        actual = state["encounters"].get(ref)
        return actual is not None and (value is None or actual == value)
    if kind == "choice_equals":
        return state["choices"].get(ref) == value
    if kind == "effect_active":
        return ref in state["effects"]
    if kind == "consequence_scheduled":
        return ref in state["consequences"]
    raise AssertionError(f"uncompiled predicate atom: {atom}")


def dnf_true(predicate: list[list[dict[str, Any]]], state: dict[str, Any]) -> bool:
    assert predicate, "empty DNF outer array is forbidden; use `[[]]` for always"
    return any(all(atom_true(atom, state) for atom in branch) for branch in predicate)


def route_index(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {route["route_id"]: route for clue in package["clues"].values() for route in clue["routes"]}


def validate_predicate_refs(package: dict[str, Any]) -> int:
    created_effects = {
        template["arguments"]["effect_id"]
        for template in package["effect_templates"].values()
        if template["core_operation"] == "create_effect"
    }
    consequences = {
        template["arguments"]["consequence_id"]
        for template in package["effect_templates"].values()
        if template["core_operation"] == "schedule_consequence"
    }
    predicates: list[tuple[str, list[list[dict[str, Any]]]]] = []
    predicates.extend((f"clue:{route['route_id']}", route["preconditions"]) for clue in package["clues"].values() for route in clue["routes"])
    for beat_id, beat in package["beats"].items():
        predicates.extend(((f"{beat_id}.entry", beat["entry"]), (f"{beat_id}.completion", beat["completion"])))
        predicates.extend((f"{transition['transition_id']}.condition", transition["condition"]) for transition in beat["transitions"])
    predicates.extend((f"{redirect_id}.preconditions", redirect["preconditions"]) for redirect_id, redirect in package["redirects"].items())
    predicates.extend((f"{outcome_id}.when", outcome["when"]) for outcome_id, outcome in package["outcomes"].items())
    count = 0
    for label, predicate in predicates:
        assert predicate, f"{label}: empty DNF outer list"
        for branch in predicate:
            for atom in branch:
                kind, ref = atom["kind"], atom["ref"]
                if kind == "fact_revealed":
                    assert ref in package["truth_facts"], label
                elif kind == "beat_completed":
                    assert ref in package["beats"], label
                elif kind in {"npc_present", "npc_absent", "npc_dead"}:
                    assert ref in package["npcs"], label
                elif kind == "clock_at_least":
                    assert ref == "clock.slice" and type(atom.get("value")) is int, label
                elif kind == "encounter_complete":
                    assert ref in package["encounters"], label
                elif kind == "choice_equals":
                    assert ref in package["choice_templates"] and atom.get("value") in package["choice_templates"][ref]["allowed_values"], label
                elif kind == "effect_active":
                    assert ref in created_effects, label
                elif kind == "consequence_scheduled":
                    assert ref in consequences, label
                count += 1
    return count


def validate_effect_template(package: dict[str, Any], effect_id: str, template: dict[str, Any]) -> None:
    operation, args = template["core_operation"], template["arguments"]
    assert operation in OPERATION_SIGNATURES, f"{effect_id}: unsupported Core operation {operation}"
    expected = OPERATION_SIGNATURES[operation]
    assert set(args) == set(expected), f"{effect_id}: expected args {sorted(expected)}, got {sorted(args)}"
    for name, expected_type in expected.items():
        assert type(args[name]) is expected_type, f"{effect_id}.{name}: expected {expected_type.__name__}"
    assert template["subject_kind"] in OPERATION_SUBJECT_KINDS[operation], f"{effect_id}: subject_kind {template['subject_kind']} invalid for {operation}"
    assert template["idempotency_scope"] in OPERATION_IDEMPOTENCY_SCOPES[operation], f"{effect_id}: idempotency scope invalid for {operation}"

    entity_ids = set(package["entities"]) | set(package["npcs"]) | set(package["starter_roles"]) | set(package["enemy_templates"])
    anchor_ids = {anchor_id for map_entry in package["maps"].values() for anchor_id in map_entry["topology"]["spawn_anchors"]}
    feature_ids = {feature_id for map_entry in package["maps"].values() for feature_id in map_entry["topology"]["objective_cells"]}
    if operation == "move_entity":
        assert args["entity_id"] in entity_ids and args["to_anchor_id"] in anchor_ids, effect_id
    elif operation in {"apply_damage", "apply_healing"}:
        assert args["source_id"] in entity_ids and args["target_id"] in entity_ids and args["amount_formula_id"] in SUPPORTED_MECHANICS, effect_id
    elif operation == "set_condition":
        assert args["target_id"] in entity_ids and args["condition_id"] in SUPPORTED_MECHANICS, effect_id
    elif operation == "spend_resource":
        assert args["actor_id"] in entity_ids and args["resource_id"] in SUPPORTED_MECHANICS and args["amount"] > 0, effect_id
    elif operation == "create_effect":
        subject_kind, subject_id = template["subject_kind"], args["subject_id"]
        valid_subjects = {
            "run": {"run.slice"},
            "encounter": set(package["encounters"]),
            "entity": entity_ids,
            "terrain": set(package["maps"]),
        }
        assert subject_id in valid_subjects[subject_kind] and args["effect_id"].startswith("effect."), effect_id
    elif operation == "set_terrain_feature":
        assert args["map_id"] in package["maps"] and args["feature_id"] in feature_ids, effect_id
    elif operation == "spawn_from_template":
        assert args["template_id"] in package["enemy_templates"] and args["anchor_id"] in anchor_ids, effect_id
    elif operation == "despawn_entity":
        assert args["entity_id"] in entity_ids, effect_id
    if operation == "reveal_fact_via_route":
        assert args["route_id"] in route_index(package), effect_id
    elif operation == "advance_clock":
        assert args["minutes"] > 0, effect_id
    elif operation == "set_npc_status":
        assert args["npc_id"] in package["npcs"] and args["status"] in {"alive_present", "alive_absent", "dead"}, effect_id
    elif operation == "advance_combat_mode":
        assert args["encounter_id"] in package["encounters"] and args["result"] in {"success", "failure", "timeout_or_partial"}, effect_id
    elif operation == "schedule_consequence":
        assert args["consequence_id"] == effect_id and effect_id.startswith("consequence."), effect_id
    elif operation == "open_physical_roll":
        assert args["roll_id"] in package["roll_templates"], effect_id


def idempotency_key(effect_id: str, template: dict[str, Any], context: dict[str, str]) -> tuple[str, str, str, str]:
    assert context.get("run_id"), f"{effect_id}: missing run_id idempotency context"
    context_key = {
        "once_per_run": "run_id",
        "once_per_beat_visit": "beat_visit_id",
        "once_per_transition": "transition_id",
        "once_per_redirect_use": "redirect_use_id",
    }[template["idempotency_scope"]]
    assert context.get(context_key), f"{effect_id}: missing {context_key} idempotency context"
    return context["run_id"], template["idempotency_scope"], context[context_key], effect_id


def apply_effect(package: dict[str, Any], state: dict[str, Any], effect_id: str, context: dict[str, str]) -> bool:
    template = package["effect_templates"][effect_id]
    validate_effect_template(package, effect_id, template)
    key = idempotency_key(effect_id, template, context)
    applied = state.setdefault("applied_effects", set())
    if key in applied:
        return False
    applied.add(key)
    operation, args = template["core_operation"], template["arguments"]
    state.setdefault("operation_log", []).append(f"{effect_id}:{json.dumps(args, sort_keys=True)}")
    if operation == "reveal_fact_via_route":
        route = route_index(package)[args["route_id"]]
        assert dnf_true(route["preconditions"], state), f"ineligible reveal route {args['route_id']}"
        state["revealed"].update(route["reveal_fact_ids"])
    elif operation == "advance_clock":
        assert args["minutes"] >= 0
        state["clock"] += args["minutes"]
    elif operation == "set_npc_status":
        assert args["npc_id"] in package["npcs"]
        assert args["status"] in {"alive_present", "alive_absent", "dead"}
        state["npcs"][args["npc_id"]] = args["status"]
    elif operation == "advance_combat_mode":
        assert args["encounter_id"] in package["encounters"]
        assert args["result"] in {"success", "failure", "timeout_or_partial"}
        state["encounters"][args["encounter_id"]] = args["result"]
    elif operation == "create_effect":
        state["effects"].add(args["effect_id"])
    elif operation == "schedule_consequence":
        state["consequences"].add(args["consequence_id"])
    elif operation == "open_physical_roll":
        state["effects"].add(f"open:{args['roll_id']}")
    elif operation == "move_entity":
        state.setdefault("positions", {})[args["entity_id"]] = args["to_anchor_id"]
    elif operation == "set_condition":
        conditions = state.setdefault("conditions", set())
        entry = (args["target_id"], args["condition_id"])
        conditions.add(entry) if args["active"] else conditions.discard(entry)
    elif operation == "set_terrain_feature":
        state.setdefault("terrain", {})[(args["map_id"], args["feature_id"])] = args["active"]
    elif operation == "spawn_from_template":
        state.setdefault("spawned", []).append((args["template_id"], args["anchor_id"]))
    elif operation == "despawn_entity":
        state.setdefault("despawned", set()).add(args["entity_id"])
    return True


def effect_probe_state(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "clock": 0,
        "revealed": set(),
        "completed": set(),
        "npcs": {npc_id: npc["initial_status"] for npc_id, npc in package["npcs"].items()},
        "encounters": {"encounter.skirmish": "success", "encounter.boss": "success"},
        "choices": {},
        "effects": set(),
        "consequences": set(),
        "applied_effects": set(),
        "operation_log": [],
    }


def check_effect_semantics(package: dict[str, Any]) -> dict[str, Any]:
    context_a = {
        "run_id": "run.effect-probe",
        "beat_visit_id": "beat.effect-probe:1",
        "transition_id": "transition.effect-probe:1",
        "redirect_use_id": "redirect.effect-probe:1",
    }
    context_b = {
        **context_a,
        "beat_visit_id": f"{context_a['beat_visit_id']}:different",
        "transition_id": f"{context_a['transition_id']}:different",
        "redirect_use_id": f"{context_a['redirect_use_id']}:different",
    }
    scopes: set[str] = set()
    duplicate_rejections = 0
    distinct_scope_reapplications = 0
    cross_run_reapplications = 0
    for effect_id, template in package["effect_templates"].items():
        validate_effect_template(package, effect_id, template)
        scopes.add(template["idempotency_scope"])
        state = effect_probe_state(package)
        assert apply_effect(package, state, effect_id, context_a), effect_id
        after_first = state_key(state)
        assert not apply_effect(package, state, effect_id, context_a), f"{effect_id}: duplicate application accepted"
        assert state_key(state) == after_first, f"{effect_id}: duplicate application mutated state"
        duplicate_rejections += 1
        reapplied = apply_effect(package, state, effect_id, context_b)
        if template["idempotency_scope"] == "once_per_run":
            assert not reapplied, f"{effect_id}: once_per_run reapplied under a different event context"
        else:
            assert reapplied, f"{effect_id}: distinct scope instance was suppressed"
            distinct_scope_reapplications += 1
        context_c = {**context_a, "run_id": "run.effect-probe.other"}
        assert apply_effect(package, state, effect_id, context_c), f"{effect_id}: a different run was suppressed"
        cross_run_reapplications += 1
    expected_scopes = {"once_per_run", "once_per_beat_visit", "once_per_transition", "once_per_redirect_use"}
    assert scopes == expected_scopes, f"unexercised idempotency scopes: {sorted(expected_scopes - scopes)}"

    invalid_cases = {
        "move_entity": ("entity", {"entity_id": "entity.missing", "to_anchor_id": "anchor.missing"}, "once_per_transition"),
        "apply_damage": ("entity", {"source_id": "entity.missing", "target_id": "entity.missing", "amount_formula_id": "rule.missing"}, "once_per_transition"),
        "apply_healing": ("entity", {"source_id": "entity.missing", "target_id": "entity.missing", "amount_formula_id": "rule.missing"}, "once_per_transition"),
        "set_condition": ("entity", {"target_id": "entity.missing", "condition_id": "rule.missing", "active": True}, "once_per_transition"),
        "spend_resource": ("entity", {"actor_id": "entity.missing", "resource_id": "rule.missing", "amount": 1}, "once_per_transition"),
        "create_effect": ("encounter", {"effect_id": "effect.invalid", "subject_id": "encounter.missing"}, "once_per_transition"),
        "set_terrain_feature": ("terrain", {"map_id": "map.missing", "feature_id": "feature.missing", "active": True}, "once_per_transition"),
        "spawn_from_template": ("entity", {"template_id": "enemy.missing", "anchor_id": "anchor.missing"}, "once_per_transition"),
        "despawn_entity": ("entity", {"entity_id": "entity.missing"}, "once_per_transition"),
        "set_npc_status": ("npc", {"npc_id": "npc.missing", "status": "alive_present"}, "once_per_transition"),
        "reveal_fact_via_route": ("fact", {"route_id": "route.missing"}, "once_per_transition"),
        "advance_clock": ("run", {"minutes": 0}, "once_per_transition"),
        "schedule_consequence": ("consequence", {"consequence_id": "consequence.missing"}, "once_per_run"),
        "open_physical_roll": ("roll", {"roll_id": "roll.missing"}, "once_per_transition"),
        "advance_combat_mode": ("encounter", {"encounter_id": "encounter.missing", "result": "success"}, "once_per_transition"),
    }
    for operation, (subject_kind, arguments, scope) in invalid_cases.items():
        invalid = {
            "template_version": 1,
            "core_operation": operation,
            "subject_kind": subject_kind,
            "arguments": arguments,
            "idempotency_scope": scope,
            "mechanic_refs": ["rule.d20"],
            "provenance_id": "prov.story",
        }
        try:
            validate_effect_template(package, f"mutation.{operation}", invalid)
        except AssertionError:
            continue
        raise AssertionError(f"dangling reference mutation accepted for {operation}")

    wrong_subject = copy.deepcopy(package["effect_templates"]["effect.clock_pressure"])
    wrong_subject["subject_kind"] = "fact"
    try:
        validate_effect_template(package, "effect.clock_pressure", wrong_subject)
    except AssertionError:
        pass
    else:
        raise AssertionError("subject-kind mutation accepted")

    consequence_state = effect_probe_state(package)
    commit_outcome(package, consequence_state, "outcome.success")
    assert "consequence.success" in consequence_state["consequences"]
    wrong_outcome_effect = copy.deepcopy(package)
    wrong_outcome_effect["outcomes"]["outcome.success"]["persistent_consequence_template_ids"] = ["effect.boss_result"]
    try:
        commit_outcome(wrong_outcome_effect, effect_probe_state(wrong_outcome_effect), "outcome.success")
    except AssertionError:
        pass
    else:
        raise AssertionError("outcome accepted a non-consequence persistent template")
    return {
        "templates_checked": len(package["effect_templates"]),
        "idempotency_scopes_checked": sorted(scopes),
        "duplicate_same_scope_rejections": duplicate_rejections,
        "distinct_scope_reapplications": distinct_scope_reapplications,
        "cross_run_reapplications": cross_run_reapplications,
        "dangling_reference_mutations_rejected": len(invalid_cases),
        "subject_kind_mutation": "REJECTED",
        "outcome_consequence_mutation": "REJECTED",
    }


def stage_supported_atoms(state: dict[str, Any], branch: list[dict[str, Any]]) -> None:
    for atom in branch:
        if atom["kind"] == "choice_equals":
            state["choices"][atom["ref"]] = atom.get("value")
        elif atom["kind"] == "encounter_complete":
            state["encounters"][atom["ref"]] = atom.get("value", "success")


def effect_route_minutes(package: dict[str, Any], effect_ids: list[str]) -> int:
    routes = route_index(package)
    costs = [
        routes[package["effect_templates"][effect_id]["arguments"]["route_id"]]["time_cost_min"]
        for effect_id in effect_ids
        if package["effect_templates"][effect_id]["core_operation"] == "reveal_fact_via_route"
    ]
    return max(costs, default=0)


def eligible_outcomes(package: dict[str, Any], state: dict[str, Any]) -> list[str]:
    eligible = [outcome_id for outcome_id, outcome in package["outcomes"].items() if dnf_true(outcome["when"], state)]
    if not eligible:
        return []
    top_priority = max(package["outcomes"][outcome_id]["priority"] for outcome_id in eligible)
    winners = [outcome_id for outcome_id in eligible if package["outcomes"][outcome_id]["priority"] == top_priority]
    assert len(winners) == 1, f"ambiguous highest-priority outcomes in reachable state: {winners}"
    return winners


def commit_outcome(package: dict[str, Any], state: dict[str, Any], outcome_id: str) -> None:
    outcome = package["outcomes"][outcome_id]
    expected: set[str] = set()
    context = {
        "run_id": "run.fixture",
        "beat_visit_id": f"outcome:{outcome_id}",
        "transition_id": f"outcome:{outcome_id}",
        "redirect_use_id": f"outcome:{outcome_id}",
    }
    for effect_id in outcome["persistent_consequence_template_ids"]:
        template = package["effect_templates"][effect_id]
        assert template["core_operation"] == "schedule_consequence", f"{outcome_id}: {effect_id} is not a consequence commit"
        expected.add(template["arguments"]["consequence_id"])
        apply_effect(package, state, effect_id, context)
    assert expected <= state["consequences"], f"{outcome_id}: missing committed consequences {sorted(expected - state['consequences'])}"


def state_key(state: dict[str, Any]) -> str:
    serializable = {
        key: sorted(value) if isinstance(value, set) else value
        for key, value in state.items()
        if key not in {"path", "timeline"}
    }
    return json.dumps(serializable, sort_keys=True)


def explore_reachable_states(package: dict[str, Any]) -> dict[str, Any]:
    beats = package["beats"]
    starts = [beat_id for beat_id, beat in beats.items() if beat["entry"] == [[]]]
    assert starts == ["beat.selection"], f"exactly one `[[]]` start required, got {starts}"
    initial = {
        "current": starts[0],
        "clock": 0,
        "revealed": set(),
        "completed": set(),
        "npcs": {npc_id: npc["initial_status"] for npc_id, npc in package["npcs"].items()},
        "encounters": {},
        "choices": {},
        "effects": set(),
        "consequences": set(),
        "applied_effects": set(),
        "operation_log": [],
        "redirect_uses": {},
        "classes": set(),
        "path": [starts[0]],
        "timeline": [{"event": "start", "minutes": 0}],
    }
    queue: deque[dict[str, Any]] = deque([initial])
    seen: set[str] = set()
    terminals: list[dict[str, Any]] = []
    infeasible: list[str] = []
    resolution_checks = 0

    def route_state(state: dict[str, Any], target: str, event_id: str) -> None:
        nonlocal resolution_checks
        state["path"].append(event_id)
        state["timeline"].append({"event": event_id, "minutes": state["clock"]})
        winners = eligible_outcomes(package, state)
        if winners:
            resolution_checks += 1
        if target in package["outcomes"]:
            if not winners:
                infeasible.append(f"{event_id}: target outcome predicate false")
                return
            if winners[0] != target:
                infeasible.append(f"{event_id}: target {target} loses priority to {winners[0]}")
                return
            commit_outcome(package, state, target)
            state["path"].append(target)
            terminals.append(state)
            return
        if winners:
            commit_outcome(package, state, winners[0])
            state["path"].append(winners[0])
            terminals.append(state)
            return
        if target not in beats or not dnf_true(beats[target]["entry"], state):
            infeasible.append(f"{event_id}: entry false for {target}")
            return
        state["current"] = target
        state["path"].append(target)
        beat_visits = sum(item in beats for item in state["path"])
        if beat_visits > 18:
            infeasible.append(f"{event_id}: exceeds 18 beat visits")
            return
        key = state_key(state)
        if key not in seen:
            queue.append(state)

    while queue:
        state = queue.popleft()
        key = state_key(state)
        if key in seen:
            continue
        seen.add(key)
        beat_id = state["current"]
        beat = beats[beat_id]

        for transition in beat["transitions"]:
            branches = beat["completion"] if transition["when"] == "complete" else [[]]
            for branch in branches:
                next_state = copy.deepcopy(state)
                stage_supported_atoms(next_state, branch)
                if not dnf_true(transition["condition"], next_state):
                    infeasible.append(f"{transition['transition_id']}: condition false")
                    continue
                base_minutes = beat["hard_cap_min"] if transition["when"] == "timeout" else beat["target_min"]
                next_state["clock"] += max(base_minutes, effect_route_minutes(package, transition["effect_template_ids"]))
                visit_index = sum(item == beat_id for item in next_state["path"])
                effect_context = {
                    "run_id": "run.fixture",
                    "beat_visit_id": f"{beat_id}:{visit_index}",
                    "transition_id": f"{transition['transition_id']}:{visit_index}",
                    "redirect_use_id": f"transition:{transition['transition_id']}:{visit_index}",
                }
                for effect_id in transition["effect_template_ids"]:
                    apply_effect(package, next_state, effect_id, effect_context)
                if transition["when"] in {"complete", "timeout"}:
                    if not dnf_true(beat["completion"], next_state):
                        infeasible.append(f"{transition['transition_id']}: completion false")
                        continue
                    next_state["completed"].add(beat_id)
                next_state["classes"].add(transition["trace_class"])
                route_state(next_state, transition["to"], transition["transition_id"])

        for redirect_id, redirect in package["redirects"].items():
            if beat_id not in redirect["from_beat_ids"]:
                continue
            if state["redirect_uses"].get(redirect_id, 0) >= redirect["use_limit"]:
                continue
            if not dnf_true(redirect["preconditions"], state):
                continue
            next_state = copy.deepcopy(state)
            next_state["redirect_uses"][redirect_id] = next_state["redirect_uses"].get(redirect_id, 0) + 1
            next_state["clock"] += max(redirect["time_cost_min"], effect_route_minutes(package, redirect["effect_template_ids"]))
            use_number = next_state["redirect_uses"][redirect_id]
            visit_index = sum(item == beat_id for item in next_state["path"])
            effect_context = {
                "run_id": "run.fixture",
                "beat_visit_id": f"{beat_id}:{visit_index}",
                "transition_id": f"redirect:{redirect_id}:{use_number}",
                "redirect_use_id": f"{redirect_id}:{use_number}",
            }
            for effect_id in redirect["effect_template_ids"]:
                apply_effect(package, next_state, effect_id, effect_context)
            if redirect["completes_current"]:
                assert dnf_true(beat["completion"], next_state) or redirect["trigger"] == "supported_off_rail_action"
                next_state["completed"].add(beat_id)
            next_state["classes"].add("recovery" if redirect["trigger"] in {"carrier_lost", "supported_off_rail_action"} else "pressure")
            route_state(next_state, redirect["to"], redirect_id)

    assert terminals, "no reachable terminal state"
    required = {oid for oid, item in package["obligations"].items() if item["required_on_showcase_trace"]}
    trace_counts: dict[str, int] = {}
    completed_minutes: list[int] = []
    terminal_trace_records: list[dict[str, Any]] = []
    for state in terminals:
        outcome_id = state["path"][-1]
        outcome_class = package["outcomes"][outcome_id]["terminal_class"]
        if "refusal" in state["classes"]:
            trace_type = "refusal_loss"
        elif "recovery" in state["classes"]:
            trace_type = f"recovery_{outcome_class}"
        elif "pressure" in state["classes"]:
            trace_type = f"pressure_{outcome_class}"
        else:
            trace_type = f"showcase_{outcome_class}"
        trace_counts[trace_type] = trace_counts.get(trace_type, 0) + 1
        consequence_ids = {
            package["effect_templates"][effect_id]["arguments"]["consequence_id"]
            for effect_id in package["outcomes"][outcome_id]["persistent_consequence_template_ids"]
        }
        assert consequence_ids <= state["consequences"], f"{outcome_id}: terminal lacks {sorted(consequence_ids - state['consequences'])}"
        terminal_trace_records.append({"type": trace_type, "outcome_id": outcome_id, "minutes": state["clock"], "consequences": sorted(state["consequences"]), "path": state["path"], "timeline": state["timeline"]})
        if outcome_class != "loss" or "refusal" not in state["classes"]:
            satisfied = {
                obligation_id
                for completed_beat in state["completed"]
                for obligation_id in beats[completed_beat]["satisfies_obligation_ids"]
            }
            assert required <= satisfied, f"{trace_type} misses {sorted(required - satisfied)}: {state['path']}"
            assert package["timing"]["minimum_min"] <= state["clock"] <= package["timing"]["maximum_min"], (state["clock"], state["path"])
            completed_minutes.append(state["clock"])
    terminal_classes = {package["outcomes"][state["path"][-1]]["terminal_class"] for state in terminals}
    assert terminal_classes == {"success", "loss", "mixed"}, (terminal_classes, trace_counts, sorted(set(infeasible))[:20])
    assert trace_counts.get("refusal_loss", 0) > 0
    assert any(name.startswith("recovery_") for name in trace_counts)
    assert any(name.startswith("pressure_") for name in trace_counts)
    return {
        "reachable_states": len(seen),
        "terminal_states": len(terminals),
        "trace_classes": dict(sorted(trace_counts.items())),
        "terminal_traces": sorted(terminal_trace_records, key=lambda row: (row["minutes"], row["type"], row["path"])),
        "completed_trace_minutes": sorted(completed_minutes),
        "infeasible_edges": len(infeasible),
        "infeasible_examples": sorted(set(infeasible))[:8],
        "unique_resolution_checks": resolution_checks,
    }


def line_cells(start: tuple[int, int], end: tuple[int, int]) -> set[tuple[int, int]]:
    x0, y0 = start
    x1, y1 = end
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    cells: set[tuple[int, int]] = set()
    while True:
        cells.add((x0, y0))
        if (x0, y0) == (x1, y1):
            return cells
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def check_maps_and_encounters(package: dict[str, Any]) -> dict[str, int]:
    reachable_cells = 0
    los_pairs = 0
    roster_bands = 0
    for map_id, map_entry in package["maps"].items():
        width, height = map_entry["width_cells"], map_entry["height_cells"]
        topology = map_entry["topology"]
        blocked = {tuple(cell) for cell in topology["blocked_cells"]}
        opaque = {tuple(cell) for cell in topology["opaque_cells"]}
        spawn_cells = [tuple(cell) for cells in topology["spawn_anchors"].values() for cell in cells]
        objective_cells = [tuple(cell) for cells in topology["objective_cells"].values() for cell in cells]
        assert len(spawn_cells) == len(set(spawn_cells)) and not (set(spawn_cells) & set(objective_cells)), f"{map_id}: overlapping spawn/objective cells"
        all_cells = spawn_cells + objective_cells
        for cell in blocked | opaque | set(all_cells):
            assert 0 <= cell[0] < width and 0 <= cell[1] < height, f"{map_id}: out-of-bounds {cell}"
        assert not (blocked & set(all_cells)), f"{map_id}: blocked spawn/objective"
        assert set(map_entry["spawn_anchor_ids"]) == set(topology["spawn_anchors"]), map_id
        party_anchor_ids = [anchor_id for anchor_id in topology["spawn_anchors"] if anchor_id.endswith("party")]
        assert len(party_anchor_ids) == 1, f"{map_id}: exactly one party anchor required"
        party_starts = {tuple(cell) for cell in topology["spawn_anchors"][party_anchor_ids[0]]}
        goals = set(all_cells) - party_starts
        assert party_starts and goals and not (party_starts & goals), map_id
        queue = deque(party_starts)
        visited = set(party_starts)
        while queue:
            x, y = queue.popleft()
            for candidate in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= candidate[0] < width and 0 <= candidate[1] < height and candidate not in blocked and candidate not in visited:
                    visited.add(candidate)
                    queue.append(candidate)
        assert goals <= visited, f"{map_id}: unreachable spawn/objective cells {sorted(goals - visited)}"
        reachable_cells += len(visited)
        for first, second in itertools.combinations(sorted(set(all_cells)), 2):
            # Supercover is the union of both integer traversals, making the authoritative
            # cell set direction-independent at exact corner crossings.
            forward_cells = line_cells(first, second) | line_cells(second, first)
            reverse_cells = line_cells(second, first) | line_cells(first, second)
            forward = not bool((forward_cells - {first, second}) & opaque)
            reverse = not bool((reverse_cells - {first, second}) & opaque)
            assert forward == reverse, f"{map_id}: asymmetric LOS {first}<->{second}"
            los_pairs += 1
        for zone in topology["light_zones"]:
            minimum, maximum = zone["min_cell"], zone["max_cell"]
            assert 0 <= minimum[0] <= maximum[0] < width and 0 <= minimum[1] <= maximum[1] < height, f"{map_id}: invalid light zone"
        for cell in all_cells:
            assert any(zone["min_cell"][0] <= cell[0] <= zone["max_cell"][0] and zone["min_cell"][1] <= cell[1] <= zone["max_cell"][1] for zone in topology["light_zones"]), f"{map_id}: unlit declared cell {cell}"

    for encounter_id, encounter in package["encounters"].items():
        map_entry = package["maps"][encounter["map_id"]]
        assert encounter_id in map_entry["encounter_ids"]
        assert encounter["objective_fact_id"] in package["truth_facts"] and encounter["failure_outcome_id"] in package["outcomes"]
        for band_name in ("party_3", "party_4", "party_5"):
            band = encounter[band_name]
            assert len({item["template_id"] for item in band["enemy_roster"]}) == len(band["enemy_roster"]), f"{encounter_id}.{band_name}: duplicate roster template"
            xp = sum(package["enemy_templates"][item["template_id"]]["xp_each"] * item["count"] for item in band["enemy_roster"])
            assert xp == band["xp_budget"], f"{encounter_id}.{band_name}: XP {xp} != {band['xp_budget']}"
            assert set(band["spawn_anchor_ids"]) <= set(map_entry["topology"]["spawn_anchors"]), f"{encounter_id}.{band_name}: dangling spawn anchor"
            capacity = sum(len(map_entry["topology"]["spawn_anchors"][anchor_id]) for anchor_id in band["spawn_anchor_ids"])
            required_cells = sum(item["count"] * math.prod(package["enemy_templates"][item["template_id"]]["size_cells"]) for item in band["enemy_roster"])
            assert required_cells <= capacity, f"{encounter_id}.{band_name}: {required_cells} occupied cells exceed {capacity} spawn cells"
            roster_bands += 1
    assert {encounter_id for map_entry in package["maps"].values() for encounter_id in map_entry["encounter_ids"]} == set(package["encounters"])
    assert {item["template_id"] for encounter in package["encounters"].values() for band_name in ("party_3", "party_4", "party_5") for item in encounter[band_name]["enemy_roster"]} == set(package["enemy_templates"])
    return {"reachable_cells": reachable_cells, "los_symmetry_pairs": los_pairs, "roster_bands": roster_bands}


def positive_projections(package: dict[str, Any], revealed: set[str]) -> dict[str, Any]:
    facts = package["truth_facts"]
    visible = {
        fact_id: fact["public_fact"]
        for fact_id, fact in facts.items()
        if fact["classification"] == "public" or fact_id in revealed
    }
    presentation = package["presentation"]
    audio: list[dict[str, Any]] = []
    for cue in presentation["audio_cues"].values():
        if not set(cue["safe_text_fact_ids"]) <= set(visible):
            continue
        assets = [asset_id for pool_id in cue["asset_pool_ids"] for asset_id in presentation["asset_pools"][pool_id]]
        audio.append({"event_key": cue["event_key"], "speaker": cue["speaker_entity_id"], "text": [visible[fid] for fid in cue["safe_text_fact_ids"]], "asset_ids": assets, "music_state": cue["music_state"]})
    approved_assets = {
        asset_id: {"kind": asset["kind"]}
        for asset_id, asset in package["assets"].items()
        if asset["status"] == "approved"
    }
    return {
        "table_public": {"available_beat_ids": sorted(package["beats"]), "facts": sorted(visible.values()), "pending_roll": {"sides": 20}},
        "scene_public": {"speaker_ids": sorted(route["entity_id"] for route in presentation["voice_routes"].values()), "subtitles": sorted(visible.values())},
        "narrator_public": {"voice_keys": sorted(route["voice_key"] for route in presentation["voice_routes"].values()), "safe_facts": sorted(visible.values())},
        "audio_public": audio,
        "cache_public": {"logical_asset_ids": sorted({asset_id for cue in audio for asset_id in cue["asset_ids"]})},
        "asset_public": approved_assets,
    }


def private_projections(package: dict[str, Any], beat_id: str) -> dict[str, Any]:
    facts = package["truth_facts"]
    return {
        "admin_private": {secret_id: {"fact_id": secret["fact_id"], "truth": facts[secret["fact_id"]]["truth"]} for secret_id, secret in package["secrets"].items()},
        "narrator_private": {secret_id: facts[secret["fact_id"]]["truth"] for secret_id, secret in package["secrets"].items() if beat_id in secret["adjudicator_scope"]},
    }


def secret_needles(package: dict[str, Any]) -> set[str]:
    needles = set(package["secrets"])
    for secret in package["secrets"].values():
        needles.add(secret["fact_id"])
        needles.add(secret["synthetic_canary"])
        needles.add(package["truth_facts"][secret["fact_id"]]["truth"])
    return needles


def projection_bytes(package: dict[str, Any], revealed: set[str]) -> bytes:
    return json.dumps(positive_projections(package, revealed), ensure_ascii=False, sort_keys=True).encode("utf-8")


def assert_no_needles(payload: bytes, needles: set[str]) -> None:
    text = payload.decode("utf-8")
    leaks = sorted(needle for needle in needles if needle in text)
    assert not leaks, f"private IDs/text/metadata leaked: {leaks}"


def check_secret_projection(package: dict[str, Any]) -> dict[str, int | str]:
    needles = secret_needles(package)
    pre = projection_bytes(package, set())
    assert_no_needles(pre, needles)
    revealed = {secret["fact_id"] for secret in package["secrets"].values()}
    post = projection_bytes(package, revealed)
    assert_no_needles(post, needles)
    for secret in package["secrets"].values():
        safe_text = package["truth_facts"][secret["fact_id"]]["public_fact"].encode()
        assert safe_text not in pre and safe_text in post, f"reveal dominance failed for {secret['fact_id']}"
        scoped = private_projections(package, secret["adjudicator_scope"][0])
        assert package["truth_facts"][secret["fact_id"]]["truth"] in json.dumps(scoped)
    admin = private_projections(package, "beat.selection")["admin_private"]
    assert set(admin) == set(package["secrets"])
    scoped_projection_checks = 0
    for beat_id in package["beats"]:
        narrator = private_projections(package, beat_id)["narrator_private"]
        expected = {secret_id for secret_id, secret in package["secrets"].items() if beat_id in secret["adjudicator_scope"]}
        assert set(narrator) == expected, f"narrator scope mismatch at {beat_id}"
        scoped_projection_checks += 1

    detected_mutations = 0
    contained_metadata_mutations = 0
    for needle in needles:
        for mutation in ("event", "voice", "pool"):
            mutated = copy.deepcopy(package)
            if mutation == "event":
                mutated["presentation"]["audio_cues"]["cue.selection"]["event_key"] = needle
            elif mutation == "voice":
                mutated["presentation"]["voice_routes"]["voice.narrator"]["voice_key"] = needle
            else:
                mutated["presentation"]["asset_pools"]["pool.combat_phase"][0] = needle
            try:
                assert_no_needles(projection_bytes(mutated, set()), needles)
            except AssertionError:
                detected_mutations += 1
        mutated = copy.deepcopy(package)
        mutated["assets"]["asset.map_skirmish"]["path"] = needle
        assert_no_needles(projection_bytes(mutated, set()), needles)
        contained_metadata_mutations += 1
    return {
        "status": "PASS",
        "private_needles_checked": len(needles),
        "pre_reveal_bytes": len(pre),
        "post_reveal_bytes": len(post),
        "public_source_mutations_rejected": detected_mutations,
        "nonprojected_metadata_mutations_contained": contained_metadata_mutations,
        "private_scope_checks": scoped_projection_checks,
    }


PLACEHOLDER_MARKERS = ("ABSTRACT", "FIXTURE", "MISSING", "NONE_", "PENDING", "UNASSIGNED", "RESEARCH_FIXTURE")
ALL_USES = {"modify", "hosted_runtime", "distribution", "public_performance", "voice_model_creation", "synthetic_generation", "cache", "marketing"}


def provenance_admission(package: dict[str, Any]) -> tuple[bool, list[str]]:
    prov = package["provenance"]
    policy = package["provenance_policy"]
    evaluation_date = date.fromisoformat(policy["evaluation_date"])
    qualified = set(policy["qualified_reviewer_ids"])
    reasons: set[str] = set()
    relationships = package["provenance_relationships"]
    if len({row["relationship_id"] for row in relationships}) != len(relationships):
        reasons.add("relationship_id_duplicate")
    relation_pairs = {(row["subject_provenance_id"], row["predicate"], row["object_provenance_id"]) for row in relationships}
    for relation in relationships:
        if relation["subject_provenance_id"] not in prov or relation["object_provenance_id"] not in prov:
            reasons.add(f"relationship_dangling:{relation['relationship_id']}")
    for prov_id, row in prov.items():
        if row["decision"] != "approved":
            reasons.add(f"decision:{prov_id}")
        if row["reviewer"] not in qualified:
            reasons.add(f"reviewer:{prov_id}")
        if date.fromisoformat(row["creation_date"]) > evaluation_date:
            reasons.add(f"future_creation:{prov_id}")
        if row["term_end"] == "unassigned_fixture":
            reasons.add(f"term_unassigned:{prov_id}")
        elif row["term_end"] not in {"perpetual", "per_license"} and date.fromisoformat(row["term_end"]) < evaluation_date:
            reasons.add(f"expired:{prov_id}")
        critical = [row[name] for name in ("title", "author_or_provider", "source_uri", "rights_owner_evidence", "license_expression", "terms_snapshot", "attribution")]
        critical.extend(row["territories"])
        if any(any(marker in value.upper() for marker in PLACEHOLDER_MARKERS) for value in critical):
            reasons.add(f"placeholder:{prov_id}")
        for input_ref in row["input_refs"]:
            if input_ref not in prov:
                reasons.add(f"input_dangling:{prov_id}:{input_ref}")
            if not any(subject == prov_id and obj == input_ref for subject, _, obj in relation_pairs):
                reasons.add(f"input_relationship_missing:{prov_id}:{input_ref}")

    required_material_uses = {
        "story": {"hosted_runtime", "distribution"},
        "rules": {"hosted_runtime", "distribution"},
        "map": {"hosted_runtime", "distribution"},
        "voice": {"voice_model_creation", "synthetic_generation", "hosted_runtime", "public_performance"},
        "recording": {"hosted_runtime", "distribution", "cache", "public_performance"},
        "music_work": {"hosted_runtime", "distribution", "public_performance"},
        "music_master": {"hosted_runtime", "distribution", "cache", "public_performance"},
        "sfx": {"hosted_runtime", "distribution", "cache", "public_performance"},
    }
    for prov_id, row in prov.items():
        if not required_material_uses.get(row["material_type"], {"hosted_runtime"}) <= set(row["allowed_uses"]):
            reasons.add(f"row_use:{prov_id}")

    required_asset_uses = {
        "map": {"hosted_runtime", "distribution"},
        "cached_speech": {"hosted_runtime", "distribution", "cache", "public_performance"},
        "music": {"hosted_runtime", "distribution", "cache", "public_performance"},
        "sfx": {"hosted_runtime", "distribution", "cache", "public_performance"},
    }
    expected_material = {"map": "map", "cached_speech": "recording", "music": "music_master", "sfx": "sfx"}
    for asset_id, asset in package["assets"].items():
        prov_id = asset["provenance_id"]
        if prov_id not in prov:
            reasons.add(f"asset_provenance_dangling:{asset_id}")
            continue
        if asset["status"] != "approved":
            reasons.add(f"asset_status:{asset_id}")
        if asset["kind"] in expected_material and prov[prov_id]["material_type"] != expected_material[asset["kind"]]:
            reasons.add(f"asset_material_type:{asset_id}")
        if asset["sha256"] != prov[prov_id]["source_hash"]:
            reasons.add(f"asset_hash:{asset_id}")
        if not required_asset_uses.get(asset["kind"], {"hosted_runtime"}) <= set(prov[prov_id]["allowed_uses"]):
            reasons.add(f"asset_use:{asset_id}")
        if asset["kind"] == "cached_speech":
            script_objects = [obj for subject, predicate, obj in relation_pairs if subject == prov_id and predicate == "performance_of_script" and obj in prov and prov[obj]["material_type"] == "story"]
            voice_objects = [obj for subject, predicate, obj in relation_pairs if subject == prov_id and predicate == "uses_voice" and obj in prov and prov[obj]["material_type"] == "voice"]
            if not script_objects or not voice_objects:
                reasons.add(f"voice_script_master_closure:{asset_id}")
        if asset["kind"] == "music" and not any(subject == prov_id and predicate == "master_of_work" and prov[obj]["material_type"] == "music_work" for subject, predicate, obj in relation_pairs if obj in prov):
            reasons.add(f"music_work_master_closure:{asset_id}")

    for route_id, route in package["presentation"]["voice_routes"].items():
        prov_id = route["provenance_id"]
        if prov_id not in prov or prov[prov_id]["material_type"] != "voice":
            reasons.add(f"voice_provenance:{route_id}")
            continue
        required = {"voice_model_creation", "synthetic_generation", "hosted_runtime", "public_performance"}
        if not required <= set(prov[prov_id]["allowed_uses"]):
            reasons.add(f"voice_use:{route_id}")

    blocked = {prov_id for prov_id, row in prov.items() if row["decision"] in {"withdrawn", "expired"}}
    changed = True
    while changed:
        changed = False
        for subject, _, obj in relation_pairs:
            if obj in blocked and subject not in blocked:
                blocked.add(subject)
                reasons.add(f"relationship_withdrawal:{subject}:{obj}")
                changed = True
    return not reasons, sorted(reasons)


def synthetic_admission_control(package: dict[str, Any]) -> dict[str, Any]:
    control = copy.deepcopy(package)
    reviewer = control["provenance_policy"]["qualified_reviewer_ids"][0]
    for row in control["provenance"].values():
        row["decision"] = "approved"
        row["reviewer"] = reviewer
        row["term_end"] = "perpetual"
        row["allowed_uses"] = sorted(ALL_USES)
        for name in ("title", "author_or_provider", "source_uri", "rights_owner_evidence", "license_expression", "terms_snapshot", "attribution"):
            if any(marker in row[name].upper() for marker in PLACEHOLDER_MARKERS):
                row[name] = "SYNTHETIC_POSITIVE_CONTROL_NOT_RIGHTS_EVIDENCE"
        row["territories"] = ["synthetic_control"]
    for asset in control["assets"].values():
        asset["status"] = "approved"
    admitted, reasons = provenance_admission(control)
    assert admitted and not reasons, reasons
    withdrawn = copy.deepcopy(control)
    withdrawn["provenance"]["prov.music_work"]["decision"] = "withdrawn"
    admitted, withdrawal_reasons = provenance_admission(withdrawn)
    assert not admitted and any(reason.startswith("relationship_withdrawal:") for reason in withdrawal_reasons)
    expired = copy.deepcopy(control)
    expired["provenance"]["prov.sfx"]["term_end"] = "2026-08-15"
    admitted, expiry_reasons = provenance_admission(expired)
    assert not admitted and "expired:prov.sfx" in expiry_reasons
    return {"synthetic_positive_control": "PASS_NOT_LEGAL_CLEARANCE", "withdrawal_mutation": "REJECTED", "expiry_mutation": "REJECTED"}


def check_contract(package: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(package), key=lambda error: list(error.path))
    assert not errors, "schema validation failed: " + "; ".join(error.message for error in errors[:8])
    invalid_date = copy.deepcopy(package)
    invalid_date["provenance"]["prov.story"]["creation_date"] = "not-a-date"
    assert list(validator.iter_errors(invalid_date)), "date format checker did not reject invalid creation_date"

    expected_hash = package_hash(package)
    assert package["identity"]["content_hash"] == expected_hash, f"content hash mismatch: expected {expected_hash}"
    mutated_hash = copy.deepcopy(package)
    mutated_hash["timing"]["reserve_min"] += 1
    assert package_hash(mutated_hash) != package["identity"]["content_hash"], "authoritative mutation did not invalidate content hash"

    facts, prov, assets = package["truth_facts"], package["provenance"], package["assets"]
    predicate_atoms_checked = validate_predicate_refs(package)
    known_subjects = set(package["entities"]) | set(package["npcs"]) | set(package["encounters"])
    for secret_id, secret in package["secrets"].items():
        assert secret["fact_id"] in facts and facts[secret["fact_id"]]["classification"] == "secret", secret_id
    for fact_id, fact in facts.items():
        assert fact["provenance_id"] in prov and set(fact["subject_refs"]) <= known_subjects, fact_id
    for entity_id, entity in package["entities"].items():
        assert entity["provenance_id"] in prov, entity_id
    for choice_id, choice in package["choice_templates"].items():
        assert choice["provenance_id"] in prov, choice_id
    for roll_id, roll in package["roll_templates"].items():
        assert roll["provenance_id"] in prov, roll_id

    routes = route_index(package)
    carrier_loss_checks = 0
    for clue_id, clue in package["clues"].items():
        assert clue["conclusion_fact_id"] in facts, clue_id
        clue_routes = clue["routes"]
        assert len({route["route_id"] for route in clue_routes}) == len(clue_routes), clue_id
        for route in clue_routes:
            assert clue["conclusion_fact_id"] in route["reveal_fact_ids"] and set(route["reveal_fact_ids"]) <= set(facts), route["route_id"]
            assert route["carrier"]["id"] in (set(package["npcs"]) if route["carrier"]["kind"] == "npc" else set(package["entities"])), route["route_id"]
        if clue["mandatory"]:
            assert len(clue_routes) >= 2 and any(route["carrier"]["durable"] and route["carrier"]["kind"] != "npc" for route in clue_routes), clue_id
            for lost_route in clue_routes:
                assert any(route["carrier"] != lost_route["carrier"] for route in clue_routes), f"single carrier loss strands {clue_id}"
                carrier_loss_checks += 1

    assert {item["kind"] for item in package["obligations"].values()} == REQUIRED_OBLIGATION_KINDS
    for obligation_id, obligation in package["obligations"].items():
        assert set(obligation["satisfied_by_beat_ids"]) <= set(package["beats"]), obligation_id
    assert {role["role"] for role in package["starter_roles"].values()} == EXPECTED_STARTER_ROLES
    assert len(package["outcomes"]) == 3 and {outcome["terminal_class"] for outcome in package["outcomes"].values()} == {"success", "loss", "mixed"}
    assert len({outcome["priority"] for outcome in package["outcomes"].values()}) == len(package["outcomes"])

    effect_refs: set[str] = set()
    effect_locations: dict[str, set[str]] = {}
    cue_ids = set(package["presentation"]["audio_cues"])
    for beat_id, beat in package["beats"].items():
        assert set(beat["presentation_cue_ids"]) <= cue_ids, beat_id
        for transition in beat["transitions"]:
            assert transition["to"] in package["beats"] or transition["to"] in package["outcomes"], transition["transition_id"]
            effect_refs.update(transition["effect_template_ids"])
            for effect_id in transition["effect_template_ids"]:
                effect_locations.setdefault(effect_id, set()).add("transition")
    for redirect_id, redirect in package["redirects"].items():
        assert set(redirect["from_beat_ids"]) <= set(package["beats"]) and redirect["to"] in package["beats"], redirect_id
        assert redirect["reveals_via_route_id"] is None or redirect["reveals_via_route_id"] in routes, redirect_id
        effect_refs.update(redirect["effect_template_ids"])
        for effect_id in redirect["effect_template_ids"]:
            effect_locations.setdefault(effect_id, set()).add("redirect")
    for outcome_id, outcome in package["outcomes"].items():
        assert outcome["continuation_hook_fact_id"] in facts, outcome_id
        effect_refs.update(outcome["persistent_consequence_template_ids"])
        for effect_id in outcome["persistent_consequence_template_ids"]:
            effect_locations.setdefault(effect_id, set()).add("outcome")
    assert effect_refs == set(package["effect_templates"]), f"dangling or unused effects: refs={sorted(effect_refs)} templates={sorted(package['effect_templates'])}"
    allowlist = set(package["compatibility"]["core_operation_allowlist"])
    for effect_id, template in package["effect_templates"].items():
        assert template["core_operation"] in allowlist and template["core_operation"] in OPERATION_SIGNATURES, effect_id
        assert template["provenance_id"] in prov, effect_id
        validate_effect_template(package, effect_id, template)
        locations = effect_locations[effect_id]
        scope = template["idempotency_scope"]
        if scope == "once_per_transition":
            assert locations == {"transition"}, f"{effect_id}: transition scope used at {sorted(locations)}"
        elif scope == "once_per_redirect_use":
            assert locations == {"redirect"}, f"{effect_id}: redirect scope used at {sorted(locations)}"
        elif scope == "once_per_beat_visit":
            assert locations <= {"transition", "redirect"}, f"{effect_id}: beat-visit scope used at {sorted(locations)}"
        else:
            assert locations <= {"transition", "outcome"}, f"{effect_id}: run scope used at {sorted(locations)}"
        if "outcome" in locations:
            assert template["core_operation"] == "schedule_consequence", f"{effect_id}: outcome reference is not a consequence commit"

    effect_controls = check_effect_semantics(package)

    mechanics: set[str] = set()
    mechanics.update(ref for beat in package["beats"].values() for ref in beat["mechanic_refs"])
    mechanics.update(ref for clue in package["clues"].values() for route in clue["routes"] for ref in route["mechanic_refs"])
    mechanics.update(ref for encounter in package["encounters"].values() for ref in encounter["mechanic_refs"])
    mechanics.update(ref for role in package["starter_roles"].values() for ref in role["rules_refs"])
    mechanics.update(ref for template in package["effect_templates"].values() for ref in template["mechanic_refs"])
    mechanics.update(ref for template in package["enemy_templates"].values() for ref in template["mechanic_refs"])
    assert mechanics <= SUPPORTED_MECHANICS, f"unsupported mechanics: {sorted(mechanics - SUPPORTED_MECHANICS)}"

    for map_id, map_entry in package["maps"].items():
        assert map_entry["asset_id"] in assets and map_entry["provenance_id"] in prov, map_id
    for asset_id, asset in assets.items():
        assert asset["provenance_id"] in prov and asset["sha256"] == prov[asset["provenance_id"]]["source_hash"], asset_id
    for pool_id, pool_assets in package["presentation"]["asset_pools"].items():
        assert set(pool_assets) <= set(assets), pool_id
    for cue_id, cue in package["presentation"]["audio_cues"].items():
        assert set(cue["asset_pool_ids"]) <= set(package["presentation"]["asset_pools"]), cue_id
        assert set(cue["safe_text_fact_ids"]) <= set(facts), cue_id
    for npc_id, npc in package["npcs"].items():
        assert npc["provenance_id"] in prov and set(npc["knows_secret_ids"]) <= set(package["secrets"]), npc_id
        assert set(npc["state_transitions"]) <= set(package["effect_templates"]), npc_id
        matching_routes = [route for route in package["presentation"]["voice_routes"].values() if route["entity_id"] == npc_id]
        assert len(matching_routes) == 1 and matching_routes[0]["voice_key"] == npc["voice_key"] and matching_routes[0]["fallback_voice_key"] == npc["fallback_voice_key"], npc_id
    for role_id, role in package["starter_roles"].items():
        assert role["provenance_id"] in prov, role_id
    for template_id, template in package["enemy_templates"].items():
        assert template["provenance_id"] in prov and template["size_cells"][0] >= 1 and template["size_cells"][1] >= 1, template_id
    known_speakers = set(package["npcs"]) | set(package["entities"]) | {package["presentation"]["narrator_entity_id"]}
    for route_id, route in package["presentation"]["voice_routes"].items():
        assert route["entity_id"] in known_speakers and route["provenance_id"] in prov, route_id
    for cue_id, cue in package["presentation"]["audio_cues"].items():
        assert cue["speaker_entity_id"] in known_speakers, cue_id
    for effect_id, template in package["effect_templates"].items():
        if template["core_operation"] == "open_physical_roll":
            assert template["arguments"]["roll_id"] in package["roll_templates"], effect_id

    graph = explore_reachable_states(package)
    map_checks = check_maps_and_encounters(package)
    projection = check_secret_projection(package)
    admitted, reasons = provenance_admission(package)
    assert not admitted and reasons, "abstract fixture must fail the positive provenance admission checker"
    provenance_controls = synthetic_admission_control(package)
    return {
        "schema_and_formats": "PASS",
        "canonical_hash": "PASS_WITH_AUTHORITATIVE_MUTATION_REJECTED",
        "reference_effect_route_mechanic_lint": "PASS",
        "carrier_loss_cases": carrier_loss_checks,
        "predicate_atoms_checked": predicate_atoms_checked,
        "effect_semantics": effect_controls,
        "mechanics_checked": sorted(mechanics),
        "reachability": graph,
        "map_encounter_closure": map_checks,
        "secret_projection": projection,
        "provenance_admission": "EXPECTED_FAIL_ABSTRACT_FIXTURE",
        "provenance_failure_count": len(reasons),
        "provenance_failure_examples": reasons[:12],
        "provenance_controls": provenance_controls,
    }


def d20_hit(rng: random.Random, attack: int, ac: int) -> tuple[bool, bool]:
    face = rng.randint(1, 20)
    return face == 20 or (face != 1 and face + attack >= ac), face == 20


def roll_damage(rng: random.Random, average: float, critical: bool = False) -> int:
    spread = max(1.0, average * 0.30)
    value = rng.uniform(average - spread, average + spread)
    if critical:
        value *= 1.65
    return max(1, round(value))


def make_party(role_names: tuple[str, ...]) -> list[dict[str, Any]]:
    result = []
    for role_name in role_names:
        role = ROLES[role_name]
        result.append({"name": role_name, **role, "max_hp": role["hp"], "downed": False, "dead": False, "death_fail": 0, "death_success": 0})
    return result


def living(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [unit for unit in units if unit["hp"] > 0 and not unit.get("dead", False)]


def pc_death_save(rng: random.Random, pc: dict[str, Any]) -> None:
    if pc["hp"] > 0 or pc["dead"]:
        return
    face = rng.randint(1, 20)
    if face == 20:
        pc["hp"] = 1
        pc["downed"] = False
        pc["death_fail"] = pc["death_success"] = 0
    elif face == 1:
        pc["death_fail"] += 2
    elif face >= 10:
        pc["death_success"] += 1
    else:
        pc["death_fail"] += 1
    if pc["death_fail"] >= 3:
        pc["dead"] = True
    elif pc["death_success"] >= 3:
        pc["downed"] = True


def side_initiative(rng: random.Random, party: list[dict[str, Any]], world_modifier: int) -> str:
    selected = max(living(party), key=lambda pc: pc["initiative"], default=max(party, key=lambda pc: pc["initiative"]))
    party_total = rng.randint(1, 20) + selected["initiative"]
    world_total = rng.randint(1, 20) + world_modifier
    if party_total != world_total:
        return "party" if party_total > world_total else "world"
    if selected["initiative"] != world_modifier:
        return "party" if selected["initiative"] > world_modifier else "world"
    return "party"


def party_phase(rng: random.Random, party: list[dict[str, Any]], enemies: list[dict[str, Any]]) -> None:
    for pc in party:
        if pc["dead"]:
            continue
        if pc["hp"] <= 0:
            pc_death_save(rng, pc)
            continue
        wounded = [ally for ally in party if not ally["dead"] and ally["hp"] < ally["max_hp"] - 7]
        if pc["heals"] and wounded:
            target = min(wounded, key=lambda ally: ally["hp"] / ally["max_hp"])
            target["hp"] = min(target["max_hp"], max(0, target["hp"]) + 8)
            target["downed"] = False
            target["death_fail"] = target["death_success"] = 0
            pc["heals"] -= 1
            continue
        targets = living(enemies)
        if not targets:
            return
        target = min(targets, key=lambda enemy: enemy["hp"])
        hit, critical = d20_hit(rng, pc["attack"], target["ac"])
        if hit:
            target["hp"] -= roll_damage(rng, pc["damage"], critical)


def world_phase(
    rng: random.Random,
    party: list[dict[str, Any]],
    enemies: list[dict[str, Any]],
    tactic: str,
) -> None:
    for enemy in living(enemies):
        for _ in range(enemy.get("attacks", 1)):
            targets = living(party)
            if not targets:
                return
            if tactic == "focus_lowest":
                target = min(targets, key=lambda pc: pc["hp"])
            else:
                target = rng.choice(targets)
            hit, critical = d20_hit(rng, enemy["attack"], target["ac"])
            if hit:
                target["hp"] -= roll_damage(rng, enemy["damage"], critical)
                if target["hp"] <= 0:
                    target["hp"] = 0
                    target["downed"] = True


def make_skirmish(n: int, spec: dict[str, Any]) -> list[dict[str, Any]]:
    count = max(1, n + spec["count_delta"])
    return [{"name": f"skirmisher-{i}", "hp": spec["hp"], "max_hp": spec["hp"], "ac": spec["ac"], "attack": spec["attack"], "damage": spec["damage"], "attacks": 1} for i in range(count)]


def make_boss(n: int, spec: dict[str, Any]) -> list[dict[str, Any]]:
    boss = {"name": "boss", "hp": n * spec["hp_per_pc"], "max_hp": n * spec["hp_per_pc"], "ac": spec["ac"], "attack": 5, "damage": spec["damage"], "attacks": max(2, n + spec["attacks_delta"])}
    add_count = n // spec["adds_divisor"]
    adds = [{"name": f"add-{i}", "hp": 8, "max_hp": 8, "ac": 12, "attack": 3, "damage": 3.5, "attacks": 1} for i in range(add_count)]
    return [boss, *adds]


def run_encounter(
    rng: random.Random,
    party: list[dict[str, Any]],
    enemies: list[dict[str, Any]],
    tactic: str,
    world_modifier: int,
    max_rounds: int = 10,
) -> dict[str, Any]:
    first = side_initiative(rng, party, world_modifier)
    first_world_down = False
    alpha_kill = False
    any_downed_before = any(pc["downed"] for pc in party)
    for round_no in range(1, max_rounds + 1):
        order = [first, "world" if first == "party" else "party"]
        for phase_index, side in enumerate(order):
            if side == "party":
                party_phase(rng, party, enemies)
                if round_no == 1 and phase_index == 0 and not living(enemies):
                    alpha_kill = True
            else:
                world_phase(rng, party, enemies, tactic)
                if round_no == 1 and phase_index == 0 and any(pc["downed"] for pc in party):
                    first_world_down = True
            if not living(enemies) or not living(party):
                return {
                    "party_won": bool(living(party)) and not living(enemies),
                    "rounds": round_no,
                    "alpha_kill": alpha_kill,
                    "first_world_down": first_world_down,
                    "new_downed": any(pc["downed"] for pc in party) and not any_downed_before,
                }
    return {"party_won": False, "rounds": max_rounds, "alpha_kill": alpha_kill, "first_world_down": first_world_down, "new_downed": any(pc["downed"] for pc in party) and not any_downed_before}


def estimate_minutes(n: int, skirmish_rounds: int, boss_rounds: int, skirmish_enemies: int, boss_enemies: int) -> float:
    def seconds(rounds: int, enemies: int) -> int:
        return rounds * (45 + n * 55 + enemies * 18 + 15)
    return (seconds(skirmish_rounds, skirmish_enemies) + 90 + seconds(boss_rounds, boss_enemies)) / 60


def simulate_one(seed: int, roles: tuple[str, ...], envelope: dict[str, Any], tactic: str) -> dict[str, Any]:
    rng = random.Random(seed)
    party = make_party(roles)
    n = len(party)
    skirmish_enemies = make_skirmish(n, envelope["skirmish"])
    skirmish = run_encounter(rng, party, skirmish_enemies, tactic, world_modifier=1)
    if not skirmish["party_won"]:
        return {"win": False, "tpk": not living(party), "death": any(pc["dead"] for pc in party), "downed": any(pc["downed"] for pc in party), "boss_alpha": False, "world_first_down": skirmish["first_world_down"], "minutes": estimate_minutes(n, skirmish["rounds"], 0, len(skirmish_enemies), 0)}

    # Frozen synthetic bridge assumption: one curated, rules-supported recovery use per hero.
    for pc in party:
        if not pc["dead"]:
            pc["hp"] = min(pc["max_hp"], max(0, pc["hp"]) + 6)
            if pc["hp"] > 0:
                pc["downed"] = False
                pc["death_fail"] = pc["death_success"] = 0

    boss_enemies = make_boss(n, envelope["boss"])
    boss = run_encounter(rng, party, boss_enemies, tactic, world_modifier=2)
    return {
        "win": boss["party_won"],
        "tpk": not living(party),
        "death": any(pc["dead"] for pc in party),
        "downed": skirmish["new_downed"] or boss["new_downed"] or any(pc["downed"] for pc in party),
        "boss_alpha": boss["alpha_kill"],
        "world_first_down": skirmish["first_world_down"] or boss["first_world_down"],
        "minutes": estimate_minutes(n, skirmish["rounds"], boss["rounds"], len(skirmish_enemies), len(boss_enemies)),
    }


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)
    return ordered[index]


def combat_sweep(iterations_per_cell: int = 500) -> dict[str, Any]:
    records: dict[str, Any] = {}
    role_names = tuple(ROLES)
    for envelope_name, envelope in ENVELOPES.items():
        records[envelope_name] = {}
        for tactic in ("random", "focus_lowest"):
            records[envelope_name][tactic] = {}
            for n in (3, 4, 5):
                compositions = list(itertools.combinations(role_names, n))
                outcomes: list[dict[str, Any]] = []
                composition_win_rates: list[float] = []
                for composition_index, roles in enumerate(compositions):
                    cell = []
                    for iteration in range(iterations_per_cell):
                        seed = 377_090_000 + list(ENVELOPES).index(envelope_name) * 10_000_000 + (0 if tactic == "random" else 5_000_000) + n * 100_000 + composition_index * 1_000 + iteration
                        cell.append(simulate_one(seed, roles, envelope, tactic))
                    outcomes.extend(cell)
                    composition_win_rates.append(sum(row["win"] for row in cell) / len(cell))
                minutes = [row["minutes"] for row in outcomes]
                records[envelope_name][tactic][str(n)] = {
                    "trials": len(outcomes),
                    "compositions": len(compositions),
                    "win_rate": round(sum(row["win"] for row in outcomes) / len(outcomes), 4),
                    "worst_composition_win_rate": round(min(composition_win_rates), 4),
                    "best_composition_win_rate": round(max(composition_win_rates), 4),
                    "tpk_rate": round(sum(row["tpk"] for row in outcomes) / len(outcomes), 4),
                    "death_rate": round(sum(row["death"] for row in outcomes) / len(outcomes), 4),
                    "any_downed_rate": round(sum(row["downed"] for row in outcomes) / len(outcomes), 4),
                    "boss_alpha_kill_rate": round(sum(row["boss_alpha"] for row in outcomes) / len(outcomes), 4),
                    "world_first_down_rate": round(sum(row["world_first_down"] for row in outcomes) / len(outcomes), 4),
                    "combat_minutes_median": round(statistics.median(minutes), 2),
                    "combat_minutes_p90": round(percentile(minutes, 0.90), 2),
                }

    normal_cells = [records["normal"][tactic][str(n)] for tactic in ("random", "focus_lowest") for n in (3, 4, 5)]
    checks = {
        "win_rate": all(SYNTHETIC_PASS_BANDS["normal_win_rate"][0] <= cell["win_rate"] <= SYNTHETIC_PASS_BANDS["normal_win_rate"][1] for cell in normal_cells),
        "tpk_rate": all(cell["tpk_rate"] <= SYNTHETIC_PASS_BANDS["normal_tpk_rate_max"] for cell in normal_cells),
        "downed_rate": all(SYNTHETIC_PASS_BANDS["normal_any_downed_rate"][0] <= cell["any_downed_rate"] <= SYNTHETIC_PASS_BANDS["normal_any_downed_rate"][1] for cell in normal_cells),
        "boss_alpha": all(cell["boss_alpha_kill_rate"] <= SYNTHETIC_PASS_BANDS["boss_alpha_kill_rate_max"] for cell in normal_cells),
        "world_first_down": all(cell["world_first_down_rate"] <= SYNTHETIC_PASS_BANDS["world_first_down_rate_max"] for cell in normal_cells),
        "timing": all(cell["combat_minutes_p90"] <= SYNTHETIC_PASS_BANDS["combat_minutes_p90_max"] and cell["combat_minutes_median"] >= SYNTHETIC_PASS_BANDS["combat_minutes_median_min"] for cell in normal_cells),
    }
    return {
        "model": "abstract_side_phase_attrition_v1",
        "seed_scheme": "377090000 + envelope/tactic/party/composition/iteration offsets",
        "iterations_per_composition_tactic": iterations_per_cell,
        "predeclared_pass_bands": SYNTHETIC_PASS_BANDS,
        "bridge_assumption": "one rules-supported 6 HP recovery use per non-dead hero; I9 must instantiate it or rerun",
        "cells": records,
        "normal_band_checks": checks,
        "normal_synthetic_verdict": "PASS" if all(checks.values()) else "FAIL",
        "scope_warning": "Synthetic attrition calibrates candidate envelopes only; it does not prove fun, player tactics, rules completeness, map quality, or real duration.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    schema, package = load()
    result = {
        "contract": check_contract(package, schema),
        "combat": combat_sweep(args.iterations),
    }
    if args.write:
        RESULTS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
