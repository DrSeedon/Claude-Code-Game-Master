<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

R9 Phase 1 is not yet implementation-ready. The overall architecture is coherent, but the deterministic probe materially overstates what it validates: several security- and authority-critical checks are either absent or operate on synthetic data that bypasses the real contract surfaces.

A verified artifact line not supplied in the request is:

> “A failed provenance row blocks product admission even when the story graph passes.”

I found 4 blocking issues and 4 non-blocking specification gaps. No files were edited.

## Findings

blocking: [r9_probe.py:178](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:178) — effect templates are neither defined nor validated, despite being the authoritative bridge to Core mutations. The probe checks only `mechanic_refs`; `effect_template_ids` can contain an arbitrary dangling ID and still report `reference_and_route_lint: PASS`. The schema itself has no `effect_templates` collection, so operations, parameters, subject kinds, idempotency, and allowlist membership cannot be compiled or checked. A counterexample adding `effect.does_not_exist` passed the complete probe. Add a closed, versioned effect-template map and validate every transition/redirect/consequence reference and compiled Core operation.

blocking: [r9_probe.py:202](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:202) — the secret-leak evidence does not test the promised projection boundary. It constructs a new three-part payload from selected `public_fact`, speaker, and event fields; it does not serialize the package’s actual table/admin/narrator/audio/cache/asset projections, does not inject a canary into every private field, and does not test reveal dominance. Consequently, a secret fact may be referenced by an audio cue before its route commits without failing. The reported “5 secret needles absent” is true only for this handcrafted payload, not the security property claimed in [research.md:91](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/research.md:91). Require actual positive serializers and stateful pre-/post-reveal tests; scan IDs as well as text and metadata.

blocking: [r9_probe.py:225](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:225) — provenance admission is reduced to `decision == approved` and asset status. It does not validate expiry, allowed use, reviewer authority, relationship closure, withdrawal propagation, or voice→script→master/music-work→master joins promised by the contract. Schema validation also disables format checking at [r9_probe.py:125](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:125); an invalid `creation_date: "not-a-date"` passed. This permits an IP admission bypass. Model relationship rows explicitly, enable deterministic date/term validation, and make admission a positive fail-closed checker rather than merely asserting that this fixture is blocked.

blocking: [r9_probe.py:124](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:124) — the canonical package hash is never calculated or compared, although [content-contract.md:40](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/content-contract.md:40) makes it the immutable authority boundary. Replacing the fixture hash with any other valid 64-hex value passed. Define exact canonicalization, blanking, encoding, and hash comparison in executable form; include a mutation test proving any authoritative field change invalidates the hash.

suggestion: [r9_probe.py:103](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:103) — the “24 terminal traces at 81/89 minutes” are topology walks, not reachable state traces. Enumeration ignores beat entry/completion predicates, transition `when`, effect-derived state, clue-route preconditions and time costs, redirects, outcome predicates, cuts, and hard caps. It also credits obligations merely by visiting a beat. Thus mutually inconsistent or ineligible branches can count as showcase paths, while real redirect/recovery time is omitted. Replace this with bounded state-space exploration over compiled effects and predicates, distinguishing showcase, refusal, recovery, loss, and infeasible traces.

suggestion: [content-contract.schema.json:180](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/content-contract.schema.json:180) — DNF identity semantics contradict the normative prose and fixture. The schema says “an empty outer array means always,” while [content-contract.md:73](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/content-contract.md:73) says `[[]]` is always, and the probe recognizes only `[[]]` as a start. Freeze one representation and reject the other so Core, compiler, and linter cannot interpret eligibility differently.

suggestion: [r9_probe.py:155](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:155) — cardinality checks do not enforce semantic uniqueness. The probe accepts six records all using duplicate role values, and the schema permits three outcomes all classified as `success`. Counterexamples with `fury` changed to `guardian` and every terminal changed to `success` both passed. Require exactly one of each starter role and at least one unique `success`, `loss`, and `mixed` terminal; also validate unique highest-priority resolution for every reachable state.

