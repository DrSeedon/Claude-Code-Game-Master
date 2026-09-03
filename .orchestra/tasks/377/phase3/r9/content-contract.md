# R9 canonical authored-slice content contract

Status: Phase 1 proposal for future I9. This is a contract and abstract fixture, not production campaign content.

## Decision

Use a **typed, compiled content package**. Authors work in small beat/NPC/clue/asset records; the build compiles them into one content-addressed `CampaignDefinition` schema v2. The runtime pins that hash in the Unified Core `RoomRunAggregate`. AI may select eligible authored beats, improvise expression, and propose a closed `ResolutionPlan`; it may not edit truth, invent a transition/effect, or create a second story state.

This direction combines the useful part of three alternatives without adopting any wholesale:

| Alternative | Useful property | Rejected as canonical authority because |
|---|---|---|
| linear/branch-and-rejoin script | easy prose authoring; explicit joins | branch growth and invisible rejoining make carrier loss, timing, and secret dominance difficult to prove; Ink's own guide notes that loose knot/divert flow can become “spaghetti-like” [E2] |
| storylets with preconditions/effects | modular authored events and incremental responsiveness | natural-language trigger evaluation is nondeterministic; recent LLM-storylet evidence is preliminary (six authors) and acknowledges closed-ontology limits [E3] |
| clue/scene graph | explicit alternate routes and navigable core | scenes alone do not model Core operations, timing, NPC lifecycle, assets, or terminal consequences |
| **selected typed package** | storylet-sized author records + clue reachability + closed effects | more up-front lint/schema work; accepted because I9 is one polished bounded slice, not a general authoring platform |

The package is bounded to at most 18 beats, 8 redirects, 3 maps, 2 encounters, 6 starter roles, and 6 routes per clue. Adding content to make a failing trace pass is not the default remedy: cut, merge, or rewrite first.

## Normative artifacts

- [`content-contract.schema.json`](content-contract.schema.json) is the machine-readable closed shape.
- [`abstract-example.json`](abstract-example.json) is deliberately sanitized and is not product-admissible: its assets/rights rows are blocked placeholders.
- [`r9_probe.py`](r9_probe.py) defines the deterministic cross-field checks and synthetic experiment.
- [`probe-results.json`](probe-results.json) records the measurement.

JSON Schema validates local types and closed fields. I9 also needs the cross-field linter below; Draft 2020-12 cannot prove reference closure, graph reachability, equality of hashes, secret dominance, or combat adequacy by shape alone.

## Author workflow

1. **Write truth, not scenes.** Create immutable `truth_facts`, explicit `secrets`, NPC goals/refusal boundaries, threats, endings, and prohibited contradictions. Every secret fact has separately authored player-safe `public_fact`.
2. **Declare showcase obligations.** Map each of the twelve fixed experience obligations to one or more beats. A beat is a delivery opportunity, not a forced scene order.
3. **Author conclusions and routes.** Each mandatory clue conclusion gets at least two independently eligible routes, including one durable non-NPC carrier. A route owns its exact reveal set and delivery mechanic.
4. **Add beats as bounded storylets.** Each beat receives a closed DNF entry predicate, closed completion predicate, target/hard-cap minutes, cut rule, supported mechanic references, presentation cues, and explicit transition results.
5. **Add honest redirects.** A redirect is an authored world reaction, mobile carrier, environmental trace, or deadline consequence. It commits visible state and preserves the player's next choice. It may move information, never rewrite truth or teleport the party.
6. **Bind Core effects.** Every transition refers to a versioned effect template which compiles only to the Unified Core operation allowlist. A required path may not contain `unsupported_in_mvp`.
7. **Attach maps, encounters, roles, presentation and provenance.** References are logical IDs, never filesystem discovery, provider voice IDs, or arbitrary prompts.
8. **Run lint and graph probes before prose polish.** Reference closure, reachability, carrier-loss, secret-projection, unsupported-mechanic, time-path, asset and provenance checks must pass. A failed provenance row blocks product admission even when the story graph passes.
9. **Run the frozen facilitator-free dry run.** Exercise all trace classes and record actual duration without changing thresholds afterward.
10. **Freeze the package.** Deep-copy the package, replace `identity.content_hash` with exactly 64 ASCII zeroes, serialize UTF-8 JSON with recursively sorted object keys, no insignificant whitespace (`separators=(",", ":")`), `ensure_ascii=false`, and NaN/Infinity forbidden; SHA-256 those bytes and write the lowercase hex digest. Recompute and compare on admission. No running room loads “latest.” `r9_probe.py` also mutates an authoritative timing field and requires the pinned digest to fail.

