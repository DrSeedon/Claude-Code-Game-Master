<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Attempt journal

- Attempt 1 completed 2026-08-16: reviewer response produced six findings and one blocking durability contradiction; round counted. Evidence valid: the quoted line was found verbatim at `research.md:28`.
- Attempt 2 started 2026-08-16 after artifact changes for the accepted blocker and adjacent deterministic seams: atomic candidate/event reference, separate normal-close terminal, purpose schema constraints, pending-roll revision check, expanded traces, and structured roll correction.
- Attempt 2 completed 2026-08-16: all six prior findings fixed, no new findings, `APPROVED`; round counted. Evidence valid: the quoted current line was found verbatim at `research.md:136`.

## Summary

The route decision is appropriately safety-first and makes no unmeasured latency claim. Provider documentation supports the stated `CloseStream` sequence and the qualified retention position. The synthetic tests pass:

`uv run ... pytest ... test_synthetic_probe.py` → `3 passed in 0.31s`

Proof of artifact review—exact line from `research.md`:

> **Result.** **CONFIRMED for correctness/security fit; UNCERTAIN for user-perceived performance.** The selected route is a contract decision, not a claim that the extra relay is faster.

## Findings

1. `blocking:` `docs/tasks/377/phase3/r5/speech-input-protocol.md:110` — The contract says durable metadata is “exactly `$defs.InputAttempt`,” but recovery at line 115 requires a complete persisted `speech.finalized`. `InputAttempt` only retains transcript/provider IDs (`protocol-schemas.json:411-421`), not transcript text, segment IDs, or an atomic reference to a separately persisted event. Consequently, the declared `ready` recovery cannot reconstruct or prove the exact R4 payload after a crash. Define the durable candidate/event record and atomic transition to `ready`, or explicitly reference a separately schema-validated durable event by identity.

2. `suggestion:` `docs/tasks/377/phase3/r5/synthetic_probe.py:263` — The probe treats receipt of `Metadata` as sufficient to create and submit the candidate, while the contract requires both terminal `Metadata` and a normal provider close (`speech-input-protocol.md:125`). Deepgram documents the sequence as final response → metadata → connection termination, so an abnormal close after metadata is a meaningful untested seam. Model the close event separately and freeze the candidate only after both conditions; add the metadata-then-abnormal-close trace. [Deepgram Close Stream](https://developers.deepgram.com/docs/close-stream)

3. `suggestion:` `docs/tasks/377/phase3/r5/protocol-schemas.json:134` — The closed schemas do not enforce the purpose-binding invariant. `CaptureAccepted`, `SpeechFinalized`, and `InputAttempt` all permit `purpose="declared_roll"` with `pending_roll_id=null`, or `purpose="action"` with a non-null roll. Add conditional schema constraints so malformed persisted/internal messages cannot represent an authority state the prose forbids.

4. `suggestion:` `docs/tasks/377/phase3/r5/synthetic_probe.py:146` — The synthetic pending-roll trace does not exercise the frozen pending-roll revision. `PendingRoll.expected_aggregate_version` is never copied or checked; the attempt instead stores the caller-supplied version, and approval checks only the roll ID. Thus the claimed stale-world/pending-roll binding is not falsified. Freeze the server-read revision and test that a revision change before approval rejects without committing.

5. `suggestion:` `docs/tasks/377/phase3/r5/probe-results.md:72` — The declared limitation is honest, but the probe omits several explicitly load-bearing deterministic seams that do not require a real browser/provider/database: ready-to-R4 restart replay, same-command admission idempotency, disallowed/cross-room actor rejection, conflicting final segments, cancellation, and metadata followed by abnormal close. Either add these traces or narrow the probe’s stated contract coverage so passing 16/16 cannot be mistaken for coverage of the release gates.

6. `question:` `docs/tasks/377/phase3/r5/speech-input-protocol.md:156` — The prose requires a “structured numeric correction control,” but the closed schema exposes only `draft.correct.replacement_text` (`protocol-schemas.json:275-293`). Is that control inherited from an existing R7/R8 schema? If not, specify its message and authority/version fields here; otherwise the physical-roll correction contract is incomplete.

## Verdict

Needs work. One blocking durability/restart contradiction should be resolved before this is decision-grade. The safety-first routing, symbolic latency budget, barge-in boundary, and provider-retention qualification are otherwise well supported.

## Round (2026-08-16T19:04:56Z)

<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Re-review status

`git diff` is empty because all seven package files are currently untracked; review used their current filesystem contents. Mechanical check: `3 passed in 0.12s`, with 26/26 probe checks.

1. `FIXED:` `speech-input-protocol.md:110-115`, `protocol-schemas.json:388-415` — `SpeechFinalized` and `InputAttempt.candidate_event_id` are now persisted atomically, and recovery validates duplicated identity/authority fields before idempotent R4 submission.

2. `FIXED:` `speech-input-input-protocol.md:125`, `synthetic_probe.py:314-336` — Metadata and normal close are separate conditions. The abnormal-close trace at `synthetic_probe.py:657-664` creates no candidate.

3. `FIXED:` `protocol-schemas.json:60-76` — shared `PurposeBinding` conditionally couples purpose and `pending_roll_id`; negative tests are at `test_synthetic_probe.py:49-57`.

4. `FIXED:` `synthetic_probe.py:161-177`, `synthetic_probe.py:487-495` — the server-read pending-roll revision is frozen and rechecked during approval. The stale-revision trace is at `synthetic_probe.py:634-655`.

5. `FIXED:` `synthetic_probe.py:584-701` — coverage now includes disallowed actors, admission replay, abnormal terminal close, conflicting finals, cancellation, and ready-state restart recovery. `probe-results.md:76-79` accurately limits this to an in-memory model rather than claiming real database/provider validation.

6. `FIXED:` `protocol-schemas.json:316-337`, `speech-input-protocol.md:146` — `roll.declared_correct` is a closed structured correction command bound to the current turn, draft version, and pending roll.

Artifact proof—exact current `research.md` line:

> - A per-capture provider connection pays connection setup. A warm stream could be faster; it is rejected only because the available terminal marker is weaker, not because it was measured slower.

## New findings

None. No new blocking contradiction was introduced by the changes.

## Verdict

APPROVED. All six prior findings are fixed, including the Round 1 blocking durability/restart issue.
