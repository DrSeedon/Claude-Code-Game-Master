# R9 timing workbook and encounter envelope

## Frozen slice clock

The slice clock starts when the first selectable hero screen is visibly interactive. Technical commissioning is recorded separately and cannot be hidden by starting the clock later. The target is 75 minutes, valid range 60–90, with at least 5 minutes of unallocated reserve.

| Beat family | Target | Hard cap | Cut/timeout rule |
|---|---:|---:|---|
| hero + Severin selection/onboarding | 6 min | 8 min | never cut; preselection is allowed only in a separately labeled rehearsal |
| important-NPC social scene | 11 | 14 | keep goal/refusal/choice; remove optional color first |
| direction choice | 3 | 5 | never choose for players; present two state-changing routes |
| one investigation/trap route | 8 | 10 | required conclusion becomes an already-authored safe atom only after a supported investigation; risk/cost remains |
| shared plan + physical declared roll | 7 | 9 | never cut or auto-roll; typed fallback may replace STT |
| tactical skirmish | 16 | 20 | objective resolves at a round boundary; no HP/dice fudge |
| authored rules dispute | 4 | 5 | compress explanation to one disclosed rule/fact citation; correction remains idempotent |
| boss/final conflict | 20 | 22 | at round boundary, authored objective state selects success/loss/mixed; no automatic victory |
| persistent consequence + continuation hook | 5 | 6 | never cut; audio may degrade to text |
| **showcase success (NPC/object route)** | **81–82** | not summed—checkpoint rules apply | within 60–90 |
| **completed recovery/pressure/mixed traces** | **79–85** | not summed—checkpoint rules apply | within 60–90; worst case preserves the frozen 5-minute reserve |
| **deliberate premise refusal → loss** | **17** | explicit early terminal | reported separately; never credited as a showcase |

The replacement compiled-state explorer reached 62 states and 25 terminals. Its first compiled run measured 80–89 minutes, exposing that the nominal `reserve_min=6` was false on the worst pressure/timeout trace. The frozen workbook was corrected to a 22-minute boss hard cap, 5-minute aftermath target and explicit 5-minute reserve; the resulting 24 completed non-refusal traces measure 79–85 minutes, plus one explicit 17-minute refusal/loss. It applies clue-route costs, redirect costs/effects, completion predicates and outcome priority; infeasible transition/condition pairings are not counted as paths. The earlier adjacency-only probe's 93-minute topology walk was itself later falsified for ignoring state. Both defects are retained in research history.

The 60-minute lower bound is not permission to add filler. A valid early finish must still satisfy all twelve obligations and persist an ending/hook. If a target trace is below 60, revise pacing/interaction depth; do not add an unrelated branch.

## Checkpoints and cut order

| Elapsed | Required state | Deterministic response if late |
|---:|---|---|
| 32 | investigation conclusion revealed and physical-roll beat armed/complete | remove unentered optional texture; fire the preauthored durable clue route if its world preconditions are true; never reveal private truth directly |
| 50 | boss route armed (party knows the objective and can choose to engage/refuse) | remove remaining optional bridge; advance the visible threat once through a named Core effect |
| 60 | boss/final conflict started, or party has explicitly chosen an authored loss/mixed route | fire the deadline consequence; it changes the world and preserves engage/retreat/alternate-objective choice |
| 78 | boss should be in its final objective phase | stop adding reinforcements/optional dialogue; do not shorten enemy HP invisibly |
| 85 | aftermath started | finish current resolution at the next legal round boundary and select the authored state-derived ending |
| 90 | terminal outcome + consequence + hook committed | hard stop; missing terminal persistence is a failed run, not overtime |

Cut order is fixed: unentered optional texture → optional flavor line/audio → optional alternate complication → compress already-revealed exposition → authored pressure consequence → state-derived round-boundary ending. Never cut hero/narrator selection, social agency, investigation conclusion, physical roll, skirmish, boss objective, dispute handling, persistent consequence or hook.

## Table-read workbook rows

I9 creates one immutable row per trace before running it:

