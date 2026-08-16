# Disposition of R1, R2, R3, and R7 evidence

`core-adr.md` is the only canonical conclusion for the unified track. This ledger prevents valid old evidence from disappearing while avoiding a patchwork of mutually authoritative documents. Old worktrees remain read-only.

## R1 — narrative director

Primary old evidence: the R1 package and `/tmp/r1-direct-review-final.txt`. “Closed” below means the integrated contract now states a falsifiable rule and, where named, the synthetic #11 probe tests it. It does not claim the real R9 campaign already satisfies the rule.

| Old finding | Disposition in Unified Core | Evidence / remaining gate |
|---|---|---|
| Route-only secret leak: discovery could reveal facts belonging to other routes. | **Accepted and closed in contract.** Reveal is an exact ledger entry for `(fact_id, route_id, audience, command_id, world_revision)`; a route may reveal only its own declared fact IDs. | ADR §8.1; schema `RevealRecord`; probe `unusual_plan_commits_once` verifies only the selected route's authored fact. R9 must lint the real graph. |
| Cross-reference validation covered only a subset of authoring references. | **Accepted and extended.** The definition linter covers facts, conclusions, carriers, NPC/location/object/event, goals, secrets, threats, thresholds, consequences, effect/templates, routes, opportunities and endings. Revealed subjects resolve or are exact registered sealed templates. | ADR §8.1; probe definition-lint assertions. R9 supplies the production definition/compiler. |
| Canary-only secrecy did not prove general non-interference. | **Accepted.** The contract requires reveal dominance for every presentation atom, positive projection schemas, a separate narrator allowlist, and fail-closed unknown fields. A canary remains a regression oracle, not the proof technique. | ADR §§6.3, 8.1, 11; Matrix M5/M6; probe safe projection and canary assertions. Formal information-flow proof is not claimed. |
| Alternate-route reachability was not demonstrated after NPC death/absence. | **Accepted and bounded.** Each mandatory fact has at least two independently eligible routes and at least one durable non-NPC route; the linter simulates every declared critical carrier becoming unavailable. | ADR §8.2; probes `definition_linter_requires_durable_alternate` and `npc_death_preserves_alternate_route`. R9 may falsify bounded coverage with compound destruction cases. |
| NPC state conflated absence and death. | **Accepted and closed.** `alive_present`, `alive_absent`, and `dead` are distinct; only present carriers satisfy present-only route requirements. | ADR §8.3; schema enum; probe `alive_absent_is_not_dead_or_present`. |
| Death, consequence scheduling and ending semantics were omitted. | **Accepted and integrated as contract.** Hero death saves, immutable campaign death history, server-derived idempotent consequence scheduling, and deterministic ending priority are kernel semantics. | ADR §§8.3–8.4, 9.2; probe covers death-save edge reduction, one-time scheduling under retry, NPC absence/death, and simultaneous/equal-priority endings. Due/firing transitions still require a future end-to-end oracle; exact content remains R9. |
| `action_id`/transition-local idempotency was weaker than R4. | **Superseded.** Every retryable command uses R4 `(room_id, command_id)` plus canonical digest; plan and transition IDs are references, not dedupe authorities. | ADR §5; Matrix M1/M6; R4 accepted ADR; duplicate/conflicting-ID probe. |
| Route eligibility could change after earlier operations in one plan. | **Accepted and closed.** All operations validate against one detached snapshot and cross-operation constraints before any reducer runs; the plan commits atomically. | ADR §§5–7; Matrix M1 order 6–7; multi-operation rollback/hash oracle. |
| Free-form prompt instructions left model authority ambiguous. | **Accepted and rejected as an architecture.** The adjudicator produces only a candidate typed plan; public prose is discarded, and only the deterministic kernel owns legality/mutation. | ADR §§2, 6; schema closed operations; unknown-operation zero-mutation probe. |
| “Once”, priority, and simultaneous semantics existed in prose without exercised state. | **Accepted with bounded evidence.** Scheduling identity is a server-derived stored cause key; consequence firing requires an explicit scheduled/fired state transition; endings have unique priority and equal-top authoring failure. Unused route priority is not part of the minimum contract. | ADR §8.4; Matrix M6; probe covers scheduling retry/forged-ID rejection and ending priority, but not due/firing execution. |
| R1 package lacked a completed independent approval and therefore could not become canonical alone. | **Accepted.** R1 is evidence only. #11 integrates the findings and is independently reviewed as one contract. | This ledger and `codex-review.md`. |

## R2 — typed world tools

Primary old evidence: the R2 package and `/tmp/r2-direct-review-final.txt`.

