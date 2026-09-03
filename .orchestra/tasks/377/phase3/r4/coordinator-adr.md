# ADR R4 — durable approval coordinator persistence

- Status: accepted for downstream R7/I1 contract work
- Date: 2026-08-16
- Decision owner: backend/reliability lead
- Scope: research artifact only; no product repository or runtime implementation was created
- Decision: transactional current state + command deduplication + transactional outbox, with non-canonical append-only audit/domain events

## Decision in one sentence

Use one remote authoritative SQLite database transaction to commit the coordinator aggregate, approved world mutation, stored command result, audit/domain records, and a projection task; deliver player projection and audio through stable-ID outboxes with acknowledgements only after consumer reduction. Keep append-only history for audit, but do not make semantic replay of that history a prerequisite for restart.

## Question

### Context

The canonical MVP has a remote authoritative backend, versioned drafts, explicit approval before mutation, three browser surfaces, server-only world secrets, provider adapters, and recovery after reconnect/restart [1]. The previous system demonstrated unacknowledged input, replay/live duplication, cursor-before-render, lost in-progress work, cross-file commit gaps, and denylist projection failure modes [1][2].

### Change under test

Compare two independently persisted shapes behind the same state decisions and client reducer:

1. append-only event log as canonical state + derived checkpoints + command result/delivery metadata;
2. transactional current state + command-result dedupe + projection/audio outbox + non-canonical audit events.

### Baseline

The baseline is persistence-neutral, not an existing runtime: exact retries return their stored result; an approved typed world command mutates once; crash/reopen produces the same committed state and player projection; any stage not yet committed is explicitly recoverable; projection/audio retries never repeat the world command [2][3].

### Measurable outcome

Both candidates run one deterministic harness across receive, draft persist, approval, execution start, world commit, projection publish, projection acknowledgement, audio enqueue, stale/out-of-order/duplicate commands, restart, late provider events, replay/live overlap, reducer failure, secret projection failure, and canonical corruption [3][4]. A candidate fails on any common-oracle violation. If both pass, the predeclared tie-break prefers direct canonical-state recovery without semantic event replay on the availability path [3].

## Hypotheses and falsifiers

| Hypothesis | Why it might be true | What would prove it wrong | Result |
|---|---|---|---|
| **H1 — canonical event log + checkpoints is necessary for deterministic recovery and replayable projections.** | Immutable events give auditability and can rebuild projections after a crash. | Transactional current state/outbox passes every identical-state, duplicate, restart, replay, secret, and corruption oracle without treating audit events as canonical. | **REFUTED as a necessity.** The event candidate passed, but the transactional candidate also passed 19/19 cases and produced the same observable digests [3]. |
| **H2 — transactional state + dedupe + outbox is the smaller recovery-critical model for this single authority.** | World/result/task can commit together; restart reads current state and pending work directly. | It loses/duplicates a mutation or output, cannot make pre-commit stage explicit, or requires more canonical reconstruction than the event candidate. | **CONFIRMED within the harness.** It passed 19/19, read one canonical aggregate row, replayed zero semantic events, and resumed explicit outbox work [3]. |
| **H3 — either model remains safe when coordinator and world commit independently.** | Stable command IDs might hide the cross-store gap. | A crash can leave “world applied, coordinator/result unknown,” requiring a distributed transaction or whole-turn replay. | **REFUTED by the contract analysis.** The measured guarantee depends on one authoritative transaction; the ticket explicitly rejects unknown commit/distributed-transaction dependence [1][4]. That alternate topology was not implemented or credited. |
| **H4 — delivery exactly once can be obtained from the transport.** | A broker could try to suppress duplicates. | Replay/live overlap delivers one stable event twice while the consumer still applies it once. | **REFUTED.** Both stores emitted the same ID twice; the reducer applied once and acknowledged only after success [3]. The contract is at-least-once delivery + effects-once reduction. |

## Method

`durability_probe.py` implements two stores over separate SQLite WAL files with `synchronous=FULL`. The stores share:

- one pure command decision function;
- one event evolution function;
- one initial synthetic world and fixed command sequence;
- the same aggregate/draft/provider versions and IDs;
- the same fail-closed player projection;
- the same synthetic canary;
- one client reducer and common assertions.

Only the durable representation and recovery path vary. Each crash case closes the store immediately after the named durable operation and before the caller can rely on an acknowledgement, reopens a fresh connection, retries the same command/event, inspects the persisted recovery action, and finishes the trace. The edge cases run on fresh databases. `test_durability_probe.py` mechanically checks every row; `probe-results.json` is the full recorded result [3].

The experiment is synthetic by instruction. It invokes no provider, browser, production service, real world state, private repository, or Orchestra runtime. Orchestra is used only as Phase 1 prior art [2].

## Findings

### F1 — both persistence families can meet the common oracle

**CONFIRMED — tier 1 direct measurement.** Each candidate passed eight crash/reload cases and eleven protocol/ordering/delivery/corruption cases, 19/19 each. The author verification run was `19 passed in 8.78s` [3].

Every complete trace produced:

- world digest `d4990f6b92655c1484c3d50b53f5b5382b4af7872be091f246cfc9a54f36cc2c`;
- player projection digest `f79f7cecfe1c3b19631cbd9af14c7d9972b7dffc0c538ed08082786a241935ce`;
- `world_mutation_count=1`;
- one client reducer application;
- one audio job;
- byte-equivalent stored `WorldCommitted` result [3].

This refutes a selection based solely on the labels “event sourcing” or “outbox.” Correct transaction and ID boundaries dominate the label.

### F2 — the transactional model has the narrower synchronous recovery path in the measured scope

**CONFIRMED — tier 1 direct structural measurement, limited to the synthetic trace.** Its cold state load verified one canonical aggregate row and replayed zero semantic events. It recovered delivery work from three outbox rows (projection task, player projection, audio enqueue) plus one durable ack [3].

The event candidate had a checkpoint exactly at the eighth and final event, so it replayed zero suffix events, but it still integrity-checked all eight canonical events to satisfy the fail-loud corruption oracle. Its command-result table remained necessary for immediate duplicate-result lookup [3].

Database file size was 4 KiB for both due SQLite page allocation and is discarded as non-evidence. No wall-clock microbenchmark is used for the decision.

### F3 — world commit, result, stage, and projection intent need one database commit

**CONFIRMED — tier 1 fault measurement plus tier 2 canonical requirement.** After faults before world commit, both candidates reloaded with mutation zero and an explicit uncommitted recovery action. After the world commit fault, both reloaded `presenting`, mutation one, and `resume_projection`; duplicate execution returned the stored result rather than calling the kernel again [1][3].

This evidence does not transfer to a separately committed `world.json` or another database. That arrangement recreates the unknown-commit gap excluded by R4 [4].

### F4 — projection publication and acknowledgement are different durable facts

**CONFIRMED — tier 1 direct measurement.** A fault after publish replayed the same event. Replay/live overlap delivered the same ID twice and applied once. An injected reducer failure left the cursor unadvanced; replay then applied once and allowed the ack [3].

Therefore `publish_attempted` is not delivery success. The durable cursor moves only after reducer commit, and brokers may duplicate rather than drop durable events.

### F5 — projection failure must fail closed without undoing or replaying the world commit

**CONFIRMED — tier 1 direct measurement.** Both candidates committed the synthetic world mutation once, detected an unknown secret-bearing canonical field, published no player event, retained the previous safe projection, exposed only `unknown_world_field`, and reloaded with `repair_projection_schema`. The canary appeared in neither player projection nor stored projection result [3].

The admin recovery surface may show the safe error, turn/revision IDs, and recovery action; it must not receive the unknown canonical value.

The ordinary successful trace also persisted a schema-valid audio job and a disclosed image prompt; the synthetic canary was absent from both. The unknown-field trace produced neither a projection event nor an audio job [3].

### F6 — stale, duplicate, out-of-order, and late inputs are durable results

