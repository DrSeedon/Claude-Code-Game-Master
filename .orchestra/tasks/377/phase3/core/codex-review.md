<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

The package has a coherent architectural direction: one remote-authoritative aggregate, immutable authored/rules inputs, typed plans, deterministic reducers, R4-style transactional persistence, and positive player-safe projections. It also preserves earlier dissent and treats literal reuse/IP cautiously.

It is not yet one internally consistent MVP contract. Several load-bearing guarantees in `core-adr.md` and the matrices are weaker or absent in the schema and probe. Most critically, the probe permits forged resolution effects and stale provider attempts, and does not durably deduplicate many invalid commands.

Verification run:

```text
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project "$PWD" --frozen pytest -q docs/tasks/377/phase3/core/test_research_core_probe.py
..                                                                       [100%]
2 passed in 1.01s
```

This is supportive synthetic evidence, not an independent oracle.

## Findings

1. blocking: [research_core_probe.py:949](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:949) — `apply_damage` accepts any positive `amount` and any target whenever `resolution_id` merely exists in `roll_ledger`. It never proves that the resolution succeeded, identifies that target, authorizes that damage amount/type, or has not already been consumed. Healing and conditions have the same existence-only binding at lines 967–995. A candidate plan can therefore cite an unrelated old roll and forge arbitrary damage, contradicting the server-derived-resolution requirement in [core-adr.md:263](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-adr.md:263) and Matrix M2. Make resolution records contain closed authorized effects and consume those effects exactly once; add wrong-target, wrong-amount, failed-roll, and reused-resolution counterexamples.

2. blocking: [research_core_probe.py:823](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:823) — unusual-plan validation checks only that `provider_attempt_id` is a string. There is no comparison with a currently persisted provider attempt, while `CoordinatorTurn` stores only `execution_attempt_id`. A late output from a cancelled/redrafted provider attempt can therefore be accepted by `turn.prepare`. This contradicts the version boundary and late-provider oracle. Persist the expected provider attempt before dispatch and bind `turn.prepare` to its turn, draft, expected version, and status; test stale and cancelled attempts.

3. blocking: [research_core_probe.py:518](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:518) — validator, lifecycle, nonce, pending-roll, combat-cursor, and unknown-operation failures raise `Rejected`, then the broad exception handler rolls back everything. Only early authorization/version failures call `_store_rejection`. Thus many “new invalid command” retries are neither durably recorded nor deduplicated, contrary to [core-adr.md:331](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-adr.md:331). The unknown-operation test explicitly expects an exception rather than a stored result. Convert post-admission `Rejected` outcomes into transactional stored command results and verify exact retry/conflicting digest behavior.

4. blocking: [research_core_probe.py:1095](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:1095) — `schedule_consequence` trusts the plan-supplied `instance_id`; effects-once is implemented only as equality against that supplied string. The same template and cause can be scheduled repeatedly under fresh IDs. This violates the ADR’s requirement that the kernel derive the stable instance from definition element plus causal command/transition. Remove authoritative `instance_id` from candidate-plan arguments or validate it against a server-derived value, then test different IDs for the same cause.

5. blocking: [core-contract.schema.json:941](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-contract.schema.json:941) — `ProjectionFamily` cannot enforce that its top-level, table, scene, and admin aggregate/world versions agree. A schema-valid mixed-version family directly contradicts the “mixed versions never render” contract. The probe tests only its own correctly generated batch. Add a machine-enforced family identity mechanism or a mandatory cross-field validator and a negative test that swaps one nested surface version/batch.

6. suggestion: [core-contract.schema.json:878](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-contract.schema.json:878) — the table projection lacks the action card, nonce, declared cost/check/stakes, visible proposed effect, legal-action hints, resources, and public events promised by [core-adr.md:311](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-adr.md:311). Consequently the probe approves by constructing a command directly; it never demonstrates safe pre-approval disclosure or that the displayed card corresponds to the stored plan digest. Define a player-safe `ApprovalCard` projection that binds to the immutable plan without exposing hidden operations/facts, and test both correspondence and secret exclusion.

