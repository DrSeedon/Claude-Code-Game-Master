# #377 / R9 — authored MVP slice contract research

- **Date:** 2026-08-16 (Europe/Berlin)
- **Scope:** Phase 1 research/abstract experiment only
- **Decision owners:** narrative/content lead; game-systems lead for encounter acceptance; R8 qualified provenance authority
- **Excluded:** production campaign prose/assets, private repository, deploy, paid provider, real participant test, current campaign data, Orchestra runtime mutation

## Question

### Context

The approved AI-table MVP must deliver one original variable 60–90 minute slice for 3–5 players with six selectable level-3 heroes, authored truth/NPC goals/secrets/turning points, AI improvisation, one social choice, investigation/trap and physical roll, a tactical fight, boss/final conflict, persistent consequence/hook, Severin, authored/fallback voices, cached combat lines/music/SFX, and a remote-authoritative Core [L1]. The Unified Core already pins immutable content/rules, uses one aggregate/kernel, requires route-specific reveal and positive projections, and makes side phases reversible [L2][L3]. R5 and R6 separately own approved input and post-commit audio [L5][L6].

### Change under test

A versioned typed content package plus author/lint/timing/balance/provenance/dry-run workflow, without assuming a script language, adventure-book layout or unrestricted LLM trigger format.

### Baselines

1. Linear/branch-and-rejoin scenario prose with human-GM judgment.
2. Freeform scene packets with LLM-selected natural-language triggers/effects.
3. A clue/scene graph without typed Core, timing, asset or provenance closure.

### Measurable outcome

The proposed contract succeeds at research level only if an abstract fixture:

- validates as a closed schema and has no unresolved reference/mechanic;
- gives every mandatory clue alternate routes including a durable non-NPC route;
- survives declared carrier loss and reaches success/loss/mixed without a sink/cycle;
- satisfies all fixed showcase obligations on every enumerated showcase path in 60–90 target minutes;
- serializes player/narrator data without secret canaries/private truth;
- gates every asset/content class through row-level provenance;
- defines 3/4/5 encounter, starter-role, presentation, cut and facilitator-free evidence requirements;
- reports synthetic balance failures without calling them fun or real difficulty.

## Hypotheses and falsifiers

| Hypothesis | What would prove it wrong | Result |
|---|---|---|
| **H1:** a compiled typed beat/clue graph is the smallest content authority compatible with the Core. | A fixed slice obligation cannot be expressed without runtime-mutated prose truth/a second authority, or the graph cannot support a plausible off-rail terminal route. | **SUPPORTED, not production-proven.** The schema expresses the required surfaces and the abstract graph closes; Core v1 must migrate to v2 to pin the whole envelope. |
| **H2:** a looser branching script or natural-language storylet trigger is sufficient and cheaper. | Deterministic route/secret/time/mechanic/provenance gates require data those formats do not close, or natural-language evaluation becomes authority. | **REFUTED as canonical runtime authority.** Both remain possible authoring frontends only if compiled into the selected closed package [E2][E3]. |
| **H3:** official XP categories plus party-count scaling can bound two side-phase fights inside the slice. | A predeclared synthetic sweep violates outcome/alpha/death/time bands across role composition or target policy. | **REFUTED for the initial normal envelope.** It failed four of six frozen band groups; objective/round caps and actual Core simulation are mandatory. |
| **H4:** media/actual-play examples can substitute for a facilitator-free timing test. | The evidence describes mediated expectations rather than the exact unedited product/runtime trace. | **REFUTED as acceptance evidence.** Actual-play scholarship explicitly studies mediation/expectation, so R9 uses it only as a warning, not timing truth [E7]. |

## Findings

### F1 — one hashed `CampaignDefinition` v2 must cover content and authoring metadata

**CONFIRMED — tier 2 local primary contract inspection.** Core v1 has facts, routes, threats, endings, templates, terrain, consequences and locations, but no beats/obligations, NPC goals/secrets, timing/cuts, map/encounter descriptors, starter-role acceptance, presentation references or provenance relationship rows [L2][L4]. Storing those beside the pinned hash would create an unversioned authority and violate the Core's immutable definition boundary [L2].

Decision: compile the R9 author package into `CampaignDefinition` schema v2 (or a byte-equivalent envelope wholly covered by the pinned definition hash). Runtime state keeps only IDs/ledgers/lifecycle/clocks. This future Core schema change must precede production I9 authoring.

### F2 — typed storylet-sized beats are preferable to a script or freeform trigger, but remain an authoring hypothesis

