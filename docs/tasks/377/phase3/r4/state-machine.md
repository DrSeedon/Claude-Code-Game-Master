# R4 durable approval coordinator state machine

Status: decision contract for I1/R5/R6/R7; persistence choice is recorded in `coordinator-adr.md`.

## Observable guarantee

“Exactly once” is an observable application guarantee, not a claim that networks deliver once. The authoritative database applies a previously approved typed kernel command at most once and durably stores its result under `command_id`. Network and worker delivery are at-least-once; stable IDs, stored results, consumer deduplication, and post-reducer acknowledgements make retries observe the same result:

> one accepted typed command → one authoritative world mutation; an exact duplicate → the stored result; restart → the same committed world and player projection; any stage before commit → an explicit recovery action.

This guarantee is valid only when the coordinator state, world state, command result, and projection task share one authoritative database transaction. A separate `world.json`, provider-owned state, browser state, or another database cannot participate in this guarantee without a new measured protocol.

## State graph

```text
                     redraft(new draft_version)
                    ┌──────────────────────────┐
                    │                          ▼
listening ─receive─▶ drafting ─persist────▶ awaiting_approval
                                             │
                          approve(current) ───┘
                                             ▼
                         executing [approval persisted]
                                             │
                              start_execution│ [attempt persisted before provider work]
                                             │
                         commit_world (one DB transaction)
                                             ▼
                       presenting [world committed; projection pending]
                           │                         │
              projection failure              projection ready
                           │                         │
            presenting + explicit repair       publish at-least-once
                           │                         │
                           └────── reproject ────────┤
                                                     │ reducer success + durable ack
                                                     ▼
                              committed [audio enqueue may still be pending]
                                                     │
                                      enqueue/retry/cancel audio only
                                                     ▼
                              committed [no pending technical stage]
```

`error` is reserved for a fail-loud invariant violation or non-retryable validation failure that requires operator inspection. Ordinary stale/out-of-order commands do not move the aggregate to `error`; their rejected result is itself persisted and idempotent.

## Durable states and recovery

| State | Durable evidence | Commands accepted | Explicit recovery after restart | World mutation allowed? |
|---|---|---|---|---:|
| `listening` | room/aggregate version | `receive` for a new immutable `turn_id` | none | no |
| `drafting` | accepted transcript identity; `recovery_action=retry_draft` | `persist_draft` | retry draft generation with a new provider attempt, or return to input | no |
| `awaiting_approval` | immutable current `draft_version`; text; `recovery_action=wait_for_approval` | `approve(current)`, `redraft(next)` | render the stored draft and wait | no |
| `executing`, no attempt | accepted approval and exact draft version; `recovery_action=start_execution` | `start_execution` | persist an execution attempt before invoking a provider/kernel | no |
| `executing`, attempt present | `execution_attempt_id`; `recovery_action=retry_uncommitted_execution` | exactly one `commit_world` for the approved typed command | inspect authoritative result by `command_id`; if absent, retry only the uncommitted execution under the same IDs | no, until the commit transaction |
| `presenting`, task pending | committed world revision/result; `recovery_action=resume_projection` | internal `prepare_projection` | build a player-safe projection from committed state | already exactly one |
| `presenting`, event ready | stable projection `event_id`; `recovery_action=publish_projection` | `ack_projection(event_id)` after reducer success | replay the same event at-least-once | already exactly one |
| `presenting`, projection failed | safe error code; last safe projection; `recovery_action=repair_projection_schema` | audited reproject after repair | do not publish; keep last safe table view; world commit remains inspectable | already exactly one |
| `committed`, audio pending | projection ack/cursor; stable `line_id/context_id`; `recovery_action=enqueue_audio` | internal enqueue, retry, or cancel audio | enqueue/retry audio only | already exactly one |
| `committed`, quiescent | result, projection ack, audio job outcome; `recovery_action=none` | next turn or explicit audio operation | rehydrate each surface from snapshot + cursor | already exactly one |
| `error` | invariant code and last verified versions | narrowly scoped audited repair | fail loud; never skip corrupt rows or replay a whole turn | forbidden until inspected |

The `executing` state deliberately has a durable substage. Approval and provider execution start are different facts even though the canonical minimum state list names both under `executing`.

## Command admission order

Every handler follows this order inside the authoritative database transaction:

1. Look up `(room_id, command_id)`.
2. If found and the canonical request digest matches, return the stored result byte-for-byte. Do this before checking current aggregate version or stage.
3. If found and the digest differs, return `idempotency_conflict`; do not overwrite the first result.
4. Authenticate the room, surface, actor, and command capability.
5. Check `expected_aggregate_version` and draft/provider attempt versions.
6. Validate the transition and typed kernel command.
7. Atomically persist current state, the command result, an append-only audit/domain event, and any required outbox task.
8. Acknowledge receipt only after commit.