## Contract semantics

### Identity and compatibility

`identity` binds package/revision/hash/locale and the original-or-cleared declaration. `compatibility` pins:

- `core_campaign_definition_schema = 2`;
- `ruleset_id = srd-5.2.1-mvp-1` and exact engine version;
- the complete Core operation allowlist;
- `r5.speech.v1` and `r6.audio.v2`.

The current Core research schema is v1 and cannot encode beats, NPC goals, timing, presentation references, or asset/provenance closure. I9 must not maintain those in an unpinned side file. Before authoring production data, I4/I9 must add `CampaignDefinition` v2 (or a byte-equivalent compiled envelope) and extend the aggregate's pinned definition hash to cover all fields in this contract. This is a required compatibility migration, not permission for another mutable authority.

`entities` closes non-NPC location/object/event/archetype references, `choice_templates` closes owner and allowed values for every predicate choice, and `roll_templates` closes each declared physical d20/pending-Core result. Subject, carrier, speaker, choice and roll IDs may not rely on name conventions or an unpinned side file.

### Authored truth, secrets, clues and NPC state

- `truth_facts.*.truth` is private immutable author truth.
- `public_fact` is the only prose eligible for disclosure after its route commits.
- `secrets` declares exact NPC knowledge, minimum adjudicator scopes, a never-project policy, and a synthetic canary.
- `clues.*.routes` binds carrier, eligibility, reveal IDs, delivery mechanic, supported mechanics and time cost. A failed physical roll may add danger/cost or reduce bonus information; it cannot erase the only required conclusion.
- `npcs` declares `alive_present | alive_absent | dead`, 1–4 ordered goals, refusal boundary, response under pressure, secret knowledge, exact voice/fallback, and closed lifecycle transitions. Dialogue is generated from safe current state; a model cannot change a goal or secret for convenience.

### Obligations versus beats

The twelve exact obligation kinds are:

`hero_selection`, `narrator_selection`, `important_npc_social`, `direction_choice`, `investigation_or_trap`, `shared_plan`, `physical_roll`, `tactical_fight`, `boss_conflict`, `rules_dispute`, `persistent_consequence`, and `continuation_hook`.

A showcase trace must satisfy all twelve. Multiple beats may satisfy one obligation; conditional alternate beats need not all occur. A deliberate mission refusal may reach an explicit early `loss` or `mixed` ending, but that trace is not a valid completed MVP showcase and must be reported as such. The runtime never overrides the refusal merely to make the checklist green.

### Beat and transition rules

`entry`, `completion`, transition `condition`, outcome `when`, and redirect `preconditions` are disjunctive normal form: the outer list is OR, each inner list is AND, and **only** `[[]]` is always. The empty outer list `[]` is invalid. Atomic predicates are closed to revealed fact, completed beat, NPC lifecycle, clock threshold, encounter completion, explicit choice, active named effect and scheduled consequence.

Each transition names one of `complete | fail | decline | timeout | supported_off_rail_action`, a deterministic condition, one of `showcase | recovery | refusal | pressure`, one beat/outcome target, and zero or more immutable effect templates. Every reachable nonterminal state must have a feasible successor or terminal outcome within 18 beat visits. Beat-transition cycles are rejected in v1; a bounded same-beat redirect is permitted only with a consumed `use_limit`.

Mandatory beats use `never_cut`. Optional texture is `cut_if_late`. Exposition may be `compress_to_public_atom` only when the atom is already legally revealed. Combat/boss uses `resolve_at_round_boundary`: the authored objective state produces success/loss/mixed; no timeout invents victory, changes dice, or deletes a death.

