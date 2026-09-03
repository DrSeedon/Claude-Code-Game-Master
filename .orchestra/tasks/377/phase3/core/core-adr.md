# ADR #11 — unified authored-story and tactical room core

- **Status:** Phase 1 research decision; proposed canonical core contract, pending the Phase 2 gate
- **Date checked:** 2026-08-16 (Europe/Berlin)
- **Decision owner:** core architecture/reliability lead; product constraints remain owner-owned
- **Scope:** one remote-authoritative MVP room turn; research schemas and a synthetic probe only
- **Not in scope:** private repository creation, product implementation, deployment, production, real model/STT/TTS calls, R5/R6/R9 content work, or R10 playtesting
- **Supersedes as a core conclusion:** the separate R1 narrative, R2 typed-tools, and unstarted R3 rules conclusions. Their evidence is retained and disposed in `old-finding-disposition.md`; they are not patched into three authorities.
- **Accepted inputs:** the canonical product spec, R4 transactional state/deduplication/outbox, and the R8 remote-authority boundary. R7 is evidence and is narrowed here into the projection contract; it is not treated as an implemented UI.

## 1. Question and strong-inference frame

### Context

The MVP needs one authored but variable story, deterministic tactical play, AI adjudication of unusual actions, physical player dice, public enemy dice, reversible side-phase combat, three safe browser projections, and crash-safe approval. R4 already selected a single remote SQLite authority where world mutation, coordinator/result, audit/domain rows, and the projection task commit together (`docs/tasks/377/phase3/r4/coordinator-adr.md:7-11,114-140`; `state-machine.md:5-11`). Old R1 and R2 modeled narrative and tools independently and were found to have unresolved reveal, reference, idempotency, authorization, and result-schema defects (`/tmp/r1-direct-review-final.txt:1-15`; `/tmp/r2-direct-review-final.txt:1-13`).

### Change under test

Replace separate narrative/rules/tool state with one versioned **RoomRunAggregate**. It pins two immutable inputs—an authored **CampaignDefinition** and a curated **RulesetBundle**—and atomically evolves coordinator, narrative, tactical, roll, and presentation-intent state through one closed **ResolutionPlan** and one game kernel. Table/scene/admin are positive projections of the resulting committed snapshot, never authorities.

### Baseline

The rejected baseline is a narrative director that mutates story state, a tactical engine that mutates combat state, and an AI tool dispatcher that mutates a generic world graph, coordinated after the fact by IDs or events. That shape has at least two commit points and cannot inherit R4's measured one-mutation recovery guarantee.

### Measurable outcome

The contract succeeds if a synthetic authored turn can, with no external provider:

1. prepare and approve an exact unusual plan without mutation;
2. atomically change terrain, reveal only the committed route's facts, advance a threat, and schedule one consequence;
3. survive crashes before and after commit without duplicating any effect;
4. enforce grid/LOS/resources, a pending physical roll, a public persisted enemy roll, side phases, and the classic fallback;
5. produce same-version table/scene/admin projections with no secret canary;
6. reject duplicates, conflicting IDs, stale versions, wrong surfaces, unknown operations, and unsafe projections with zero extra mutation.

`research_core_probe.py` met all 48 final contract assertions; `probe-results.json` records the exact result. This is tier-1 evidence for the synthetic model only, not production readiness.

### Hypotheses and falsifiers

| Hypothesis | Falsifier sought | Result |
|---|---|---|
| **H1 — one aggregate is the smallest coherent authority.** Immutable definition/rules inputs plus mutable narrative+tactical state can share one R4 world transaction. | A required turn effect cannot be validated/applied without independently committing narrative or tactical state, or projection needs a second canonical state. | **SUPPORTED.** The integrated probe applied story, terrain, consequence, roll, phase, and presentation intent in one aggregate and recovered correctly. |
| **H2 — separate narrative and tactical aggregates are safer modularity.** A saga can coordinate them without weakening R4. | A crash can observe story revealed but terrain/damage absent (or the reverse), or retry needs semantic reconciliation. | **REFUTED for this MVP.** R4's guarantee explicitly applies only when coordinator and world share one transaction (`state-machine.md:7-11`); splitting the same turn recreates the excluded gap. Modules remain pure decision functions inside one transaction, not separate authorities. |
| **H3 — the original seven world primitives are a complete public command API.** The model/client can submit them safely. | Authored/tactical needs require resource, healing, condition, roll, phase, clock, NPC lifecycle, or consequence semantics, or low-level `damage/reveal/remove` bypass rules. | **REFUTED.** The seven are neither sufficient nor safe as public commands. Some survive as internal effect operations; others are narrowed/replaced and the algebra is extended (Table M2). |
| **H4 — AI can be the transition authority if output is typed.** A schema alone makes an AI decision authoritative. | A schema-valid but illegal move, forged damage resolution, unrevealed fact, impossible resource use, or contradictory story transition is possible. | **REFUTED.** The model is only a candidate-plan producer. The deterministic kernel owns admission, rules, references, reveal eligibility, and mutation. |
| **H5 — one filtered canonical payload can safely feed all browsers and narration.** | Any secret/unknown field reaches scene/admin/narrator bytes or a denylist misses a new field. | **REFUTED.** R4 and R7 canary results require positive projections and fail-closed publication (`r4/coordinator-adr.md:90-102`; R7 `surface-contract.md:41-68`). The integrated probe also rejects injected secret projection bytes. |