7. suggestion: [research_core_probe.py:913](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:913) — `move_entity`, `phase.end_players`, and `phase.execute_world` implement side-phase checks regardless of `combat.mode`; `classic_order` and `classic_index` are never used for admission or advancement. The classic test proves only that a mode string and order were stored, not that the classic scheduler works over the same state. The “confirmed structurally/synthetically” conclusion is therefore stronger than the evidence. Add equivalent legal/illegal action and cursor-transition cases in both modes, including wrong-initiative rejection.

8. suggestion: [core-adr.md:365](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-adr.md:365) — the coverage summary overstates several areas. The probe does not exercise death-save semantics, actual six-starter mechanics, reconnect replay, stale provider/audio events, all transaction write boundaries, or classic scheduling. Its pre-commit failpoint is only after command/event insertion, and the assertion compares aggregate state without proving result/event/outbox absence. Narrow the coverage statement and add explicit negative oracles before using these as Phase 2 gates.

## Verdict

Needs work. The aggregate boundary and authority model are promising, and the seven-primitive disposition, authored-truth semantics, R4/R7 integration, and reuse/IP closure are directionally coherent. However, the four authority/idempotency defects and the mixed-version projection gap prevent approval of the package as the canonical Phase 1 MVP contract.

Review route: Sol technical review. Cross-family verdict unavailable.

## Round (2026-08-16T19:34:24Z)

<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

Round 1 dissent remains preserved verbatim in [codex-review.md](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/codex-review.md). Re-reviewing the complete package found all eight prior findings fixed across prose, schema, matrices, disposition, and executable probe.

Exact requested command result:

```text
..                                                                       [100%]
2 passed in 1.52s
```

## Findings

1. blocking, Round 1 #1 — **FIXED.** `_consume_resolution_effect` requires an exact unconsumed effect tuple, including operation, target, amount, and damage type ([research_core_probe.py:1106](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:1106)). Negative cases cover wrong target, amount, failed roll, and reuse.

2. blocking, Round 1 #2 — **FIXED.** `turn.begin_adjudication` persists the running attempt before candidate work; prepare and cancel compare against current durable identity/status ([research_core_probe.py:645](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:645)). Cancelled and stale attempts are durably rejected and deduped.

3. blocking, Round 1 #3 — **FIXED.** Post-admission `Rejected` exceptions roll back and become stored command results ([research_core_probe.py:610](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:610)). The nonce oracle verifies exact retry and conflicting-digest behavior.

4. blocking, Round 1 #4 — **FIXED.** `schedule_consequence` accepts only `template_id`; the reducer derives identity from template and causal command ([research_core_probe.py:1376](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:1376)). A supplied `instance_id` fails the closed operation shape.

5. blocking, Round 1 #5 — **FIXED.** A mandatory cross-field validator compares every nested projection’s aggregate/world versions with the outer family ([research_core_probe.py:1500](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:1500)); the schema explicitly documents the non-expressible JSON Schema invariant and the probe rejects a mixed family.

6. suggestion, Round 1 #6 — **FIXED.** `ApprovalCard` and `TableProjection` now expose plan digest, nonce, intent, costs/check/stakes, visible effects, hints, resources, and public events through closed schemas ([core-contract.schema.json:1014](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-contract.schema.json:1014)). The pre-approval probe checks binding and absence of operations/secrets.

7. suggestion, Round 1 #7 — **FIXED.** Classic mode enforces the persisted cursor actor and deterministically advances/wraps initiative ([research_core_probe.py:883](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/research_core_probe.py:883)). The probe covers wrong actor and a complete round.

8. suggestion, Round 1 #8 — **FIXED.** Coverage claims are now explicitly bounded in [core-adr.md:369](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/ai-table-architecture/docs/tasks/377/phase3/core/core-adr.md:369). All four simulated pre-commit write boundaries compare aggregate state and every table count; death-save edges and latest-safe reconnect are covered while real UI/audio/providers/class mechanics remain unproven.

No new blocking defects found.

## Verdict

**APPROVED as the canonical Phase 1 research conclusion.** Schema, probe, ADR, matrices, prior-finding disposition, and evidence claims now agree on the reviewed load-bearing seams. This does not constitute production readiness.

Review route: Round 2 Sol technical re-review. Cross-family verdict unavailable.