### Redirect/pressure rules

Redirects are limited-use and declare trigger, allowed source beats, target beat, whether the current beat completes, eligibility, effect templates, optional exact clue route, time cost, and `player_choice_preserved=true`. Redirect time and route delivery time are included in state-space timing. Valid examples are an NPC pursuing their goal, a durable record appearing through a plausible world event, or a visible clock consequence changing the situation. Invalid redirects include:

- invisible walls or refusal to parse a supported action;
- teleporting the party to a planned beat;
- moving a clue without an authored carrier/reaction;
- changing a secret truth so the current guess becomes correct;
- spawning an unmanifested encounter or unsupported mechanic;
- presenting the same choice in cosmetic wording after every refusal.

### Outcomes, death and continuation

The MVP slice has exactly one `success`, one `loss`, and one `mixed` outcome with unique priorities. Each stores one or more consequence template IDs plus a continuation-hook fact. All eligible endings are evaluated by the Core after a world commit; exactly one highest-priority outcome must exist in every reachable resolving state. Equal highest priority is an authoring error.

Hero death uses Core physical death saves and persists in campaign history. The authored package may provide a resurrection path only as explicit future content; the slice cannot silently revive a hero. Every outcome, including timeout and abandonment, persists a consequence and a player-safe continuation hook.

### Maps and encounters

Each map references a cleared content-addressed art asset and contains closed collision cells, opaque cells, light rectangles, spawn-anchor cells, and objective cells. Image pixels and filenames are not authority. Each enemy template is also closed over XP, footprint, HP, AC, initiative, actions/phase, attack bonus, average damage, mechanic references, Core spawn operation and provenance. Required deterministic checks are:

- integer dimensions 8–64 cells, 5 feet/cell;
- no spawn/objective blocker or party/world overlap; all required objective and enemy spawn cells are reachable from the party spawn under declared terrain state;
- LOS fixtures are symmetric where the rules require it and hidden cells do not project;
- every light-sensitive declared cell is covered by a light zone;
- each encounter references the map, objective fact, exact 3/4/5-player roster with counts, recomputed XP budget, sufficient spawn capacity, side-phase policy, supported mechanics, time cap and failure outcome.

The encounter envelope and its current synthetic failure are in `timing-and-balance.md`.

### Presentation and audio

The content package stores logical `voice_key`, `event_key`, `music_state`, safe fact references and cache-pool IDs only. It never stores provider credentials or raw provider voice IDs.

- Narrator is exactly `narrator:severin` / `narrator.severin`, with `text_only` fallback.
- Important NPCs have exact cleared voices and one declared cleared archetype fallback or text-only.
- Generic archetypes come from a finite roster; there is no provider search or random voice.
- Normal `hit/miss/critical/death/spell` cues are `cache_only`; dynamic TTS is reserved for important NPC/story/phase/dispute events.
- Music is a state enum; SFX/music/cached line pools resolve to explicit content-addressed asset IDs, and every asset must be approved before routing.
- A cache pool must satisfy the repetition oracle in `acceptance-templates.md`; missing pools degrade to text-only/silence and never invoke live TTS.

### Row-level provenance

Every story/rules/map/image/voice/recording/music-work/music-master/SFX/font/generated-output row includes source kind, title, author/provider, URI, immutable version, date, checksum, rights-owner evidence, SPDX expression or exact `LicenseRef`, terms snapshot, every input reference, permitted uses, territory/term, attribution, reviewer and decision. `provenance_policy` freezes the evaluation date and qualified reviewer IDs. Typed relationship rows close recording→script, recording→voice and music-master→music-work joins. Unknown/placeholder evidence, an unqualified reviewer, missing relationship, disallowed use, non-approved asset, mismatched hash, expiry, or withdrawal blocks admission and propagates to dependants.

SPDX syntax helps encode license combinations but does not decide whether a use is cleared [E5]. CC attribution must retain title/author/source/license and indicate modifications where applicable [E6]. R8 remains the decision authority; this schema is an evidence carrier, not legal clearance.