## 2. Decision

Adopt one **remote-authoritative, transactional RoomRunAggregate** per active room run.

The aggregate is the only mutable game authority. It includes the current coordinator turn, narrative run state, tactical encounter state, player/enemy roll records, and structured public presentation intent. It references, but never modifies:

- a content-addressed **CampaignDefinition**: immutable facts, NPCs, routes, clue topology, threats, consequences, maps/templates, and endings;
- a content-addressed **RulesetBundle**: `srd-5.2.1-mvp-1`, curated starter-hero features, deterministic resolver tables, and an engine version.

The browser, model provider, narrator, projection worker, broker, and audio layer never hold an independently writable copy of canonical world state. Narrative and tactical logic are separately testable pure modules, but they accept one snapshot and produce one candidate plan for the same kernel transaction.

### 2.1 Why the boundary is an aggregate, not “everything in one object”

The decision is about **one compare-and-swap/transaction boundary**, not one source file or god class. Internally, the code can have `NarrativePolicy`, `TacticalResolver`, `AdjudicationValidator`, `EndingEvaluator`, and `Projector` modules. None may commit state. Only `RoomRunRepository.commit(expected_aggregate_version, validated_plan)` may persist a game transition.

The durable physical representation follows accepted R4: current aggregate row(s), `(room_id, command_id)` stored results, append-only audit/domain rows, and transactional outbox. Audit events are useful evidence but are not canonical replay prerequisites (`r4/coordinator-adr.md:116-146`).

## 3. Canonical inputs and version boundaries

| Boundary | Immutable identity | Mutability rule | What a mismatch means |
|---|---|---|---|
| Campaign definition | `campaign_definition_id + definition_hash + schema_version` | Never edited for a running room. A revision is a new hash and starts only a new run/migration rehearsal. | Stop before play or require an explicit tested migration; never silently load “latest.” |
| Ruleset bundle | `ruleset_id=srd-5.2.1-mvp-1 + rules_engine_version + bundle_hash` | Fixed for an encounter/run. Difficulty changes declared inputs, not past dice. | Reject/resume only with the pinned bundle; no mixed 5.1/5.2.1 semantics. |
| Room aggregate | `room_id + aggregate_version` | Every accepted coordinator/domain transition increments `aggregate_version`; CAS is mandatory. | `version_conflict`, stored as a durable rejection for a new command ID. |
| World state | `world_revision` within aggregate | Increments only when narrative/tactical/roll/public-presentation game state changes. Approval, projection ack, diagnostics, and volume do not increment it. | Distinguishes game mutation from workflow/control progress. |
| Turn draft/plan | `turn_id + draft_version + plan_id + plan_digest` | A draft version and its private plan are immutable. Redraft creates the next version. | Stale approval is rejected; a plan may not be edited under an approved version. |
| External/provider work | `execution_attempt_id/provider_attempt_id` | The coordinator persists a `running` attempt before dispatch. A candidate is admitted only for that exact current attempt; cancel/replace closes the old identity. | Drop/audit late output; never reopen execution. |
| Roll | `roll_id + resolution_id + resolution_effect_id` | Pending request is immutable; one confirmed record authorizes exact typed effects and each effect is consumed once. Enemy faces/result are stored in the commit that uses them. | Duplicate returns stored result; changed face or changed target/amount/type conflicts or fails exact effect binding. |
| Projection family | `projection_batch_id + aggregate_version + world_revision` | Full allowlisted table/scene/admin snapshots from one committed read boundary; a mandatory cross-field validator proves every nested projection carries the outer versions. | Mixed versions never render; last safe family remains. |

There are not separate `story_version` and `tactical_version` authorities. Optional component hashes may help caches/tests, but admission uses the aggregate version. This prevents a command from validating against story v8 and tactics v9.

## 4. Aggregate contract

`core-contract.schema.json#/$defs/RoomAggregate` is the machine-readable research shape. Cross-field rules below are normative even where JSON Schema cannot express them.

### 4.1 Coordinator state

The R4 lifecycle remains authoritative:

```text
listening → drafting → awaiting_approval → executing
          ↘ redraft                    ↘ awaiting_roll (when required)
executing/awaiting_roll → presenting → committed → listening
                                    ↘ error with explicit recovery_action
```