**LIKELY — multi-source structural evidence plus local constraints, no author study on this product.** Ink demonstrates productive branching/joining and also documents loose, potentially spaghetti-like flow [E2]. Storylets explicitly combine preconditions/content/effects and reduce some branching burden, while the cited LLM framework used only a preliminary six-author study and acknowledges closed-ontology/narrative-control limits [E3]. Open GUMSHOE guidance uses one navigable core plus alternate clue scenes [E4].

The selected package combines closed preconditions/effects, alternate clue routes and small beat records. Natural-language authoring may later compile into it, but neither LLM trigger nor branch script is authoritative. This does not prove the workflow is pleasant; I9 must record author time, lint failures and revision count.

### F3 — the abstract compiled state graph closes after falsifying the first topology-only probe

**CONFIRMED for the fixture — tier 1 direct deterministic measurement; UNCERTAIN for production content.** The first simple graph walk found an NPC-route-failure path of 93 minutes, but adversarial review then showed that adjacency walks ignored predicates, effects, redirects and infeasible branches [R1]. That result was withdrawn, not patched cosmetically. The replacement bounded state explorer compiles DNF predicates and closed Core effects, consumes redirect limits/time, and produced:

- schema/date format, canonical hash/mutation, reference/effect/route/mechanic lint: `PASS`;
- 62 reachable states, 25 terminal states and 25 unique highest-priority resolution checks;
- 2 showcase-success, 8 recovery-success, 8 recovery-mixed, 2 pressure-success, 4 pressure-mixed and 1 deliberate-refusal/loss traces;
- 24 completed non-refusal trace durations from 79 to 85 minutes; the refusal/loss is intentionally early and not credited as a showcase;
- 28 rejected infeasible transition/condition pairings and 34 validated predicate atoms, reported separately rather than counted as paths;
- 2 single-carrier-loss cases;
- 22 referenced mechanics, all in the frozen supported set;
- 15 effect templates replayed in the same scope and rejected as duplicates, 11 non-run templates reapplied in a distinct causal scope, all 15 reapplied in a distinct run, and all four declared idempotency scopes exercised;
- 15 operation-specific dangling-reference mutations plus a mismatched subject-kind mutation rejected, and every one of the 25 terminal traces contains its outcome-declared persistent consequence;
- closed map/encounter checks over 710 reachable cells, 110 direction-independent LOS pairs and six 3/4/5 roster bands.

The fixture is intentionally sanitized: strings such as `ABSTRACT_*` carry no production scenario expression, and its 49 fail-closed provenance reasons keep every placeholder map/voice/audio route blocked.

### F4 — timing must be controlled by obligations, checkpoints and state-derived cuts, not scene deletion after overrun

**LIKELY — deterministic workbook and compiled-state closure, no human timing measurement.** The 75-minute target assigns 6/11/3/8/7/16/4/20/5 minutes to selection/social/choice/investigation/plan-roll/skirmish/dispute/boss/aftermath. Checkpoints at 32/50/60/85/90 minutes cut optional texture, fire authored pressure or select a round-boundary outcome. Mandatory agency/consequence beats are never cut. The first compiled-state pass measured 80–89 minutes and falsified its claimed six-minute reserve; tightening only the boss hard cap/aftermath budget produced 79–85 minutes and an honest five-minute worst-case reserve. The result is still unproven at a real table; I9 must run cold 3/4/5 facilitator-free reads and record human deliberation separately from system waits.

### F5 — the initial stat-only normal encounter envelope is falsified

**REFUTED — tier 1 deterministic synthetic evidence for the abstract model only.** `r9_probe.py` ran 123,000 two-encounter traces: every combination of 3–5 roles from six, 500 seeds, three envelopes and random/focus-lowest policies. Normal pass bands were frozen before the full sweep.

Normal random-target win was 99.05–99.97%, exceeding the 98% upper band for all sizes and falling below the tension/downed band for 4–5 players. Under focus-lowest, five-player any-down was 80.10% and world-first down was 24.53%, exceeding 70%/15%. Normal p90 estimated combat time was 50.55–81.70 minutes, above the 43-minute allowance in every cell. Boss alpha-kill was 0 in all cells and TPK stayed within 5%, but those successes do not rescue the failed envelope [M1].

The gentler envelope controlled focus-fire lethality but still produced a five-player p90 of 52.77 minutes. The hard focus-fire envelope produced 15.08–29.30% TPK and 64.20–101.75 p90 minutes. Therefore I9's default bounds are low-XP-ceiling skirmish + moderate-XP-ceiling boss, ≤2 stat-block shapes, enemy turns bounded by party size, non-HP objectives, target 2+3/hard 3+4 rounds, and actual Core resimulation. Official level-3 XP budgets (150/225/400 per character for low/moderate/high) are ceiling inputs, not side-phase proof [E1].