Rejected stale, invalid-stage, dynamic-authorization, and version-conflict results are stored too. A statically forbidden actor/command shape fails closed at schema admission and is transport-audited without entering the command-result namespace. A retry of a valid rejected command therefore cannot become accepted merely because state changed later.

## Required transitions

| From | Input | Guard | Atomic durable outcome | Rejection |
|---|---|---|---|---|
| `listening` | final transcript `receive` | new command/turn; authenticated table actor | state=`drafting`; received identity and result | `invalid_stage`, `wrong_aggregate` |
| `drafting` | `persist_draft(v1)` | final transcript exists | immutable draft v1; state=`awaiting_approval` | `invalid_stage` |
| `awaiting_approval` | `redraft(v+1)` | exact next draft version | immutable new version becomes current | `draft_version_conflict` |
| `awaiting_approval` | `approve(v)` | `v == current draft_version` | accepted version; state=`executing`; no world change | `stale_draft`, `invalid_stage` |
| `executing` | `start_execution` | approval persisted; no active attempt | stable `execution_attempt_id` before external work | `invalid_stage` |
| `executing` | trusted `commit_world` | same approved command/attempt; expected world revision | world mutation + typed result + state=`presenting` + projection task in one transaction | conflict/error; zero mutation |
| `presenting` | internal `prepare_projection` | committed revision; no ready event | allowlisted projection event, or safe projection error | fail closed; no browser payload |
| `presenting` | `ack_projection(event_id)` | reducer succeeded; ID equals pending event | cursor/ack; state=`committed`; audio enqueue task | `cursor_conflict`, `invalid_stage` |
| `committed` | internal `enqueue_audio(line_id)` | matching pending line | one durable audio job | duplicate returns stored result |

## Projection and cursor semantics

- Projection IDs derive from durable identity, for example `projection:{turn_id}:{world_revision}`; they never derive from payload text.
- Relay delivery is at-least-once. Replay and live delivery may contain the same `event_id`.
- A client reducer validates the exact allowlisted envelope, applies an unseen ID transactionally to its local view, then sends the ack. It does not advance the cursor before rendering/reduction succeeds.
- Server ack is monotonic per `(room_id, surface, consumer_id)` and names the exact `event_id` plus reducer/schema version.
- A new or restarted browser may discard all ephemeral state and request snapshot + events after its last durable cursor. The snapshot and events must carry one aggregate/world revision boundary.
- Admin projection contains stage, versions, safe technical errors, recovery controls, and audit identity. It does not inherit canonical world fields or receive hidden world secrets.
- Unknown projection fields/types yield `ProjectionFailed`; the committed world remains, the last safe table projection remains, no event is published, and the admin sees `repair_projection_schema` without the secret value.

## Provider and late-event semantics

- Persist `execution_attempt_id`, `provider_request_id`, and the intended uncommitted stage before external work.
- Provider events authorize no world mutation. They are observations bound to the current attempt.
- A late event for an old attempt is durably acknowledged as `late_provider_event` and ignored.
- Restart before world commit may retry only the named uncommitted attempt/typed command. Restart after world commit resumes projection/audio and must not call the kernel again.
- No design here requires a provider/browser/world distributed transaction.

## Audio semantics

- Projection acknowledgement makes the turn committed; audio is a degradable technical stage.
- An audio job uses stable `line_id`, `context_id`, `turn_id`, and disclosed `text_event_id`.
- Enqueue and delivery can retry. Provider and browser dedupe on the stable IDs; an explicit repeat may create a new playback attempt but not a new game command.
- Cancel closes provider generation and independently stops/discards browser buffers for the same `line_id/context_id`.
- Audio failures leave committed text/board visible and never move the turn back to `executing`.

## Measured recovery points

The synthetic harness observed these states identically for both candidates:

| Crash after | State on reload | Mutation count | Recovery action |
|---|---|---:|---|
| receive | `drafting` | 0 | `retry_draft` |
| draft persist | `awaiting_approval` | 0 | `wait_for_approval` |
| approval | `executing` | 0 | `start_execution` |
| execution start | `executing` | 0 | `retry_uncommitted_execution` |
| world commit | `presenting` | 1 | `resume_projection` |
| outbox publish | `presenting` | 1 | `publish_projection` |
| projection ack | `committed` | 1 | `enqueue_audio` |
| audio enqueue | `committed` | 1 | `none` |

Source: `probe-results.json`, 16/16 crash cases passed (eight per candidate).