The canonical product's single action card collapses transcript normalization and adjudication into one reviewed artifact:

- ordinary voice action: deterministic parser/resolver prepares the card;
- unusual voice action: private adjudicator proposes a typed plan during `drafting`;
- table click/touch action: the high-level intent is itself an explicit commit gesture; the server prepares a deterministic plan without an LLM;
- no world mutation occurs before the exact card/plan is approved or explicitly committed by the table gesture.

An unusual action does **not** require two player approvals. The card shows the canonical intent, declared cost/check/stakes, and visible proposed effect. Its nonce and displayed `plan_digest` resolve server-side to the complete immutable plan; the card contains neither private operations nor hidden facts. Hidden authored facts may influence validation, but arbitrary concealed AI mutations are forbidden.

### 4.2 Narrative run state

Canonical mutable narrative state contains only IDs and state transitions, not mutable truth text:

- exact reveal ledger `fact_id → {route_id, audience, command_id/world_revision}`;
- engaged/consumed routes and opportunities;
- NPC lifecycle/presence: `alive_present`, `alive_absent`, or `dead` (not a truthy present flag);
- threat/clock values and fired threshold/consequence instance IDs;
- immutable-choice/branch IDs where the party committed a branch;
- one terminal ending ID or none.

Fact `truth` and `public_fact` stay in the pinned definition. A later discovery adds a reveal record; it does not rewrite truth. A retcon requires a new definition/version outside a running room.

### 4.3 Tactical run state

Canonical tactical state contains:

- board/map ID, dimensions, cell/edge geometry, walls, terrain, light/reveal state, and effect instances;
- entity/token position, footprint, HP/temp HP, AC, speed, lifecycle, conditions, and visibility reference;
- action/bonus/reaction/movement resources plus curated class/spell uses;
- encounter mode, round, side/initiative cursor, acted set, and eligible combatants;
- pending physical-roll requests and immutable confirmed/public roll records;
- resolution records to which damage/healing/conditions must refer.

The server computes path, range, LOS, cover, occupancy, resource cost, targets, save/attack outcome, and effect duration. A model/client may name desired actor/target/destination only through a closed intent. It may not submit a path, result amount, resource balance, or visibility patch as authority.

### 4.4 Presentation intent

The aggregate stores only structured **public atoms** and stable public references generated by the kernel transition: visible result, speaker/entity reference, public roll, scene cue, and music/SFX event kind. It never stores generated narration as world truth. Narration/TTS is downstream delivery: replaying it cannot mutate the aggregate.

## 5. Exact admission, deduplication, authorization, and approval order

This resolves the old R2/R4 contradiction. There are two boundaries:

### 5.1 Transport/static admission (outside the command-result transaction)

1. Enforce request size/rate limits, TLS/Origin/CSRF or single-use WS ticket, and a valid server session.
2. Bind `room_id`, surface, actor allowlist, consumer identity, and coarse capability namespace from server session/socket context; ignore no authority-looking field—unknown fields reject.
3. Select the closed schema allowed for that surface. Scene has no game-command/approval schema; admin has operational commands only.
4. Parse/canonicalize the bounded envelope and compute the request digest. Static failures are redacted transport audits and do not enter the command-result namespace.

This is not a second game authorization. It establishes the server-owned namespace in which R4 admission runs.

### 5.2 R4 command transaction (exact order)

1. Look up `(room_id, command_id)`.
2. If the stored digest is exact, return the stored **player-safe** result byte-equivalently; do not recheck current version/stage/capability and do not dispatch.
3. If the same ID has another digest, return `command_id_conflict`; zero mutation.
4. For a new ID, apply dynamic authorization: current run state, surface capability, selected actor, actor ownership, and command kind.
5. Check expected aggregate version and, where applicable, draft version, plan digest, execution/provider attempt, pending roll, and combat cursor.
6. Check lifecycle transition and nonce. `turn.approve` contains a fresh `command_id`, `turn_id`, `draft_version`, and single-use nonce; it contains no plan, target, operation, actor, role, or room authority.
7. Revalidate the complete plan against the current pinned definition/rules and detached aggregate copy. Any failed operation rejects the whole plan with zero mutation.
8. Atomically persist next aggregate/result/audit+domain rows/outbox task, or a durable rejection result.
9. Return/ack only after commit. Projection cursor is separate and advances only after schema+reducer+render success.

R7's research `DraftApprove` schema omitted `command_id`; this integrated contract adds it because R4 requires every retryable client command to have stable identity. That is a disposition of evidence, not an edit to the R7 worktree.

The duplicate-first order can return an old result after actor selection/capability changes. Therefore stored external results are deliberately safe summaries—never private plan, secret fact, raw model output, or admin-only detail. A different surface cannot reach the schema/namespace at transport admission.