| Field | Meaning |
|---|---|
| `trace_id` / `package_hash` | exact frozen content version |
| `party_size` / `role_ids` / `difficulty` | 3–5 selected roles and declared mode |
| `choice_script` | normal, alternate route, carrier loss, off-rail, refusal, failed roll, dispute, combat loss, death/reconnect variants |
| `beat_id` / `entered_at` / `exited_at` | monotonic observed timestamps |
| `human_deliberation_s` | speaking/planning, separate from system latency |
| `system_wait_s` | draft/model/projection/audio waits, tagged by R5/R6 span IDs |
| `round` / `side` / `actor_actions` | tactical phase count and participation |
| `cut_id` / `triggered_at` | exact predeclared cut, never a post-hoc edit |
| `outcome_id` / `obligations_met` | terminal state and coverage |
| `technical_failures` | transport/state/UI/audio failures only |
| `content_failures` | unclear stakes, dead clue, implausible redirect, weak choice, pacing |
| `soul_repetition_failures` | flat NPC/narrator, repeated line/cadence, technology-first response |

## Selected side-phase contract

For both encounters:

1. One chosen hero makes a physical public `d20 + that hero's initiative modifier`; the world makes one persisted public `d20 + encounter initiative modifier`.
2. Higher total acts first; a tie uses higher static modifier, then the party. Both phases complete, then a round ends.
3. Within a party phase, players choose any eligible unacted hero. Each hero acts once. The world policy selects each eligible enemy once. Mode is locked after the first action.
4. Action/bonus/reaction/movement resources and start/end timing remain Core rules. The scheduler changes order only; it does not create extra actions.
5. The package declares enemy goals and target policy. I9 must simulate both declared policy and an adversarial focus-fire policy; success cannot depend on the AI “being nice.”
6. Classic initiative remains the rules-compatible fallback; R10, not R9 synthetic data, decides whether side phases are fun or should revert.

This preserves one visible initiative decision while acknowledging that individual initiative features are not all equally valuable. Any selected starter feature that becomes nonfunctional under side phases must be replaced with an in-bundle authored feature or force classic fallback; it cannot silently do nothing.

## Encounter/difficulty envelope

Official 2024 encounter guidance gives level-3 per-character budgets of 150 XP low, 225 XP moderate, and 400 XP high [E1]. For the normal MVP slice, use these as **ceilings**, not proof of balance:

| Encounter | 3 PCs | 4 PCs | 5 PCs | Other hard constraints |
|---|---:|---:|---:|---|
| skirmish: low ceiling | 450 | 600 | 750 | target 2 rounds, hard 3; at most PCs count in enemy turns; ≤2 stat-block shapes |
| boss: moderate ceiling | 675 | 900 | 1,125 | target 3 rounds, hard 4; one boss plus ≤floor(PCs/2) auxiliaries; ≤2 shapes |
| hard-mode boss ceiling (not MVP default) | 1,200 | 1,600 | 2,000 | allowed only after actual Core simulation and table evidence; official guidance says high may be lethal |

Story mode uses a low boss ceiling. Normal uses low skirmish + moderate boss. Hard mode may use moderate skirmish + high boss only after it passes separate death/timing gates. Difficulty changes predeclared templates/stats/rosters/objective clocks before play; it never changes a stored die or secretly rescales HP.

Each encounter must have a non-HP objective, a visible failure state and a round-cap resolution. That is the timing control: the skirmish can end when the party holds/escapes/disables its objective, and the boss may retreat/complete an objective/force a mixed result. “Kill every HP pool” is not allowed as the only exit for both encounters.

The two fights share no assumed full rest. If the fixture depends on the synthetic bridge's one 6-HP recovery use per surviving hero, I9 must instantiate it as an explicit curated item/ability, spend its resource through Core, and retest parties without a healer. Otherwise rerun with no bridge recovery.

## Synthetic experiment: predeclared model and result

`r9_probe.py` froze three abstract attrition envelopes (`story`, `normal`, `hard`), two enemy policies (`random`, `focus_lowest`), every combination of 3–5 roles selected from six, and 500 seeded trials per composition/policy/envelope. Total trials were:

- 41 role combinations × 500 × 2 policies × 3 envelopes = **123,000 two-encounter traces**;
- normal cells: 10,000 trials at 3 PCs, 7,500 at 4, and 3,000 at 5 for each policy.

Frozen normal pass bands were 70–98% aggregate win, ≤5% TPK, 10–70% any-down, ≤5% boss alpha-kill before retaliation, ≤15% world-first down, median combat time ≥18 minutes and p90 ≤43 minutes for every party-size/policy cell.

### Recorded normal-envelope results

| policy / PCs | win | worst composition | TPK | death | any down | world-first down | median / p90 estimated combat min |
|---|---:|---:|---:|---:|---:|---:|---:|
| random / 3 | 99.05% | 97.2% | 0.69% | 1.33% | 10.34% | 0.21% | 37.50 / 50.55 |
| random / 4 | 99.96% | 99.8% | 0.00% | 0.31% | 4.65% | 0.15% | 49.87 / 58.97 |
| random / 5 | 99.97% | 99.8% | 0.03% | 0.43% | 6.87% | 0.37% | 55.77 / 68.73 |
| focus / 3 | 93.41% | 80.6% | 3.95% | 14.68% | 57.37% | 4.88% | 41.55 / 55.20 |
| focus / 4 | 97.37% | 94.2% | 0.43% | 14.11% | 59.95% | 9.93% | 52.80 / 69.80 |
| focus / 5 | 97.40% | 95.4% | 0.47% | 18.87% | 80.10% | 24.53% | 62.25 / 81.70 |

Boss alpha-kill was 0 in all normal cells. The normal envelope **failed** the frozen win/down/timing/world-first-down bands. The gentler story envelope controlled focus-fire lethality (0–0.08% TPK; 0.16–1.55% death across sizes) but five-player p90 remained 52.77 minutes. The hard envelope was clearly outside the slice envelope under focus fire (15.08–29.30% TPK and 64.20–101.75 p90 minutes).

### What follows—and what does not

- **Supported:** a stat/HP-only two-fight design is not enough; explicit objective/round caps are required, and declared enemy target policy materially changes results.
- **Supported:** the proposed hard envelope must not be used for I9 default content.
- **Not supported:** that the story envelope is fun, that normal is actually easy/hard, that players take 55 seconds/action, or that the abstract role stats match the future RulesetBundle.
- **Not supported:** official XP budgets compensate for side phases. They are a starting ceiling from classic encounter guidance.

The experiment uses no map, LOS, real spells, actual Core resolver, human decisions, room latency or audio. It calibrates the evidence as **UNCERTAIN for balance and fun**, **CONFIRMED for the deterministic model's internal outcomes**, and **REFUTED for the initial normal-envelope claim under its own frozen bands**.

## I9 balance gate

Before a production encounter row is accepted:

1. use actual pinned hero and enemy templates, exact map, objectives, Core dice/resources/effects and selected side-phase scheduler;
2. rerun every legal 3–5-player role combination under declared and adversarial target policies with fixed seeds;
3. freeze outcome/time/alpha/death bands before the run and report every cell, including failures;
4. prove target 2+3 rounds and hard 3+4 round caps select authored objective outcomes without hidden stat changes;
5. table-read all 3/4/5 sizes; simulation never substitutes for real timing or fun;
6. fail I9 if no envelope meets correctness, 90-minute timing and provenance simultaneously; do not add mechanics or weaken the test.

## Sources

- **[E1] Primary rules guidance:** Wizards of the Coast, [2024 Basic Rules: DM's Toolbox, Combat Encounter Difficulty](https://www.dndbeyond.com/sources/dnd/br-2024/dms-toolbox), opened 2026-08-16. It specifies level-3 budgets of 150/225/400 XP per character and warns about many/powerful creatures and excessive stat-block variety.
- **[E2] Primary licensed rules document:** Wizards of the Coast, [SRD 5.2.1](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf), opened 2026-08-16. The future bundle uses only this version and its required attribution.
- **[M1] Direct synthetic measurement:** `r9_probe.py` and `probe-results.json`, run 2026-08-16 with the command recorded in `research.md`.