**CONFIRMED — tier 1 direct measurement.** Both models stored and replayed `invalid_stage` for approval before a draft, `stale_draft` for approving v1 after redraft v2, and `late_provider_event` after commit. Same-ID/different-payload reuse returned an idempotency conflict. `(room_id, command_id)` scoping prevented a same-ID cross-room result leak. Duplicate world commit returned the original schema-valid result and mutation remained one [3].

Deduplication precedes expected-version and stage checks. Otherwise a retry of a once-valid command could become a different error after state advances.

### F7 — the measured protocol records conform to the declared schemas and capability boundary

**CONFIRMED — tier 1 direct measurement.** The harness validates every admitted command, returned/stored result, durable event envelope, player projection, and audio job through JSON Schema Draft 2020-12. Internal execution/projection/audio commands require a server coordinator actor; provider events require a server provider actor. A forged player `commit_world` was rejected by schema admission and runtime without mutation in both candidates [3].

## Decision

Select **transactional current state + command dedupe + outbox** for I1.

### Required durable records

The names are logical; R7/I1 may choose physical table names without weakening the constraints.

| Record | Authority/invariant |
|---|---|
| coordinator/world aggregate | current turn stage/substage, aggregate/world versions, approved draft reference, execution attempt, canonical world state, last safe projection reference, explicit recovery action; checksummed/versioned |
| immutable drafts | `(turn_id, draft_version)` unique; approved version never changes |
| command results | `(room_id, command_id)` unique; canonical request digest + full stored result; checked before current version/stage |
| projection/audio outbox | stable event/task ID; kind; safe payload or server-only task reference; state/attempts; checksummed |
| delivery acknowledgements | monotonic per room/surface/consumer; exact event and reducer/schema version; update only after reduction |
| audio jobs | stable `line_id/context_id`; unique enqueue; retries/cancellation separated from world execution |
| audit/domain events | append-only, causal command/turn/version IDs; written in the same transaction but not required to reconstruct current state |

### Atomic boundaries

1. **Command admission transaction:** stored rejection, or state transition + stored result + audit event.
2. **World commit transaction:** approved typed kernel mutation + new world/coordinator version + structured result + audit/domain events + server-only projection task.
3. **Projection transaction:** read the committed version, build an exact allowlisted projection, persist snapshot/event/outbox; on failure persist only a safe error and keep the last safe snapshot.
4. **Projection ack transaction:** advance the consumer cursor, mark the stable event acknowledged, transition the turn to committed, and create the audio enqueue task.
5. **Audio enqueue transaction:** create one stable job and mark the outbox task done. Playback delivery remains repeatable/cancellable without a kernel call.

All writes use a single authoritative database. Provider requests and browser delivery occur outside transactions after their intent/task is durable.

## Why not canonical event sourcing for I1

The event-log candidate is viable and passed every correctness case. It is not selected because this MVP has one remote authority, needs direct operational inspection/recovery, and has no measured requirement for arbitrary point-in-time reconstruction. In the recorded trace, canonical replay added no observable correctness while retaining a command-result index and a checkpoint/integrity lifecycle. Current state plus outbox met the same oracle with a direct canonical read [3].

Append-only audit/domain rows remain in the selected design. The decision is about which representation is authoritative on restart, not whether domain events exist.

Reopen the decision if a later measured requirement needs multiple independently rebuilt projections, temporal queries over arbitrary past versions, cross-service event distribution, or offline deterministic re-simulation that current snapshots/audit rows cannot satisfy. A new decision must reuse the common oracle and add schema-upcast/checkpoint-loss cases.

## Consequences

### Positive

- Restart answers “accepted?”, “approved version?”, “world committed?”, “projection acknowledged?”, and “audio pending?” by reading current records and outbox state.
- Duplicate commands return an immutable result without depending on current stage.
- Projection/audio failures cannot reopen game execution.
- Operational admin recovery can expose one explicit action rather than “retry turn.”
- Audit remains available without making availability depend on replay/upcasters.

### Costs and risks