## 6. Standard actions and unusual adjudication share one kernel

### 6.1 Standard deterministic action

```text
table intent (pointer/confirmed voice)
  → deterministic resolver reads pinned rules + aggregate
  → ResolutionPlan(kind=standard)
  → kernel validates all operations against detached state
  → one R4 world commit
  → safe projection family
```

Standard actions include move, attack, curated ability/spell/item, target selection, damage/heal, condition changes, end phase, and physical-roll confirmation. No model call is on this path. A Pointer Event produces only a high-level intent; the server is authoritative for the snapped cell and legality, consistent with R7's evidence (`wireflows.md:40-52`).

### 6.2 Unusual AI-adjudicated action

```text
final transcript/button invocation
  → coordinator commits provider_attempt_id=running
  → private adjudicator gets bounded current context + permitted operation schema
  → candidate ResolutionPlan(kind=unusual, matching provider_attempt_id)
  → deterministic validator rejects/normalizes no fields; it either accepts exact data or asks redraft
  → player-safe card derived from plan and approved once
  → execution attempt persisted
  → kernel revalidates exact plan digest/current state and atomically commits
```

The adjudicator has no DB, filesystem, shell, SQL, network, projection, audio, or generic patch capability. It cannot introduce rules text, fact truth, templates, arbitrary entity components, or numeric damage without a validated resolution/check reference. An unusual action that needs a new semantic operation stops at an explicit unsupported-action result; it does not fall back to JSON Patch.

### 6.3 Private adjudicator versus public narrator

The private adjudicator may receive the minimum relevant secret facts needed to judge an action. Its public prose is discarded/not trusted. After commit, the projector builds a **PresentationBundle** from exact revealed facts, visible sensory results, public rolls, and safe atoms. A separate narrator receives only that bundle. Thus the model responsible for fluent player-facing text cannot accidentally echo unrevealed truth it never received. TTS accepts only persisted narrator output bound to the safe presentation ID.

## 7. Typed operation algebra

The original seven names are not the network API. They are disposed as internal effects in Table M2 (`contract-matrices.md`):

- retain/narrow `move` and `create_effect`;
- bind `damage` to an immutable validated resolution;
- replace generic terrain/spawn/remove/reveal with definition-scoped semantic operations;
- extend with healing, conditions, resources, roll request, NPC lifecycle, threat/consequence, and combat-mode/phase operations.

Every operation has closed arguments, a deterministic precondition, one reducer, named domain events, a projection rule, and zero-mutation rejection. `core-contract.schema.json#/$defs/Operation` is the minimum algebra for the researched slice. R9 may falsify completeness with authored content; the only permitted response is another named operation plus oracle and schema version.

## 8. Authored truth, branching, NPCs, death, and endings

### 8.1 Immutable truth and route-specific reveal

Each authored fact has private `truth` and a separately authored `public_fact`. A route explicitly lists `reveal_fact_ids`; a successful transition writes those exact IDs with that route ID. “Clue discovered” is not a blanket boolean from which every alternate route's facts are inferred. This fixes the route-only leak measured against R1 (`/tmp/r1-direct-review-final.txt:1`).

The authoring linter must close every reference before a definition can start:

- fact, conclusion, carrier, NPC/location/object/event, goal, secret, threat, threshold, consequence, effect/template, route, opportunity, and ending references;
- exact subject kind and lifecycle/status enum;
- every route includes its own conclusion in `reveal_fact_ids`;
- every public presentation atom is dominated by a public fact or a reveal in the same/earlier transition;
- sealed future subjects may be unresolved only when a registered definition template reserves the exact ID/kind; every revealed subject resolves.

### 8.2 Alternate clue reachability

For every mandatory fact, the minimum authoring rule is two independently eligible routes, at least one with a durable non-NPC carrier. The linter simulates declared critical-carrier loss (`dead`/`alive_absent`/location unavailable) and requires a remaining route. Runtime recomputes eligibility before any mutation. This is a bounded, falsifiable guarantee—not a claim to solve reachability for arbitrary player destruction.

### 8.3 NPC and hero lifecycle

- `alive_present`: can speak/act and carry a route;
- `alive_absent`: alive but cannot satisfy present-carrier requirements;
- `dead`: terminal NPC status unless an authored resurrection transition exists;
- enemies/NPCs reach `defeated/dead` according to their template; generic `despawn_entity` is never death;
- a hero at 0 HP becomes downed/unconscious and opens death saves; third failure means dead, third success means stable, and healing resets as defined by the curated SRD rule;
- hero death remains canonical campaign history; generic remove cannot erase it.

### 8.4 Consequences and endings

Every threshold/transition consequence has a stable `consequence_instance_id` derived server-side from definition element + causal command/transition. Neither model nor client may supply the instance identity. The ledger makes it effects-once.