### F6 — six role templates close onboarding and coverage without authoring final characters

**LIKELY — local Core rule-coverage decision plus acceptance design.** The six fixed roles remain guardian/fury/shadow/beacon/arcanist/voice, all level 3 [L3]. `acceptance-templates.md` adds strengths, weaknesses, tactical/social hooks, first-turn prompts, visible/conditional choice caps and rejection criteria. No required clue can depend on one role, and any side-phase-invalid initiative feature must get a tested interpretation or force classic fallback. Final values, names, biographies, equipment, spells, portraits and balance remain I9.

### F7 — player-safe projection must be tested across content and media, not only world JSON

**CONFIRMED as a contract requirement and reference gate — tier 2 local primary security/audio inputs plus tier 1 fixture probe.** Core requires separate positive table/scene/admin/narrator projections, and R6 routes only already-disclosed text through logical audio identities [L2][L6]. The replacement reference serializers emit six public surfaces (table, scene, narrator, audio, cache and asset) plus separate privileged admin/scoped-narrator surfaces. Seven private secret-ID/fact-ID/truth/canary needles were absent from 1,764 pre-reveal and 2,235 post-reveal public bytes; post-reveal contained only each authored `public_fact`. Twenty-one public-source mutations were detected, seven path-metadata mutations remained nonprojected, ten private scope projections matched exactly, and a cue with a secret fact reference was suppressed until that route was committed. I9 must port these positive serializers/mutations to the actual Core/R6 adapters; the fixture does not prove an implementation that does not yet exist.

### F8 — provenance is a separate admission gate, not a story-schema checkbox

**CONFIRMED — tier 2 accepted R8/R6 route plus external primary metadata standards.** R8 says first-party code authorization does not clear third-party content/assets/voices and requires blob/row-level evidence [L7]. R6 starts with an empty approved voice/asset roster [L6]. SPDX expressions can encode license combinations, while CC attribution guidance calls for title/author/source/license and modification notice [E5][E6]; neither constitutes legal approval.

The schema requires source/author/version/hash/rights/license/terms/inputs/uses/territory/term/attribution/reviewer/decision, a frozen evaluation date/qualified reviewer set, and typed recording→script, recording→voice and music-master→work relationships. The positive admission checker rejects placeholder evidence, disallowed uses, expiry, withdrawal and dependent relationship failure. The abstract package is structurally valid but rejected for 49 reasons. A mechanically all-green synthetic control passes, while expiry and withdrawal mutations fail; this tests checker reachability and is explicitly not rights evidence or legal clearance. “Чикен карри” remains unidentified; no supplied exact source resolves it, so it cannot be used as a source, owner, style input or clearance claim.

### F9 — facilitator-free evidence needs separate technical, content, soul, repetition and product verdicts

**LIKELY — predeclared protocol, not yet executed.** `dry-run-protocol.md` defines ten automated traces, cold 3/4/5 reads, no-GM operator restrictions, frozen success criteria and a failure taxonomy. A technical fallback may preserve a content run but does not make the failed subsystem green. Synthetic or author evidence cannot prove fun; real spontaneous continuation intent remains R10-only [L1][L8].

## Decision-grade artifact index

| Requirement | Artifact |
|---|---|
| canonical contract/schema, truth/secrets/clues/NPC/beats/redirects/endings/maps/audio/provenance | `content-contract.md`, `content-contract.schema.json` |
| sanitized example graph | `abstract-example.json` |
| 60–90 workbook, checkpoints/cuts, table-read rows | `timing-and-balance.md` |
| deterministic schema/reachability/secret/mechanic/provenance checks | `r9_probe.py`, `probe-results.json` |
| encounter/balance experiment | `timing-and-balance.md`, `r9_probe.py`, `probe-results.json` |
| six starter-role templates | `acceptance-templates.md` |
| map/NPC/voice/line/asset/provenance templates | `acceptance-templates.md` |
| facilitator-free dry run | `dry-run-protocol.md` |
| stop gates and exact future I9 delivery/oracle | `i9-handoff.md` |

## Counter-evidence and limitations

