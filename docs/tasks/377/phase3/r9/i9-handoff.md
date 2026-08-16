# R9 falsification gates and exact I9 handoff

## R9 decision gate

The research package is mechanically complete for the Phase 1 gate, but its final recorded review verdict remains `NEEDS WORK`: the two last counterexamples were closed after the canonical two-round review ceiling, so confirmation is escalated rather than relabeled as approval. **Production authoring is not yet executable.** I9 remains blocked until the orchestrator approves the next phase, the future private repository exists, and the Unified Core accepts/pins the entire `CampaignDefinition` v2 envelope. The current synthetic normal encounter envelope also failed its frozen bands; actual encounter templates require Core-rules calibration with objective/round caps.

## Stop/falsification list

Any item below stops or returns I9; it is not waived by prose review or a green unrelated test.

### Contract/authority

1. Any content field that can change truth, NPC goal, beat, route, encounter or ending without a new package hash.
2. Timing/NPC/asset/provenance data lives outside the definition hash or browser/model holds writable canonical story state.
3. A model emits freeform mutation, unknown operation, numeric damage, arbitrary terrain/map/entity or unsupported rule as authority.
4. I9 requires an operation/mechanic absent from the pinned Core/RulesetBundle. Add a named operation+oracle through Core review or rewrite the content; never generic-patch it.

### Reachability/agency

5. Missing operation argument reference, unresolved/mismatched subject kind or effect signature, a template used outside its declared idempotency scope, empty DNF outer list, or reachable nonterminal sink/unbounded cycle.
6. Any compiled completed non-refusal trace misses one of the twelve obligations or target time is outside 60–90; infeasible predicate/transition pairs are counted separately, never as showcase paths.
7. A mandatory conclusion has fewer than two independently eligible routes, no durable non-NPC route, or fails a declared critical-carrier-loss case.
8. A redirect changes truth, repeats a cosmetic choice, teleports/blocks the party, reveals without a route, or does not preserve a meaningful next choice.
9. A failed check blocks the only mandatory conclusion; failure must add cost/consequence or reduce optional advantage instead.
10. The slice lacks exactly one each of success/loss/mixed, reachable predicates tie at highest priority, or any terminal is committed before all of its declared persistent consequence templates and continuation hook are present in authoritative state.

### Secrets/privacy

11. Any secret canary, secret ID, private truth, adjudicator output/prompt, raw transcript, provider ID/error, or admin-inappropriate content occurs in a player/table/scene/public-narrator/subtitle/audio/cache/asset projection; or an admin/private-narrator projection exceeds its declared scope.
12. Public narration is generated from a private adjudicator context rather than a committed safe `PresentationBundle`.
13. An absent/dead NPC speaks, carries a present-only clue or remains visible without an explicit authored state transition.

### Timing/balance

14. Any valid dry run misses minute 60 or exceeds 90, or boss is not started/explicitly refused by 60.
15. A cut changes stored dice/HP, invents victory, skips consequence/hook or chooses for players.
16. Actual Core simulation fails predeclared 3/4/5 outcome, alpha-strike, focus-fire, death, round or time bands.
17. The normal package uses the R9 hard synthetic envelope, assumes random/merciful AI targeting, or uses official XP labels as balance proof.
18. Encounter completion requires killing all units after its round cap; non-HP objective/visible failure outcome is mandatory.
19. Balance assumes a healer or the synthetic 6-HP bridge without an explicit curated, consumed recovery mechanic.

### Heroes/maps/audio/assets/provenance

20. Not exactly six distinct level-3 roles, any required route depends on one selected role, or any visible feature lacks a pinned rule/golden test.
21. Map pixels are collision/LOS authority, a declared cell is out of bounds/unlit, a spawn/objective is blocked/unreachable/overlapping/hidden-leaking, roster XP/count exceeds its closed template/budget/spawn capacity, or 3/4/5 variants are improvised.
22. Provider/library/filesystem/random fallback selects a voice/audio/asset; a `cache_only` miss invokes live TTS.
23. Normal combat line pool repeats adjacent assets, plays one asset >2 times in the bounded worst trace, contains hidden facts/rules claims, or blocks action timing.
24. Any provenance field is blank/unknown/unassigned, checksum/term/status mismatches, allowed use is missing, recording→script/voice or music-master→work relationship is unresolved/withdrawn, or the reviewer is absent/not in the frozen qualified set.
25. Closed adventure text/map/character expression/show transcript, concept-reference binary, current campaign state, raw voice sample or uncleared generated asset enters the private repo.
26. “Чикен карри” is used as a source/style/owner assertion without an exact supplied source and accepted provenance row.
27. First-party code permission is used to infer rights in third-party content, SRD branding, adventure expression, maps, voices, fonts, music, SFX or provider output.

### Playtest validity

28. Technical operator gives a clue, chooses a route, plays an NPC, adjusts a roll/stat or otherwise acts as DM.
29. Thresholds, trace class, clock boundary or success wording changes after observing results without a new version.
30. Technical, content, soul, repetition and product failures are collapsed into one score.
31. Fun/continuation is claimed from synthetic runs, author table reads, actual-play media or fewer/invalid R10 sessions.

## Exact future repository inputs

I9 receives, by immutable commit/hash:

1. approved I0 private-repo/provenance/security gate;
2. `r9.content.v1` schema and linter requirements from this directory;
3. Unified Core `CampaignDefinition` v2 migration and pinned aggregate contract;
4. actual `srd-5.2.1-mvp-1` bundle with six role mechanic coverage and classic/side schedulers;
5. R5 `r5.speech.v1` typed/shared-plan/physical-roll/dispute interfaces;
6. R6 `r6.audio.v2`, approved empty-first voice/asset manifests and withdrawal/fallback behavior;
7. R8 row-level rights decision process and exact SRD attribution requirement;
8. frozen timing/balance and dry-run protocol from this directory.

Absent or version-mismatched input stops authoring rather than being filled with a local placeholder in product data.

## Exact future delivery tree

Names are relative to the future private repository and may change only with the named oracle updated before implementation:

```text
campaigns/mvp/
  package.json
  definition.compiled.json
  truth.json
  npcs.json
  clues.json
  beats.json
  redirects.json
  outcomes.json
  effect-templates.json
  encounters.json
  enemy-templates.json
  starter-roles.json
  presentation.json
assets/maps/manifest.json
assets/portraits/manifest.json
assets/audio/voice-manifest.json
assets/audio/asset-manifest.json
docs/content/provenance-policy.json
docs/content/provenance.json
docs/content/provenance-relationships.json
docs/content/dry-run-freeze.json
docs/content/dry-run-results.json
tests/content/test_i9_campaign_package.py
tests/content/fixtures/secret-canaries.json
tests/content/fixtures/adversarial-traces.json
```

No actual production file is created by R9.

## Future immutable test command and RED assertions

Create and commit the oracle before campaign implementation:

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT \
  uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q \
  tests/content/test_i9_campaign_package.py::test_i9_campaign_package_is_complete_reachable_secret_safe_and_cleared
```

The test must collect successfully and fail on a missing package behavior, not ImportError. Freeze at least these assertions:

```python
assert package.schema_version == "r9.content.v1"
assert package.core_definition.schema_version == 2
assert package.pinned_definition_hash == canonical_hash(package)
assert set(role.role for role in package.starter_roles) == {
    "guardian", "fury", "shadow", "beacon", "arcanist", "voice"
}
assert {role.level for role in package.starter_roles} == {3}
assert required_obligation_kinds == observed_showcase_obligation_kinds
assert all(60 <= trace.target_minutes <= 90 for trace in compiled_completed_non_refusal_traces)
assert exactly_one_success_loss_and_mixed_outcome(package)
assert every_reachable_resolution_has_one_unique_highest_priority_outcome(package)
assert every_mandatory_clue_has_two_routes_and_one_durable_non_npc_route(package)
assert all(single_carrier_loss_keeps_a_route(case) for case in declared_carrier_loss_cases)
assert no_reachable_nonterminal_sink_or_unbounded_cycle(package)
assert all_effect_templates_match_closed_core_operation_signatures(package)
assert every_effect_argument_reference_and_subject_kind_resolves(package)
assert every_effect_rejects_same_scope_replay_and_allows_the_next_declared_scope_instance(package)
assert every_required_mechanic_is_supported(package, pinned_rules_bundle)
assert all_maps_pass_bounds_collision_reachability_symmetric_los_light_and_spawn_fixtures(package)
assert every_encounter_has_exact_3_4_5_rosters_xp_spawn_capacity_and_round_cap(package)
assert no_secret_needle_in_any_player_scene_public_narrator_audio_cache_or_asset_bytes(package)
assert private_admin_and_narrator_projections_are_scope_minimal(package)
assert positive_provenance_admission_has_qualified_reviewer_allowed_use_hash_term_and_relationship_closure(package)
assert withdrawal_rehearsal_selects_only_declared_cleared_fallbacks(package)
assert normal_combat_makes_zero_live_tts_calls(package)
assert worst_case_line_trace_has_no_adjacent_repeat_and_max_two_plays_per_asset(package)
assert every_terminal_outcome_persists_consequence_and_continuation_hook(package)
```

Also freeze focused commands for schema/reference lint, combat simulation and dry-run workbook generation. A child/executor may implement content only after the named main command is observed red and must never edit/skip/weaken its oracle.

## Required evidence returned by I9

- exact executor commit and clean status;
- package/definition/rules/asset manifest hashes;
- named test output plus full focused regression output;
- deterministic reachability report enumerating reachable states, feasible terminal traces/minutes, infeasible edges, redirect use/time, carrier-loss cases, operation-reference mutation rejection, idempotency replays, unique-priority endings and each terminal's committed consequence IDs;
- secret scan target list, canary count and zero-leak output;
- actual Core-rules combat report for every 3/4/5 role combination and both declared/adversarial target policies, with frozen bands and failures;
- cold facilitator-free 3/4/5 timing workbooks, cuts, system/human time and invalid runs;
- approved row-level provenance plus voice/asset withdrawal rehearsal;
- map topology/LOS/spawn report;
- cached-line worst-trace repetition report;
- explicit technical/content/soul/repetition failure counts;
- named game-systems, narrative/content and qualified provenance reviewer decisions.

## Handoff acceptance

I9 is accepted only when the immutable test is green, every evidence item exists, no stop condition is open, and the facilitator-free delivery runs meet the frozen 60–90 envelope. It is still not a product-success verdict; R10 owns real-player continuation evidence.