Endings are predicates over canonical state with `terminal_class` and unique authored priority. After every world commit, the kernel evaluates all endings:

- no match → continue;
- one highest priority → commit it terminally;
- simultaneous unequal priorities → highest wins and the complete matched set remains audit evidence;
- equal highest priority → authoring error, definition cannot ship unless represented as one explicit `mixed` ending.

The synthetic probe exercises success/loss simultaneity, equal-priority rejection, `alive_absent`, route loss, and one consequence. This closes evidence missing from R1 (`/tmp/r1-direct-review-final.txt:7-15`).

## 9. Tactical rules and dice

### 9.1 Grid, LOS, and resources

The square-grid baseline follows official SRD 5.2.1: a square represents 5 feet; movement spends squares, difficult terrain costs two, walls block diagonal corner crossing, and range counts the shortest route ([official SRD 5.2.1 PDF, p.13](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), checked 2026-08-16). The engine uses integer cells and definition-authored blocking edges/cell properties. It must separately implement and test:

- footprint/occupancy and no illegal overlap;
- path cost and speed budget;
- LOS/visibility and cover from cell/edge geometry;
- range/area templates and target eligibility;
- action, bonus action, reaction, movement, slots, class uses, duration, concentration, and condition timing.

The MVP uses only the subset required by six curated heroes and the authored slice; it is not a full SRD engine.

### 9.2 Physical player rolls

The kernel first persists `PendingRoll{roll_id, actor, die, modifier, reason, target/DC/AC, resolution context}` and projects it. Room speech supplies only the raw face/result draft. Confirmation is a new idempotent command; the server adds the stored modifier and consumes the pending request once. A number without a matching pending request cannot become a roll. Damage/healing/condition operations must reference the resulting immutable `resolution_id`.

Death saves are also pending physical d20 rolls. SRD 5.2.1 specifies success on 10+, third success stable, third failure dead, natural 1 two failures, and natural 20 restores 1 HP ([official PDF, pp.17–18](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), checked 2026-08-16).

### 9.3 Enemy/world rolls

The server generates enemy/world dice with an injected RNG interface. The faces, modifier, total, reason, target, and resulting resolution are persisted in the same transaction that consumes the roll and then projected publicly. Nothing is published before commit, so a crash before commit may redraw without contradicting visible history; a crash after commit returns the stored roll/result and never rerolls. Difficulty may change authored stats/DCs before the roll, never its stored face.

### 9.4 Side phases and classic fallback

`combat.mode` is selected at encounter creation and locked once any combatant acts:

- `side_phases`: player phase admits any eligible unacted hero in player-chosen internal order; one action set per hero. `end_players_phase` closes planning, then world tactics generates enemy intents/rolls. Round reset restores resources according to rules.
- `classic_initiative`: the same entities/resources/commands use a persisted initiative order and cursor; only the cursor actor is admitted, and completing the actor advances or wraps the cursor and refreshes the next round. Official SRD uses individual Dexterity-check initiative ([official PDF, p.13](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), checked 2026-08-16).

No state migration is needed to fall back: only the combat scheduler differs. Per the owner decision, first-side/tie/balance choices are experiment-owned, not owner questions. The side-phase experiment measures alpha strike, phase duration, participation, and initiative-feature value in R10.

## 10. Six level-3 starters and the minimum SRD 5.2.1 subset

The core ships six **mechanical profiles**, while R9 owns names, personality, campaign equipment, and prose:

| Profile | SRD class/subclass baseline | MVP role | Mechanics that force kernel coverage |
|---|---|---|---|
| guardian | Fighter 3 / Champion | defender | weapon attack, AC, Second Wind/healing, Action Surge/resource, weapon mastery, crit rule |
| fury | Barbarian 3 / Berserker | striker | Rage duration/use, resistance, Reckless Attack advantage, Frenzy extra damage |
| shadow | Rogue 3 / Thief | scout | Expertise, Sneak Attack once/turn, Cunning Action bonus action, Steady Aim, Hide |
| beacon | Cleric 3 / Life Domain | healer | spell slots/DC, healing, Bless concentration, Preserve Life, save effects |
| arcanist | Wizard 3 / Evoker | controller | spell attack/save, area template, damage type, concentration, terrain/effect spell |
| voice | Bard 3 / Lore | support/social | Bardic Inspiration die/resource, skill checks, healing/control, reaction/condition interaction |

Official SRD 5.2.1 contains these six classes and their listed SRD subclasses (contents, pp.29–80); characters up to level 4 use proficiency bonus +2 ([official PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), lines/pages surfaced in the checked source). The destination must include the exact official attribution statement from SRD 5.2.1 p.1. It may say “5E compatible” but does not assume D&D/Forgotten Realms branding.

The minimum rules closure is enumerated in Table M4. Anything outside it is `unsupported_in_mvp` until an authored hero/encounter test adds a named mechanic. SRD 5.1 is not mixed into this bundle.

