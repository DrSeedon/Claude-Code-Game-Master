<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

The plan is comprehensive and closely tracks the named authority, but three load-bearing sequencing/protocol defects remain. The required Sol review route was unavailable in this environment, so this is an evidence-backed direct review rather than an independent model verdict.

## Findings

- `blocking: docs/tasks/377/implementation/plan.md:210 —` I0’s immutable RED oracle specifies only rejection cases. A deny-all gate could satisfy those cases, while the delivery contract also requires accepting a fully closed, owner-authorized reuse row at line 212. Because the oracle cannot be expanded during the implementation attempt under lines 150–154, the positive authorization path lacks executable pre-implementation coverage. → Put both a fully closed owner-authorized positive row and the listed negative rows into the initial RED oracle; RED should fail because the positive row is not admitted while every incomplete row remains rejected.

- `blocking: docs/tasks/377/implementation/plan.md:144 —` “The designated table/composite acknowledges … That ack advances delivery” implies a shared delivery advancement, but accepted R7 requires an independent durable cursor for every `(room, surface, consumer_id, schema, reducer)` and separate acknowledgements after each successful render. A table acknowledgement must not advance scene/admin delivery or cause their failed projections to be skipped on reconnect. → Define per-consumer cursor advancement explicitly in the load-bearing repository/transport interfaces and AC. Keep audio-work eligibility separate from projection delivery advancement and require the current lease/fence checks independently.

- `blocking: docs/tasks/377/implementation/plan.md:392 —` The R10 freeze is required to contain participant-consent references and be signed “before recruitment/session data.” Individual participant consent references cannot exist before participants have been recruited, making the stated RED/admission sequence impossible without fabricated placeholders or premature collection. → Split the gate into a protocol freeze before recruitment—consent form/version, questions, criteria, retention rules and owners—and a participant admission check after recruitment but before any microphone/provider/session activity, containing each actual consent reference.

## Verdict

**Needs work.** The overall integrated sequence and scope are credible, but I0 can currently admit a deny-all provenance implementation, projection recovery can conflate independent consumer cursors, and the R10 consent gate is temporally impossible as written. These must be corrected before the plan is canonical.

## Round 1 disposition

- **I0 positive path — fixed:** the initial immutable oracle now contains one fully closed owner-authorized positive row and all named negative rows. Its observed RED is specifically the positive row not being admitted while negative rows remain rejected, so deny-all cannot pass.
- **Projection delivery — fixed:** `ProjectionDeliveryPort` and the transaction order now key and advance a durable cursor independently for every `(room_id, surface, consumer_id, schema_version, reducer_version)` after that consumer renders. Table acknowledgement cannot advance scene/admin. Audio-work eligibility is separate and rechecks the current lease and `audio_fence`.
- **R10 consent timing — fixed:** protocol content/version/criteria/retention/owners freeze before recruitment. Actual participant references are created after recruitment and must be admitted before microphone, provider, or session activity. The oracle rejects both fabricated pre-recruitment references and pre-admission room I/O.

Attempt 1 is consumed. The journal metadata identifies the reviewer as `gpt-5.6-sol`; the review prose's claim that the Sol route was unavailable conflicts with that metadata, so it is not used as route evidence. The concrete findings remain valid direct technical review evidence. No cross-family or otherwise independent verdict is claimed. The artifact changed after every finding, so one final resumed Sol round is permitted.

## Round (2026-08-16T21:29:31Z)

<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

All three prior blockers are fixed. No genuinely new blocking findings were found.

## Findings

- `FIXED: docs/tasks/377/implementation/plan.md:215 —` I0 now freezes both the fully closed positive row and all negative rows; RED specifically requires the positive row to remain unadmitted, so deny-all cannot pass.

- `FIXED: docs/tasks/377/implementation/plan.md:148-149 —` projection cursors now advance independently per consumer only after successful render. Table acknowledgement cannot advance scene/admin, and audio separately rechecks the playback lease and `audio_fence`.

- `FIXED: docs/tasks/377/implementation/plan.md:393-400 —` R10 now separates the pre-recruitment protocol freeze from post-recruitment participant admission, which must precede all microphone, provider, and session activity.

Review-completion evidence from the artifact:

> “First-party authorization does not waive contributor, dependency, asset, SRD, trademark, privacy, retention, or notice checks.”

## Verdict

**APPROVED.** Final prose round complete; no blocking findings remain.

## Canonical route outcome

- **Reviewed artifact and consumers:** `docs/tasks/377/implementation/plan.md`; future private-repository implementation owners for I0–I12 and R10, plus repository/IP, security/privacy, game-systems, content, provider/data/budget, VPS/release, and product-experiment decision owners.
- **Author runtime:** Orchestra Codex runtime; no exact versioned author-model identifier is exposed in this task's artifact/session metadata.
- **Named acceptance contract:** orchestrator Task #15, grounded in `mvp-product-spec.ru.md`, merged `research.md`, accepted Core and R4–R9 artifacts, and the plan's per-ticket RED/delivery/AC/rollback/boundary/stop fields.
- **Mechanical evidence:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project "$PWD" --frozen python docs/tasks/377/implementation/check_plan.py` → `PASS`, 14 tickets, acyclic DAG depth 11, critical spine `I0,I1,I2,I3,I4,I8,I9,I10,I11,I12,R10`; `git diff --check` → pass.
- **Risk and oracle independence:** high risk due repository/IP admission, transactional authority, security/privacy, provider boundaries, and human consent. The manifest checker was authored with the plan, so it is useful deterministic evidence but not an independent behavioral oracle.
- **Route:** direct Sol technical review, as required by the high-risk floor; Luna was not used as a substitute. Two prose rounds consumed, which is the ceiling. Round 1 returned three blockers; all were changed before the resumed Round 2, which marked each `FIXED` and returned `APPROVED` with no new blockers.
- **Independence:** reviewer metadata records `gpt-5.6-sol`. No cross-family reviewer and no independent acceptance-test author participated, so this is a completed technical review, not an independent or cross-family verdict.