- Current-state migrations require schema/version discipline and backup/restore tests.
- The audit log is non-canonical; audit/state divergence must be monitored even though state remains authoritative.
- SQLite remains a single-writer authority; writer contention, busy timeouts, disk-full handling, backups, and failover are unmeasured.
- Outbox consumers must be idempotent. No broker can substitute for stable event IDs and post-reducer ack.
- Projection repair after a newly unknown field needs an audited reproject operation; silently dropping fields or exposing them is forbidden.

## Stop/falsification conditions for implementation

Stop I1 and return to R4 if any implementation:

- stores the canonical world in a separately committed file/database without a measured idempotent unknown-commit protocol;
- acknowledges a command before its result/state commit;
- checks current version/stage before exact command dedupe;
- retries a whole turn after the world revision may have committed;
- advances a projection cursor before reducer success;
- publishes an unknown/failed projection or carries world-secret fields into an admin/browser/audio payload;
- uses payload text/content hashes as the sole replay dedupe identity;
- treats audio retry/cancel as a reason to call the game kernel;
- skips corrupt canonical state or outbox rows.

## Counter-evidence and limitations

1. **Against claiming event sourcing is inferior:** it passed all 19 cases, supplies a natural immutable history, and may win when rebuildable multi-consumer projections become a measured requirement [3].
2. **Against claiming production readiness:** the probe is single-process SQLite with synthetic state. It does not cover disk-full, real `SIGKILL` timing, concurrent writers, filesystem damage, backup restore, multi-node failover, browser implementation, or network partition [3].
3. **Against treating the selected outbox as magic:** correctness came from the one-database commit, stored command result, stable IDs, and post-reducer ack. Moving world state or effects outside that boundary invalidates the evidence.
4. **Against wholesale reuse:** Phase 1 calls Orchestra useful prior art but explicitly excludes copying its worktree/subagent/systemd/quota machinery; licensing/reuse clearance belongs to R8 [1][2]. No Orchestra source or runtime code was copied.
5. **Against hiding projection failures:** the safe last projection can temporarily lag committed world state. The UI/admin must display the degraded/repair state; pretending convergence before a safe projection exists would violate the oracle.

## Review gate inputs

- Changed/created consumers: research artifacts and synthetic probes only; downstream consumers are R7 surface contract and I1/R5/R6 implementations.
- Risk floor: high — persistence, command/event protocol, message delivery, recovery, and secret projection conclusions.
- Author runtime: Orchestra Codex runtime; no versioned model ID was exposed in repository/session metadata available to this artifact.
- Exact AC: R4 ticket in `docs/tasks/377/plan.md:130-144` and the persistence-neutral common oracle above.
- Mechanical check: `uv run --frozen pytest -q docs/tasks/377/phase3/r4/test_durability_probe.py` → `19 passed in 8.78s`.
- Independent oracle status: the harness was created during this research, so it is evidence but not a pre-existing independent oracle. The high-risk gate therefore requires Sol technical review; a same-family verdict is not called cross-family independent review [5].

## Sources

1. **[1] Tier 2 primary local source:** `docs/tasks/377/mvp-product-spec.ru.md`, especially §§5–6, 8–9, 14, 16–18, 20, 22, 25. Canonical product decisions and mandatory guarantees, fixed 2026-08-16.
2. **[2] Tier 2 primary local evidence:** `docs/tasks/377/research.md`, especially the confirmed current-flow failures, persistence-neutral minimum, capability matrices, replay/live probe, counter-evidence, and Phase 1 conclusion; plus `docs/tasks/377/codex-review-research.md` for preserved dissent.
3. **[3] Tier 1 direct measurement:** `durability_probe.py`, `test_durability_probe.py`, `probe-results.json`, and `fault-matrix.md`. Run in this worktree on 2026-08-16.
4. **[4] Tier 2 primary task contract:** `docs/tasks/377/plan.md:130-144`, exact R4 evidence, common oracle, falsification, privacy, and acceptance criteria.
5. **[5] Process source:** `.codex/skills/codex-debate/SKILL.md`, review routing and completed-verdict evidence rules, read in full before review.