## 11. Projection and narration boundaries

One committed snapshot produces a **ProjectionFamily**:

1. projection worker loads exact aggregate+definition/rules hashes at the committed version;
2. it constructs table and scene only from visibility/reveal-ledger/public-roll/public-atom inputs;
3. it constructs admin independently from coordinator/outbox/health records, never by filtering the aggregate;
4. it validates all three closed schemas and scans secret canaries;
5. it runs a cross-field family validator that requires every nested aggregate/world version to equal the outer batch versions; Draft 2020-12 shape validation alone cannot express this equality;
6. it persists one batch with three stable surface events; table/scene publish together or neither;
7. a safe admin degradation event may separately report a projection error code/version, never the rejected field/value;
8. the designated table/composite ACK after successful schema+reducer+visible render completes presentation; scene/admin catch up independently.

### Table

Public board/cells/tokens, legal-action hints, HP/status/resources appropriate to players, combat phase/order/acted set, pending physical roll, public roll ledger, action card/nonce, public events, and temporary overlays. It never receives full definition, secret fact IDs/text, private plan, model prompt/output, raw transcript history, or admin recovery detail.

### Scene

Public scene/asset/speaker references, subtitle/narration, result/roll, and activity state. It has no input authority except optional separately commissioned audio candidacy. No draft/approve/actor/tool/admin schema exists.

### Admin

Start/pause/end, diagnostics, volume, cancel generation/audio, reproject last safe, and retry exact unfinished stage. Browser bytes contain only run/coordinator versions/stage/recovery action, health enums/age buckets, safe error code/correlation, and operation result. Admin receives no map, NPC/story truth, plan, narration source, raw provider error, transcript, or creative override.

### Narration

Narrator input is a fourth server-internal allowlist, not the admin/table schema: safe public atoms, revealed `public_fact` text, public sensory state, and public roll/results. The generated line is persisted with `presentation_id/line_id/context_id` before TTS. Reprojection or audio retry never calls the kernel.

This retains R7's measured full-projection/stable-ID/post-render-ack behavior, but records three corrections: R7 is synthetic evidence, approval needs `command_id`, and projection generation is constrained by the integrated reveal ledger rather than a generic “revealed state.”

## 12. Recovery and adversarial oracles

Table M5 is normative. The load-bearing invariants are:

- exact duplicate → byte-equivalent stored safe result, even after stage/version advances;
- same ID/different digest → conflict, zero mutation;
- new unauthorized/stale/invalid command → durable rejection, zero mutation;
- provider attempt identity/status persists before dispatch; candidate, cancellation and late output must match that exact current attempt;
- approval card and nonce bind to the stored immutable plan digest before execution;
- all plan operations validate on a detached snapshot before any write;
- world+result+versions+events+projection task commit together;
- crash before commit → no world effect and one explicit recovery stage;
- crash after commit → stored result/world/roll and projection-only recovery;
- projection failure → no unsafe player bytes, last safe UI retained, world not replayed;
- reducer/render failure → cursor unchanged;
- reconnect → latest safe full snapshot, then bounded stable-ID replay if unambiguous;
- late provider/audio events → dropped/audited without kernel call;
- every table/scene/admin/narrator serialization must exclude all secret canaries, not only one hard-coded fixture.

## 13. Evidence from the synthetic integration probe

Command (run from this isolated worktree with the mandated environment clearing):

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT \
  uv run --project "$PWD" --frozen \
  python docs/tasks/377/phase3/core/research_core_probe.py