“Чикен карри” is still an unidentified owner reference. No exact supplied source resolves ownership, work, license or intended use, so it is not a valid provenance row, content source, style transfer input or production reference.

## Exact interfaces

### Unified Core / R4

1. Compiler emits one immutable `CampaignDefinition` v2 and definition hash. It includes Core v1 facts/routes/threats/endings/templates/terrain/consequences plus the hashed R9 beat/NPC/obligation/map/encounter/presentation/provenance records.
2. `RoomRunAggregate` pins definition ID/hash, `srd-5.2.1-mvp-1`, rules engine and bundle hash. Runtime state contains IDs/ledgers/status/clocks only; authored prose is never mutated.
3. `NarrativePolicy(snapshot, approved_intent)` is pure and returns an eligible candidate `ResolutionPlan`. Only the Core validates and commits operations.
4. Route reveal compiles to `reveal_fact_via_route`; pressure to named `advance_clock`/`schedule_consequence`/definition-scoped lifecycle or terrain operations. No generic patch exists.
5. Projection resolves revealed fact IDs to `public_fact`, then removes IDs. Private adjudicator receives only the minimum scoped truth. Public narrator receives only the committed safe `PresentationBundle`.
6. R4 stores approved plan/result/world/audit/outbox atomically. Delivery, narration or audio retry cannot advance a beat or encounter.

Every `effect_templates` row is version 1, names its subject kind and idempotency scope, and compiles to exactly one operation. The v1 argument signatures are closed; extra or missing arguments fail before Core:

| Core operation | exact arguments |
|---|---|
| `move_entity` | `entity_id: str`, `to_anchor_id: str` |
| `apply_damage`, `apply_healing` | `source_id: str`, `target_id: str`, `amount_formula_id: str` |
| `set_condition` | `target_id: str`, `condition_id: str`, `active: bool` |
| `spend_resource` | `actor_id: str`, `resource_id: str`, `amount: int` |
| `create_effect` | `effect_id: str`, `subject_id: str` (`run.slice` or a closed entity/encounter/map ID matching `subject_kind`) |
| `set_terrain_feature` | `map_id: str`, `feature_id: str`, `active: bool` |
| `spawn_from_template` | `template_id: str`, `anchor_id: str` |
| `despawn_entity` | `entity_id: str` |
| `set_npc_status` | `npc_id: str`, `status: str` |
| `reveal_fact_via_route` | `route_id: str` |
| `advance_clock` | `minutes: int` |
| `schedule_consequence` | `consequence_id: str` |
| `open_physical_roll` | `roll_id: str` |
| `advance_combat_mode` | `encounter_id: str`, `result: str` |

The compiler validates every operation argument against the closed definition namespace and rejects a subject whose `subject_kind` does not match the operation. Idempotency keys are exact: `(run_id, effect_template_id)` for `once_per_run`; `(run_id, beat_visit_id, effect_template_id)`, `(run_id, transition_instance_id, effect_template_id)`, and `(run_id, redirect_use_id, effect_template_id)` for the three narrower scopes. A transition-scoped template may appear only on a transition, a redirect-scoped template only on a redirect, and an outcome reference must be a `schedule_consequence` template. After selecting the unique highest-priority outcome, Core applies every declared `persistent_consequence_template_id` in the same terminal commit and verifies each resulting consequence ledger row; it may not mark the run terminal if one is absent.

### R5 input

1. R9 receives only an R4-approved canonical action/party-plan card, never interim audio or a raw transcript.
2. A physical-roll beat first commits Core `open_physical_roll`; R5 freezes the current public pending-roll identity at capture admission and later supplies one approved declared total.
3. Shared-plan beats require one versioned party-plan approval. A correction creates a new immutable draft; it does not edit content truth.
4. A dispute beat accepts the player's challenge as an approved read-only input. It either emits an idempotent corrected resolution plan or a short explanation citing only an allowlisted disclosed rules/fact reference. There is no player vote or admin creative override.
5. Typed-input fallback follows the same contract and must keep the slice playable when STT is unavailable.

### R6 output