| Old finding | Disposition in Unified Core | Evidence / remaining gate |
|---|---|---|
| Approval did not bind the exact stored plan/draft/provider attempt strongly enough. | **Accepted and closed in contract.** Coordinator persists the running provider attempt before dispatch; `turn.prepare` must match it; the player-safe card exposes the stored plan digest; `turn.approve` supplies only stable command/turn/draft/nonce identity and loads that exact stored plan. | ADR §§4–6; schemas `BeginAdjudicationCommand`, `ApprovalCard`, `ApproveCommand`; provider begin/cancel/late-attempt and approval-card probe assertions. |
| R2 authorization-before-dedupe contradicted accepted R4 duplicate-first admission. | **Accepted; R4 wins.** Static transport capability runs outside the transaction; inside the R4 transaction dedupe+digest precedes current dynamic authorization/version/stage checks. Stored duplicate results are public-safe summaries. | ADR §5; Matrix M1 rows 1–4; probe `dedupe_precedes_dynamic_actor_checks`. |
| Result schema could represent contradictory committed/rejected combinations. | **Accepted and closed mechanically.** The JSON Schema conditionally requires `status=committed` with `code=ok` and committed versions, while rejection cannot use `ok` or committed versions. | `core-contract.schema.json#/$defs/CommandResult`; schema validation check. |
| Reveal payload did not require/reconcile its subject/reference. | **Accepted and replaced.** `reveal_fact_via_route` contains an existing fact and route; the definition linter verifies route membership, conclusion inclusion and subject/template closure before a definition can be pinned. | ADR §8.1; schema operation; definition-lint probe. |
| `resolution_ref` could be forged or absent while applying damage/results. | **Accepted and closed in invariant.** Damage/healing/condition effects require an exact unconsumed `resolution_effect_id`; op/target/amount/type must match the immutable authorized effect, not merely an existing resolution. | ADR §§7, 9.2–9.3; Matrix M2/M6; probe `roll_effect_is_exactly_bound_and_consumed_once` covers wrong target, wrong amount, failed roll and reuse. |
| Seven low-level primitives were assumed sufficient and safe for model/client use. | **Rejected.** They are neither the public command API nor a complete algebra. M2 keeps/narrows two, binds damage, replaces four broad forms, and adds domain semantics. | ADR §7; Matrix M2; schema closed union. R9 can add only named/versioned operations. |
| R2 lacked a completed independent approval. | **Accepted.** R2 is evidence only; the reviewed #11 package supersedes it as conclusion. | `codex-review.md`. |

## R3 — tactical engine and SRD scope

R3 had no separately accepted standalone conclusion to preserve. Treating it as a missing patch would recreate three authorities. Unified Core directly fixes the tactical contract:

- one pinned `srd-5.2.1-mvp-1` rules bundle, not full D&D and not a 5.1/5.2.1 mix;
- six explicit level-3 coverage profiles;
- server-authoritative grid, LOS/range/resources, rolls, HP/death/conditions/effects;
- side phases and classic initiative as two schedulers over the same state/commands;
- deterministic standard resolver and the same kernel validator for AI candidate plans.

This is **research closure**, not proof of rules completeness or balance. R9 must enumerate the actual prepared heroes, encounters and unusual beats against Matrix M2/M4. R10 owns play quality, side-phase balance and fallback decision evidence.

## R7 — three surfaces

Primary old evidence: commit `2bd6a1f` under the read-only R7 worktree.

| R7 evidence | Disposition in Unified Core | Correction / remaining gate |
|---|---|---|
| Full snapshot families with stable version IDs and post-render cursor acknowledgement. | **Retained as evidence and integrated.** All three projections are derived from one committed aggregate version; mandatory cross-field validation rejects mixed nested versions; cursor moves only after render success. | ADR §11; Matrix M1/M5/M6; synthetic mixed-family/reconnect/render probes. A real browser/WebSocket test remains future implementation evidence. |
| Table/scene/admin schemas are distinct. | **Retained and narrowed.** Positive allowlists remain, but admin is operational-only and does not inherit world secrets. Narrator is a fourth server-internal allowlist. | ADR §§6.3, 11; Matrix M5. |
| `DraftApprove` omitted `command_id`. | **Corrected.** Every retryable approval includes stable `command_id`; it also binds `turn_id`, `draft_version`, and a single-use nonce while authority/plan stay server-owned. | ADR §5; `ApproveCommand` schema. |
| “Revealed state” was a generic source for surface projection. | **Narrowed.** Only route-specific reveal ledger entries and independently visible public state may feed table/scene/narrator. | ADR §§8.1, 11; Matrix M5. |
| Synthetic clients demonstrated reconnect and fail-closed behavior. | **Evidence, not UI acceptance.** The result constrains later implementation but does not prove Pointer Events, fullscreen, browser storage, real broker order, latency or three physical screens. | ADR §17 counter-evidence; R7 remains a prerequisite for future implementation, not an independently accepted conclusion. |
| Planning overlays are collaborative but not world state. | **Retained.** Overlay IDs/TTL/reconnect rules live on an ephemeral channel and never increment `world_revision` or enter narrative truth. | Matrix M5; real reconnect/expiry browser oracle remains later implementation work. |

## Final authority statement

R1, R2 and R7 remain cited primary research evidence. They are not independently composable runtime contracts. R3 is answered only inside Unified Core. When any statement conflicts, the precedence is: canonical owner product decisions → accepted R4/R8 boundaries → `core-adr.md` → detail matrices/schema → old evidence.