```

The probe's fake adjudicator output enters only through a coordinator-authorized `turn.prepare`; a table-originated candidate plan is rejected. Candidate plans contain typed operations and binding IDs/hashes, not public prose. Public atoms are rebuilt after the kernel transition from safe domain events and authored `public_fact` values.

Observed on 2026-08-16:

- `oracle=PASS`, `48/48` assertions;
- final `aggregate_version=12`, `world_revision=5`;
- 17 stored command results, 12 domain records, 12 projection outbox tasks, 4 projection batches, 3 cursors;
- final state SHA-256 `b2d46b938418331b9d4b1249a91be949f6dd0bee1b3e3ed58720599333ef2c6d`;
- focused pytest: `2 passed in 1.51s`, including Draft 2020-12 validation of final aggregate, stored command results, and all projection families.
- repository regression: `544 passed in 14.94s` under the same isolated `--frozen` environment.

Covered synthetically: definition/cross-reference/alternate-route lint; six level-3 profile records (not their class mechanics); deterministic standard movement through the typed kernel; exact/conflicting duplicate and durable invalid-command results; provider begin/cancel/late-attempt binding; approval-card/digest binding; wrong surface/stale version/nonce; exact one-time roll-effect binding including wrong target/amount/failed roll; rollback at all four simulated transactional write boundaries and stored-result recovery after commit; one unusual multi-domain commit; server-derived consequence identity; public enemy roll; pending/confirmed physical roll; death-save edge reducer; NPC death/absence; simultaneous endings; legal/illegal cursor movement in side/classic schedulers; same-version projection validation; latest-snapshot reconnect; fail-closed canaries; and render-gated cursor.

Not covered: real concurrent writers, disk-full/SIGKILL/backup restore, production auth/HTTP/WS, actual browser reconnect/render, stale audio events, production provider adapters, end-to-end death-save roll/duplicate flow, six starter class mechanics, every transaction/storage failure mode, dense-map performance, exhaustive pathfinding/LOS/spells, model quality, speech/audio, real authored campaign, or physical play. These remain stop conditions, not inferred successes.

## 14. Reuse/IP decision under the owner's new authorization

The #11 owner message explicitly grants future copy/reuse/modification permission for **first-party** DnD and Orchestra code. This supersedes R8's “no separate grant supplied” finding for owner-controlled first-party material only. It does not prove ownership/assignment of Sstobo, DrSeedon, `vadimd`, or any other contributor's expression; it does not clear dependency, asset, SRD, trademark, generated-art, music/SFX, voice, or personal-data rights.

Therefore literal reuse is now an engineering option, not the default prohibition. The row-level verdict remains conditional:

1. identify exact lines/blob and authors with `git blame/log`;
2. record why each author is covered by the first-party grant or a separate assignment/license;
3. close immediate and transitive code/data dependencies and notices;
4. confirm the copied behavior fits this ADR rather than importing a second authority;
5. copy tests/provenance with the code and record modifications.

`reuse-matrix.md` gives exact candidates. The practical conclusion is still narrow reuse:

- DnD `WorldRepository` and its tests prove revision/CAS/fsync/rollback behavior, but copying it as the canonical store would violate accepted R4 because it commits `world.json` separately.
- DnD `DiceRoller` has mixed Sstobo/Maxim line provenance and global RNG/CLI/WorldGraph coupling; it is not a clean SRD 5.2.1 resolver.
- DnD `campaign_views.py` is owner-authored but denylist-based and cannot become the security projector.
- Orchestra `merge_operations.accept_operation_snapshot` is strong literal prior art for digest conflict/insert-or-read, but the file has mixed Maxim/DrSeedon authorship and git-agent coupling.
- Orchestra `LiveBroker` is explicitly best-effort/drop-oldest and is valid only for ephemeral partials/overlays, never durable projections.
- Orchestra routing code is useful provider-selection prior art but carries Pydantic/quota/model-registry coupling and is outside the synchronous game kernel.

The new private repository is still not created in this research. Its dependency graph must be selected fresh; current manifests/locks are not copied wholesale.

## 15. Consequences and falsification gates

### Positive

- One authority answers “what happened?” across story, tactics, rolls, consequences, and presentation.
- Standard and unusual actions converge on the same validator/reducer rather than duplicate game logic.
- R4 recovery applies directly: no distributed story/tactical reconciliation.
- Secret-safe projections and narrator context are derivations, never filtering at the browser/provider.
- Side phases and classic initiative share state and action semantics, making the experiment reversible.
- R9 can add authored content only through definition/rules/operation contracts with mechanical closure.

### Cost

- The aggregate schema is a load-bearing migration boundary.
- One SQLite writer serializes room mutations; contention/failover remain unmeasured.
- Authoring requires reference/reachability/reveal-dominance lint and scenario fixtures.
- Curated class/spell mechanics still constitute substantial rules work; this ADR deliberately refuses “full D&D.”
- An AI plan may frequently be rejected/redrafted until schemas and adjudication quality mature.

### Stop and reopen #11 if any implementation requires

- a separately committed narrative, tactical, roll, or canonical projection store;
- model/client-authored mutation outside a validated ResolutionPlan;
- a generic patch/metadata/expression/script operation;
- damage/heal/condition without a stored resolution or deterministic rule reference;
- reveal content supplied by the model/command rather than pinned authored facts/routes;
- browser/admin/narrator filtering of full secret state;
- checking current version/stage before exact duplicate result lookup;
- a whole-turn retry after world commit may have happened;
- changing combat mode after encounter actions without an explicit migration oracle;
- mixing SRD 5.1/5.2.1 rules or untracked brand/content material;
- literal code whose first-party/contributor/dependency closure is incomplete.

## 16. Findings and confidence

| Finding | Confidence and evidence tier |
|---|---|
| One aggregate is coherent with accepted R4 and avoids a story/tactical unknown-commit gap. | **CONFIRMED as a contract requirement** by accepted R4 primary local evidence; **SUPPORTED synthetically** by 48/48 probe assertions. |
| The seven old primitives are insufficient/sometimes overbroad as the public/core vocabulary. | **CONFIRMED by contract decomposition** and old R2 blockers; the extended algebra is **LIKELY sufficient** for the synthetic slice, **UNCERTAIN** until R9 authored-action enumeration. |
| Route-specific reveals, full cross-reference lint, and alternate durable routes close measured R1 defects. | **CONFIRMED for the synthetic fixtures**; real campaign reachability remains **UNCERTAIN** until R9. |
| Positive table/scene/admin/narrator projections can exclude known secret canaries. | **CONFIRMED in R4/R7/#11 synthetic probes**; production projector/browser safety remains **UNCERTAIN**. |
| Side phases and classic fallback can share one canonical tactical state. | **CONFIRMED structurally/synthetically**; gameplay quality/balance is **UNCERTAIN** and belongs to R10. |
| The selected six level-3 class baselines exist in SRD 5.2.1 and imply the enumerated minimum rule categories. | **CONFIRMED from the official primary PDF**; exact prepared abilities/content balance remains **UNCERTAIN** until R9/R10. |
| Owner authorization makes literal first-party reuse possible. | **CONFIRMED as an owner decision for owner-controlled first-party code**; contributor ownership and dependency/content closure remain **UNCERTAIN** until documented per blob. |

## 17. Counter-evidence and limits

1. A separate bounded tactical service could scale independently, but it would need a measured distributed transaction/unknown-outcome protocol and would no longer inherit R4. The MVP has no evidence that this cost buys needed scale.
2. Canonical event sourcing also passed R4's oracle; current-state/outbox was chosen for direct recovery, not because events are invalid (`r4/coordinator-adr.md:142-148,182-186`).
3. Full projection families may be expensive on a dense board. Chunk/asset references may be introduced after measurement, but version/allowlist/ack guarantees cannot weaken.
4. Static alternate-route lint cannot prove a satisfying story. It proves only declared reachability under modeled carrier-loss cases.
5. A private adjudicator seeing secrets can still choose a biased/poor plan. Typed validation prevents illegal mutation and leakage paths; it does not prove fun, fairness, or narrative quality.
6. The six-class subset may still be too large. R9/R10 may remove hero mechanics, but may not silently approximate SRD behavior while labeling it supported.
7. Git attribution is not ownership proof. The new owner permission changes the first-party route but does not erase third-party authorship or obligations.

## 18. Sources and package index

### Canonical/local primary evidence

1. `docs/tasks/377/mvp-product-spec.ru.md` — owner-approved product truth, especially §§5–19, 22–25.
2. `docs/tasks/377/research.md` — original measured reuse/current-flow/IP baseline; superseded only where later owner decisions differ.
3. `docs/tasks/377/phase3/r4/coordinator-adr.md`, `state-machine.md`, `fault-matrix.md`, schemas/probe/results — accepted persistence/recovery input.
4. `docs/tasks/377/phase3/r8/remote-authority-threat-model.md`, `ip-route.md`, `transfer-manifest.tsv` — accepted remote authority and old fail-closed IP baseline; #11 owner grant supersedes only its absent-first-party-grant premise.
5. Old R1 package at `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-narrative-director/docs/tasks/377/phase3/r1/` and `/tmp/r1-direct-review-final.txt` — read-only evidence.
6. Old R2 package at `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-typed-world-tools/docs/tasks/377/phase3/r2/` and `/tmp/r2-direct-review-final.txt` — read-only evidence.
7. R7 commit `2bd6a1f` package at `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-three-surfaces/docs/tasks/377/phase3/r7/` — read-only synthetic evidence, not an implemented UI.
8. DnD source/history in this worktree and Orchestra source/history under `/home/kesha/orchestra` — direct code and Git measurements summarized in `reuse-matrix.md`.
9. #11 owner/orchestrator message — explicit first-party reuse authorization and research scope.

### External primary source

10. [Wizards of the Coast, System Reference Document 5.2.1 PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf) — official CC-BY-4.0 rules document, published 2025-05-01; checked 2026-08-16.
11. [Official SRD page and FAQ](https://www.dndbeyond.com/srd) — download/version/licensing/attribution context, page updated 2026-03-02; checked 2026-08-16.

### Package artifacts (no duplicate summary)

- `core-adr.md` — the sole canonical conclusion/contract.
- `core-contract.schema.json` — machine-readable research shapes.
- `contract-matrices.md` — exact turn, operations, SRD subset, projection, and fault oracles.
- `old-finding-disposition.md` — every material R1/R2/R7 finding and its disposition.
- `reuse-matrix.md` — literal/behavioral reuse candidates, authorship, dependencies, coupling, and closure.
- `research_core_probe.py`, `test_research_core_probe.py`, `probe-results.json` — reproducible synthetic evidence, explicitly not product/UI code.
- `codex-review.md` — independent review record after the canonical review gate.