1. After safe projection acknowledgement, Core emits `audio.intent` with committed presentation/text IDs, speaker/entity, event key, policy, locale and ordinal.
2. R6 resolves the package's logical voice/cache/asset references against separately approved immutable manifests. The package never selects a raw provider resource.
3. `cache_only` miss is text-only, not live synthesis. Dynamic lines require disclosed safe text and approved voice/retention route.
4. `audio_fence`, lease, cancel, retry, reconnect and telemetry remain wholly R6/R7 concerns and cannot mutate beat state.

## Required cross-field linter

The future I9 named test must implement all of these as deterministic failures:

1. JSON Schema valid; all unknown fields rejected.
2. Canonical content hash matches; every reference and operation argument resolves with the expected kind. Mutation controls reject a dangling reference or mismatched `subject_kind` for every allowlisted Core operation and replay every declared idempotency scope in the same and a distinct scope instance.
3. Exactly six unique level-3 roles and twelve obligation kinds.
4. Bounded compiled-state exploration applies completion atoms and effect operations, evaluates DNF predicates, consumes redirect limits and timing, commits outcome-declared persistent consequences, and separately labels showcase, recovery/pressure, refusal/loss and infeasible edges. Every completed non-refusal trace satisfies all required obligations in 60–90 target minutes, and no trace becomes terminal before its declared consequence is in the ledger.
5. Every reachable state either terminates or has an eligible successor; every resolving state has one unique highest-priority outcome; no unbounded beat/redirect cycle exists.
6. Every mandatory clue has at least two routes, one durable non-NPC route, and survives every declared single critical-carrier loss.
7. Every reveal route includes its conclusion and every safe atom is dominated by an earlier/same-transition reveal.
8. Positive serializers separately produce table, scene, public narrator, audio, cache and asset projections; none exposes source path/hash/provenance metadata. Before reveal, safe text and audio cues referencing a secret fact are absent; after the committed route, only `public_fact` appears. Scan IDs, text and metadata against unique secret-ID/fact-ID/truth/canary needles. Admin and scoped narrator projections are tested for least privilege, not conflated with player output. Mutation probes must reject needles in event, voice and cache-pool public sources and prove nonprojected asset-path metadata stays contained.
9. Every mechanic/effect is in the pinned rules bundle/Core operation allowlist. Its exact arguments, subject kind, reference targets, placement and idempotency scope validate. A required path containing an unsupported or dangling mechanic fails.
10. Map bounds/collision/reachability/direction-independent LOS/light/spawn fixtures and encounter 3/4/5 roster counts, XP sums and spawn capacity validate against closed map/enemy records.
11. Positive fail-closed admission requires every output asset/content row to join to approved, unexpired, hash-matching provenance with permitted use and qualified reviewer; recording→script→voice and music-master→work relationships close. A synthetic all-green control tests checker reachability but is explicitly not rights evidence or legal clearance.
12. Withdrawal of one voice and one asset makes all linked material unroutable and selects only the declared cleared fallback/text-only/silence.

## Sources used for structural comparison

- **[E1] Local canonical primary source:** `docs/tasks/377/mvp-product-spec.ru.md`, fixed product facts and vertical-slice obligations.
- **[E2] External primary implementation documentation:** Inkle, [Writing with Ink](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md), opened 2026-08-16; knots, diverts, joins, loops and authoring complexity.
- **[E3] External primary research:** Sun et al., [Drama Llama: An LLM-Powered Storylets Framework for Authorable Responsiveness in Interactive Narrative](https://arxiv.org/abs/2501.09099), opened 2026-08-16; preliminary authoring study and stated limitations.
- **[E4] External open publisher guidance:** Pelgrane Press, [Core Vs. Alternate Scenes](https://pelgranepress.com/2021/05/17/core-vs-alternate-scenes/), opened 2026-08-16; one navigable core plus alternate clue scenes. Structural lesson only; no scenario expression was copied.
- **[E5] External primary standard:** SPDX, [SPDX License Expressions 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/), opened 2026-08-16.
- **[E6] External publisher guidance:** Creative Commons, [Recommended practices for attribution](https://wiki.creativecommons.org/index.php?title=Recommended_practices_for_attribution), opened 2026-08-16.
