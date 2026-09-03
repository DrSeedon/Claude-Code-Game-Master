# R4 synthetic fault matrix

## Reproduction

Run from the repository root:

```bash
uv run --frozen pytest -q docs/tasks/377/phase3/r4/test_durability_probe.py
uv run --frozen python docs/tasks/377/phase3/r4/durability_probe.py \
  --output docs/tasks/377/phase3/r4/probe-results.json
```

Observed on 2026-08-16:

```text
...................                                                      [100%]
19 passed in 8.78s
```

`probe-results.json` records 38 scenario/model rows: 19/19 passed for `event_log_checkpoints` and 19/19 passed for `transactional_state_dedupe_outbox`. The candidate implementations use Python 3.11 `sqlite3`, WAL, `synchronous=FULL`, deterministic state, fixed IDs, no network, no provider, and the synthetic canary `GM_ONLY_CANARY_377_R4`.

## Predeclared oracle and selection rule

The harness constant `SELECTION_RULE` was written before the recorded run:

> Reject a candidate on any common-oracle failure. If both pass, prefer the candidate whose cold recovery reads canonical current state directly and does not require semantic event replay on the availability path.

Every successful complete trace must satisfy:

1. exact duplicate returns the stored result;
2. final authoritative `world.mutation_count == 1` and `world.revision == 1`;
3. crash/reopen preserves byte-equivalent state at the fault boundary;
4. recovery finishes with `stage=committed` and `recovery_action=none`;
5. durable player projection equals the client projection and contains no canary;
6. one stable audio job exists;
7. both candidates produce the same world, projection, and stored world-command result digests.
8. accepted command/result, durable event, player projection, and audio records validate against `command-event-schemas.json`; statically forbidden actor/command combinations fail closed.

The harness does not claim that TCP/WebSocket delivery is exactly once. It deliberately delivers duplicates and tests effects-once reduction.

## Candidate shapes held constant

Both candidates share the same command decision function, event evolution function, projection allowlist, fixed command sequence, expected versions, and client reducer. Only persistence/recovery differs.

| Candidate | Canonical representation | Dedupe/result | Projection delivery | Corruption check |
|---|---|---|---|---|
| event log + checkpoints | append-only schema-valid typed events; derived checkpoint every four events | separate checksummed `command_results` keyed by `(room_id, command_id)` | stable projection event replay + persisted attempts + ack event | checksum every canonical event on cold recovery; checkpoint checksum binds event position + state; fail loud |
| transactional state + dedupe + outbox | one checksummed current aggregate row updated with world/result/task in one SQLite transaction | checksummed `command_results` keyed by `(room_id, command_id)` | checksummed projection/audio outbox plus post-reducer ack | current-state, result, and outbox checksums; fail loud |

The transactional candidate also appends non-canonical audit/domain rows in the same transaction. These rows support inspection but are not replay prerequisites.

## Crash/restart matrix

Fault injection happens immediately after the named durable operation and before the caller can rely on an acknowledgement. The process is represented by closing and reopening a new store instance on the same SQLite file. The exact last command is then retried; every row below returned its stored result/event.

| Fault point | Expected reload observation | Event log + checkpoints | Transactional state + outbox |
|---|---|---:|---:|
| receive | `drafting`; mutation 0; `retry_draft` | PASS | PASS |
| draft persist | `awaiting_approval`; mutation 0; `wait_for_approval` | PASS | PASS |
| approval | `executing`; mutation 0; `start_execution` | PASS | PASS |
| execution start | `executing`; mutation 0; `retry_uncommitted_execution` | PASS | PASS |
| world commit | `presenting`; mutation 1; `resume_projection`; never rerun kernel | PASS | PASS |
| outbox publish | `presenting`; mutation 1; the same `event_id` republishes | PASS | PASS |
| projection ack | `committed`; mutation 1; `enqueue_audio` | PASS | PASS |
| audio enqueue | `committed`; mutation 1; `none`; one job | PASS | PASS |

All 16 recovered complete traces ended at the same values:

```text
world_digest      d4990f6b92655c1484c3d50b53f5b5382b4af7872be091f246cfc9a54f36cc2c
projection_digest f79f7cecfe1c3b19631cbd9af14c7d9972b7dffc0c538ed08082786a241935ce
world mutations   1
client applies    1
audio jobs        1
```

The stored world-command result was byte-equivalent in both candidates:

```json
{"aggregate_version":5,"code":"WorldCommitted","command_id":"cmd-world","request_digest":"91b10415d63ec97a83f9a4b727b1d54b06f1c6381fcf6327ed506837059e9df7","room_id":"room-synthetic","schema_version":1,"stage":"presenting","status":"accepted","turn_id":"turn-0001","world_mutation_count":1,"world_revision":1}
```

## Ordering, duplicate, projection, and corruption matrix

| Scenario | Required observation | Event log + checkpoints | Transactional state + outbox |
|---|---|---:|---:|
| approve before draft | stored `invalid_stage`; zero mutation | PASS | PASS |
| player forges internal `commit_world` | JSON contract and runtime reject actor/capability combination; zero mutation | PASS | PASS |
| redraft v2 then approve v1 | stored `stale_draft`; current draft remains v2; zero mutation | PASS | PASS |
| same `command_id`, different payload | schema-valid `idempotency_conflict`; first transition/result remains | PASS | PASS |
| same `command_id` in another room | separate stored `wrong_aggregate`; no first-room result leak | PASS | PASS |
| duplicate world command after completion | exact stored result; mutation remains 1 | PASS | PASS |
| late provider event after commit | stored `late_provider_event`; mutation remains 1 | PASS | PASS |
| schema-shaped audio/image outputs | one valid audio job; disclosed image prompt; canary absent from both | PASS | PASS |
| replay/live overlap | both deliveries carry same ID; reducer applies once | PASS | PASS |
| reducer fails before ack | cursor does not advance; same event replays and applies once | PASS | PASS |
| unknown secret-bearing world field | world remains committed; no player event; safe `unknown_world_field`; canary absent from projection/result | PASS | PASS |
| canonical row corruption | reload raises `IntegrityFailure`; no skip or guessed state | PASS | PASS |
| checkpoint position/outbox payload corruption | recovery raises `IntegrityFailure`; no stale checkpoint or corrupt delivery accepted | PASS | PASS |

The first table counts eight crash scenarios per model. The second list covers eleven additional harness scenarios per model; duplicate world, late-provider, and audio/image boundary checks share one scenario row in `probe-results.json`.

## Cold-recovery evidence

Golden-path durable row counts from the same run:

| Metric | Event log + checkpoints | Transactional state + outbox |
|---|---:|---:|
| canonical current-state rows read | checkpoint + suffix | 1 |
| canonical event rows integrity-checked at cold recovery | 8 | 0 |
| semantic events replayed after latest checkpoint | 0 | 0 |
| command-result rows | 8 | 8 |
| audit/canonical event rows | 8 canonical | 8 non-canonical audit |
| projection/audio delivery rows | 1 delivery-attempt + 1 audio job | 3 outbox + 1 ack + 1 audio job |

The 4 KiB SQLite file-size result for both candidates is page-allocation noise and is not used for selection. This micro-harness also does not use wall-clock timing as an architecture metric.

The event candidate’s zero suffix replay came from a checkpoint exactly at event 8. It still verified all eight canonical events to meet the fail-loud corruption oracle. A production design could move full-chain scrubbing off startup, but then cold availability would temporarily depend on a trusted checkpoint and a separately specified background integrity guarantee. That alternative was not measured.

## What the harness establishes

- Either persistence family can satisfy the common correctness oracle when all authoritative facts share one SQLite transaction boundary and every external delivery uses stable IDs.
- Event sourcing is not required for the observable guarantee.
- The selected transactional candidate makes recovery inspect one canonical current-state row and outstanding outbox work; event history remains useful as non-canonical audit evidence.
- Projection and audio are retryable after world commit without re-entering execution.
- Unknown player-projection shape fails closed while preserving the committed canonical world and last safe view.

## Limits and counter-evidence

- `close()`/reopen at a committed boundary tests commit-before-ack ambiguity and process restart. It does not simulate torn storage sectors, kernel/filesystem bugs, disk-full behavior, multi-node failover, or actual `SIGKILL` at every SQLite instruction.
- SQLite WAL/full-sync behavior is exercised through the standard library, but the harness uses one process and one writer. Contention, busy timeouts, backup/restore, and capacity require later deployment tests.
- Projection failure uses a synthetic unknown-field canary and a deterministic reducer exception, not a browser or production schema migration.
- Event log + checkpoints passed every correctness case. Its rejection is not justified; it loses the tie only under the predeclared direct-recovery rule for this single-authority MVP.
- The result forbids coupling a separately committed world file/database to either coordinator by assumption. That topology needs a new idempotent kernel protocol and unknown-commit experiment before use.