1. A script language such as Ink may be much faster for writers and already has mature tooling [E2]. The selected contract does not reject a compiler/frontend; it rejects script control flow as the unlinted runtime authority.
2. Storylet+LLM work offers preliminary evidence for authorable responsiveness [E3]. Its natural-language trigger path could reduce author burden, but it cannot authorize Core state changes or secrets without deterministic compilation/validation.
3. A guaranteed alternate clue can feel artificial if its carrier follows the party without causal world logic. The contract therefore requires a carrier/reaction/effect and preserves refusal/loss; mechanical reachability alone is not narrative quality.
4. Bounded compiled-state exploration models declared predicates/effects/actions, not arbitrary player language, semantic quality or compound destruction. The Core/I9 linter covers declared single critical-carrier losses only; adversarial dry runs must seek multi-carrier and unmodeled off-rail failures.
5. Target minutes are author budgets, not measured human duration. Refuting the initial 93-minute topology path, then the compiled 89-minute reserve claim, and measuring replacement 79–85-minute traces proves the checker operates on declared numbers, not that humans will finish in that time.
6. The combat model omits map/LOS, exact dice/features/spells, human strategy, latency and audio. Its result rejects one abstract envelope; it cannot certify another or prove fun.
7. Official XP guidance assumes the published combat framework, not this side-phase experiment [E1]. Party-side focus and world focus remain material risks.
8. Actual-play examples are mediated and may shape expectations [E7]; no closed scenario prose/map/transcript was copied or used as timing data.
9. Rights rows, the synthetic positive admission control and engineering checks are not legal opinions or actual clearance. Qualified R8 review remains mandatory.

## Affected future files and interfaces

- Unified Core: `CampaignDefinition` v2 schema/compiler/hash and aggregate compatibility; NarrativePolicy consumes the pinned envelope.
- I9 private package: paths enumerated in `i9-handoff.md` only after I0/Core gates.
- R5: shared-plan card, pending physical roll and dispute correction/explanation consume approved input only.
- R6: logical voice/event/music/cache references join post-disclosure to approved manifests; no raw provider ID in content.
- I4/I5/I6/I7: consume definition/encounter/presentation content; cannot invent missing content locally.
- R10: consumes the frozen dry-run/playtest packet and alone owns the continuation/fun verdict.

## Risks and edge cases to retain

- player refuses the premise or never engages boss: explicit loss/mixed consequence, not forced relocation;
- NPC carrier dead/absent/refuses; durable route remains causally available;
- failed physical roll adds cost but cannot delete the only conclusion;
- two endings match; unique priority or explicit mixed ending required;
- 5-player focus fire and action-count timing;
- no-healer party and no assumed free recovery;
- role feature incompatible with side phases;
- dispute cites an undisclosed fact/rule or correction applies twice;
- hidden map layer/asset metadata/cache line leaks a canary;
- withdrawn voice/master has linked derived outputs;
- hard cutoff during death saves/boss phase;
- provider/STT unavailable: typed/text-only degradation preserves state, not subsystem acceptance;
- unidentified “Чикен карри” reference remains excluded.

## Reproduction

Run from this worktree using the mandated environment isolation:

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT \
  uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice \
  --frozen python docs/tasks/377/phase3/r9/r9_probe.py --iterations 500 --write