suggestion: [r9_probe.py:190](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:190) — map and encounter validation is not implementable from the current package. Maps contain only logical layer/anchor references, but the contract has no collision, LOS, lighting, topology, spawn-anchor, objective-cell, or enemy-template definitions for those references to resolve against. The probe checks only that each map asset and provenance ID exists. Add closed authoritative topology/template records or specify an exact hashed external manifest interface before claiming map reachability, LOS symmetry, spawn, roster, or unsupported-mechanic closure.

## Verdict

**Needs work — not decision-grade or implementation-ready.**

The sanitized fixture demonstrates schema shape and a useful synthetic combat falsification, but it does not establish the advertised reference, reachability, secret, provenance, hash, or map gates. The four blocking authority/security gaps must be resolved before Phase 2 planning can safely treat this as the canonical external contract.

Review route: required Sol review unavailable in this session; adversarial self-review performed. Cross-family verdict unavailable.

## Round (2026-08-16T20:46:57Z)

<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

Six prior findings are fixed, one is substantially fixed, and one remains blocking. Two load-bearing counterexamples still pass the current probe.

Verification quote from [content-contract.md:40](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/content-contract.md:40):

> “No running room loads ‘latest.’”

## Findings

- **Prior 1 — STILL BLOCKING:** effect templates now have closed signatures and reference-set equality, but argument reference closure, `subject_kind`, and idempotency semantics remain unchecked. A rehashed mutation changed `effect.clock_pressure` to `move_entity` with nonexistent entity/anchor IDs and `subject_kind: fact`; the full `check_contract` still returned `PASS`. See [r9_probe.py:223](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:223) and [r9_probe.py:827](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:827).

- **Prior 2 — FIXED:** positive projections, pre/post-reveal dominance, scoped private projections, and mutation probes replace the handcrafted payload. See [r9_probe.py:526](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:526).

- **Prior 3 — FIXED:** bounded state exploration now evaluates DNF predicates, effects, redirects, completion, obligations, timing, and outcome priority. See [r9_probe.py:290](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:290).

- **Prior 4 — FIXED:** provenance now has positive admission, format checking, typed relationships, allowed-use checks, expiry, qualified reviewers, and transitive withdrawal controls. See [r9_probe.py:637](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:637).

- **Prior 5 — FIXED:** canonical serialization and authoritative mutation rejection are implemented at [r9_probe.py:128](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:128).

- **Prior 6 — FIXED:** duplicate roles and missing outcome classes are rejected by [r9_probe.py:807](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:807). Both prior mutations now fail.

- **Prior 7 — FIXED:** only `[[]]` is accepted as the DNF identity; an empty outer array is schema-invalid.

- **Prior 8 — FIXED for Phase 1:** inline topology, enemy templates, roster closure, reachability, light, spawn capacity, and LOS calculations now provide executable map/encounter evidence.

blocking: [r9_probe.py:223](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:223) — `apply_effect` validates argument types but silently accepts most operations without validating referenced subjects or enforcing the declared idempotency scope. This can compile dangling Core mutations that later crash or corrupt state. Add operation-specific reference/subject validation and exercise each idempotency scope with repeated application.

blocking: [r9_probe.py:315](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-authored-slice/docs/tasks/377/phase3/r9/r9_probe.py:315) — terminal resolution does not apply or verify the outcome’s `persistent_consequence_template_ids`. Removing `effect.persist_success` from the success transition and deleting that template—while leaving the outcome’s declared `consequence.success`—still passes the full probe. The terminal therefore satisfies obligations without demonstrating that its declared consequence was committed. Apply outcome templates during resolution or assert that the resulting state contains every declared terminal consequence.

## Verdict

**NEEDS WORK.**

Phase 1 is close, but the two remaining state-integrity gaps are genuinely blocking: dangling authoritative effects and terminal outcomes that can pass without persisting their declared consequences.

Review route: final prose round completed by adversarial self-review; required external Sol/cross-family route was unavailable.
