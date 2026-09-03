## Summary

The package is directionally strong: it selects behavioral rewrite, separates SRD/content routes, covers the named authority threats, and records substantial repository controls. However, four load-bearing contradictions prevent a fail-closed verdict. No files were edited.

## Findings

- `blocking:` `docs/tasks/377/phase3/r8/transfer-manifest.tsv:20` — `SRD-521-01` permits `CONDITIONAL_LITERAL_EXCERPT` while its hash, content inventory, destination, and reviewer approval are explicitly missing. This contradicts the package’s own rule that any `unknown` or incomplete field makes literal action `AVOID` (`ip-route.md:36-45`) and the ticket requirement that unproven actions be marked avoid. A consumer could treat `CONDITIONAL` as admission authority. → Set its current `allowed_action` to `AVOID` or `BEHAVIORAL_REWRITE` and status to `AVOID_LITERAL`. Define a separate executable transition to literal use only after all six checks in `ip-route.md:38-43` are populated and signed. Apply the same rule to every future conditional row.

- `blocking:` `docs/tasks/377/phase3/r8/remote-authority-threat-model.md:86` — the replay oracle proves only “one successful session/command and exactly one world revision” across the original request and replay. It can pass when the original fails and the replay succeeds, so it does not prove that the replay itself is rejected with observable zero mutation. It also conflicts with the global replay invariant at lines 19–27. → First complete and record the legitimate consumption, snapshot revision and command/outbox/mutation counts, then issue sequential and concurrent replays. Require every replay to be denied, all post-snapshot counts to remain unchanged, the stored original result to remain unchanged, and a replay-denial audit row to exist.

- `blocking:` `docs/tasks/377/phase3/r8/remote-authority-threat-model.md:29` — the document claims approval, audit, outbox/command record, and world revision are one atomic operation, but the concrete protocol persists approval/outbox and marks `executing` at line 71, then invokes the kernel and mutates later at lines 72–73. “Transactionally equivalent durable protocol” is not specified. Unique `command_id` alone does not close crashes between kernel mutation, result persistence, and outbox acknowledgement. → Choose an executable protocol: either commit command consumption, audit, world mutation, result, and outgoing event in one database transaction, or specify the durable state machine and recovery decisions for every boundary, including an authoritative mutation ledger/idempotency lookup. Require crash tests to assert both world revision and command/result/outbox state at each boundary. If R4 must choose this, explicitly mark this security guarantee blocked by R4 rather than claiming it is closed.

- `blocking:` `docs/tasks/377/phase3/r8/repo-security-baseline.md:19-25` — the stop-before-first-push gate requires evidence from a rejected policy rehearsal, test PR/CODEOWNERS delivery, and a successful first mirror, but an empty repository has no branch, PR, pushed commit, or mirrorable content. The gate is therefore not executable as written and can force either an undocumented bypass or permanent deadlock. → Split it into two gates: (1) before bootstrap push, verify ownership, visibility, access, host policies, ruleset configuration, scanners, and a rehearsal in a disposable private repository; (2) allow exactly one reviewed allowlisted bootstrap commit through a named, time-bounded bootstrap procedure, then require the real repository’s rejected direct-push/PR/CODEOWNERS rehearsal and successful off-provider mirror before any product-code push. Record and revoke the bootstrap authority.

- `suggestion:` `docs/tasks/377/plan.md:121` — the canonical ticket names flattened artifact paths such as `phase3/r8-ip-route.md`, but the actual files are under `phase3/r8/`. This makes the delivery contract mechanically false even though the package exists. → Correct the ticket paths or add an authoritative artifact index pointing to the actual four research files. Do not duplicate the artifacts.

- `suggestion:` `docs/tasks/377/phase3/r8/ip-route.md:22` — “public, uncopyrightable behavior” is broader than the cited US Copyright Office evidence supports, especially outside the United States. The later caveat helps, but the operative permission remains categorical. → Describe the route as independently implementing behavior-level requirements without copying protectable expression, subject to jurisdiction-specific qualified review; avoid declaring the behavior itself universally uncopyrightable.

## Verdict

**REJECT — needs work.**

Blocking findings: 4. The I0 route is conservative overall, but the SRD manifest transition is not fail-closed, the replay oracle can accept the wrong execution, the mutation protocol leaves an unresolved crash seam, and the first-push gate cannot currently be executed as written. The corrections above are documentation/research corrections only and require no repository, provider, or production action.

## Response to round 1

- Accepted the manifest finding: `SRD-521-01`, `SRD-51-01`, and future asset/voice rows now authorize only `AVOID`/`BEHAVIORAL_REWRITE` in their current rows. Admission requires a new complete `USE_AS_GRANTED` row with immutable evidence and dated qualified signatures.
- Accepted the replay finding: the oracle now completes and snapshots the legitimate use before sequential/concurrent replay, requires each replay denied, keeps every protected-state snapshot identical, and separately permits exactly one winner only in the simultaneous-original race.
- Accepted the crash-seam finding: the route now chooses a relational-database state machine with a no-mutation approval transaction and a single execution transaction containing command consumption, audit, mutation ledger, world revision, result, and outgoing event. Crash and recovery outcomes are stated for every boundary; storage that cannot supply that transaction blocks remote mutation.
- Accepted the bootstrap finding: repository establishment now has Gate A, one exact-hash 15-minute bootstrap authority, immediate revocation, and Gate B before any product-code push. Policy/secret negative rehearsals use a disposable private repository before bootstrap; real-branch, CODEOWNERS, and mirror evidence follow the bootstrap.
- Accepted both suggestions within owned scope: `ip-route.md` now has the authoritative nested artifact index because the parent plan is outside R8 ownership, and the rewrite permission is jurisdiction-qualified rather than declaring behavior universally uncopyrightable.

- Attempt 2: focused Sol follow-up completed; all four blocking findings were fixed, no new blocker was found, and the verdict is `APPROVED — no blocking findings`.

## Round (2026-08-16T13:04:29Z)

## Summary

All four former blockers are closed. The revised manifest is fail-closed, replay testing isolates replay mutation, the relational transaction boundary closes the crash seam, and the two-stage bootstrap removes the first-push deadlock. No new security blocker was introduced.

## Findings

- `suggestion:` `docs/tasks/377/phase3/r8/ip-route.md:7-15` — the index declares exactly five R8 artifacts, but `docs/tasks/377/phase3/r8/codex_sessions.json` is a sixth file containing review-session metadata. It is not a security blocker, but it violates the stated five-file package boundary. → Keep tool/session metadata outside the delivered R8 artifact directory.

Prior findings:

- **FIXED:** `transfer-manifest.tsv:20-24` — incomplete SRD, voice, and asset rows now authorize only `AVOID`/`BEHAVIORAL_REWRITE`; literal admission requires a separate completed and signed row.
- **FIXED:** `remote-authority-threat-model.md:88,113` — legitimate consumption is completed and snapshotted before replay; every replay must be denied with byte-identical protected state and a denial audit row.
- **FIXED:** `remote-authority-threat-model.md:29,71-75` — approval performs zero world mutation, while mutation ledger, world revision, result, audit, and outgoing event commit atomically in one execution transaction.
- **FIXED:** `repo-security-baseline.md:11-44` — Gate A, constrained bootstrap, immediate revocation, and Gate B provide an executable evidence sequence before product code.
- **FIXED:** `ip-route.md:34` — the behavioral-rewrite route is now jurisdiction-qualified.

## Verdict

**APPROVED — no blocking findings.**

Independent-read evidence, verbatim from `remote-authority-threat-model.md:29`:

> The kernel performs no external side effect inside or before that execution commit.