```

Observed: schema/formats, canonical hash mutation, reference/effect/route/mechanic and secret-projection checks `PASS`; all 15 effect templates rejected same-scope duplicates, all four idempotency scopes were exercised, 15 dangling-reference mutations and one subject-kind mutation were rejected, and every terminal committed its declared consequence; 62 reachable states, 25 terminals, 24 completed non-refusal traces at 79–85 minutes, 34 predicate atoms and 28 infeasible edges kept separate; map closure covered 710 cells/110 LOS pairs/six roster bands; abstract provenance failed for 49 reasons while positive/expiry/withdrawal controls behaved as predeclared; 123,000 combat traces retained the normal synthetic verdict `FAIL`. Full cells are in `probe-results.json`.

## Review-gate inputs

- **Changed files/consumers:** research artifacts only under `docs/tasks/377/phase3/r9/`; future consumers are Core schema/compiler and I9/I4/I5/I6/I7/R10.
- **Author runtime:** Orchestra Codex runtime; exact versioned author model ID is not exposed in the artifact metadata available to this worker.
- **Exact AC:** R9 ticket in `docs/tasks/377/plan.md` plus the orchestrator's #14 assignment and nine required output groups.
- **Named checks/output:** reproduction command above produced schema/hash/reference/projection `PASS`, 15/15 same-scope duplicate rejections, 15/15 cross-run applications, all four idempotency scopes, 15 dangling-reference mutation rejections, terminal consequence commits, 62 reachable states/25 terminals, completed times `[79..85]`, 710 map cells/110 LOS pairs/six roster bands, 49 expected fixture provenance failures plus green synthetic/rejected expiry-withdrawal controls, 123,000 combat traces and normal verdict `FAIL`. `git diff --check`, JSON parsing, required-anchor/file checks and the final `jq -e` predicate are rerun after review disposition.
- **Risk/oracle:** high due externally consumed content schema, secrets/projections, rules boundary and admission/provenance gates. The probe was authored in this research and is not an independent pre-existing oracle. Canonical route is targeted Sol review, not skip/Luna.
- **Review outcome:** round 1 `Needs work` found four blocking authority/security gaps and four specification gaps [R1]. The allowed final round accepted all eight earlier findings as fixed or fixed-for-Phase-1, then found two blocking state-integrity counterexamples: dangling authoritative effect arguments/idempotency and terminal outcomes without committed declared consequences [R1]. Both were reproduced and closed after that verdict with the deterministic mutation/replay/terminal-ledger controls above. The review artifact's final verdict remains `NEEDS WORK`; the canonical two-round prose ceiling forbids a third review, so confirmation is escalated to the orchestrator rather than relabeled as approval.

## Sources

### Local primary/canonical sources read for R9

- **[L1]** `docs/tasks/377/mvp-product-spec.ru.md` — fixed product facts and exclusions.
- **[L2]** `docs/tasks/377/phase3/core/core-adr.md` and `core-contract.schema.json` — aggregate, definition, truth/reveal, operations, projections and v1 schema.
- **[L3]** `docs/tasks/377/phase3/core/contract-matrices.md` and `old-finding-disposition.md` — end-to-end operation/rule/role/projection/reachability obligations.
- **[L4]** `docs/tasks/377/phase3/core/reuse-matrix.md`, probe result and review artifacts — reuse/provenance limits and evidence scope.
- **[L5]** `docs/tasks/377/phase3/r4/coordinator-adr.md`, `state-machine.md`; R5 `research.md`, `speech-input-protocol.md`, schemas/results/review — approval/input/roll/reconnect/privacy interface.
- **[L6]** R6 `research.md`, `playback-event-contract.md`, `provenance-boundary.md`, capability/result/review artifacts — post-commit presentation/audio, cache, voice/asset and withdrawal interface.
- **[L7]** R8 `ip-route.md`, `transfer-manifest.tsv`, `repo-security-baseline.md`, `remote-authority-threat-model.md`, review — fail-closed content/repository/IP route.
- **[L8]** `docs/tasks/377/plan.md` R9/I9/R10 and `docs/tasks/377/research.md` — ticket acceptance, prior evidence and limits.
- **[R1]** `docs/tasks/377/phase3/r9/codex-review.md` two-round review artifact — both `Needs work` verdicts and the counterexamples retained verbatim.

### External sources opened 2026-08-16

- **[E1] Primary rules guidance:** Wizards of the Coast, [2024 Basic Rules: DM's Toolbox](https://www.dndbeyond.com/sources/dnd/br-2024/dms-toolbox), encounter budgets/troubleshooting.
- **[E2] Primary implementation documentation:** Inkle, [Writing with Ink](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md), branch/join/loop authoring.
- **[E3] Primary research:** Sun et al., [Drama Llama](https://arxiv.org/abs/2501.09099), LLM/storylet authoring study and limitations.
- **[E4] Open publisher guidance:** Pelgrane Press, [Core Vs. Alternate Scenes](https://pelgranepress.com/2021/05/17/core-vs-alternate-scenes/), structural clue/scene guidance only.
- **[E5] Primary standard:** SPDX, [SPDX License Expressions 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/).
- **[E6] Publisher guidance:** Creative Commons, [Recommended practices for attribution](https://wiki.creativecommons.org/index.php?title=Recommended_practices_for_attribution).
- **[E7] Primary open-access scholarship:** Denny & Webber, [Not Actual Play: Examples of Play and Expectations of Experience in TTRPGs](https://www.open-access.bcu.ac.uk/15884/).
- **[E8] Primary licensed rules document:** Wizards of the Coast, [SRD 5.2.1](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), exact version/license/attribution source.

## Phase 1 conclusion

The implementation-ready direction is a bounded typed content package compiled into one canonically hashed Core definition, with storylet-sized beats, closed operation templates, alternate clue routes, causal pressure, compiled state-derived endings/cuts, positive safe presentation, closed map/enemy records and positive fail-closed provenance admission. The first adjacency-only reachability claim was refuted; the replacement abstract state-space/projection/hash/map/provenance probes now close their fixture claims. The encounter experiment still prevents a false closure: the initial normal stat envelope is not approved, and I9 must add explicit objective/round caps and rerun actual Core mechanics before authoring is accepted. No result here proves fun, author usability, room timing, voice quality, product serializer correctness or legal clearance.
