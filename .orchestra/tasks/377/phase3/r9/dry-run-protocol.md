# R9 facilitator-free dry-run and playtest protocol

Status: predeclared future I9/R10 protocol. No participant session was conducted in R9.

## Purpose and separation of evidence

The protocol answers three different questions and never merges them into one “felt good” verdict:

1. **Delivery/correctness:** does the frozen package reach a terminal consequence safely, in 60–90 minutes, through the real Core/R5/R6 contracts without a human GM?
2. **Content/soul/repetition:** are stakes, NPC goals, choices, Severin's presence and line variation memorable rather than generic/repetitive?
3. **Product/fun:** do real players engage with one another and spontaneously want to schedule continuation?

R9 can define and mechanically rehearse (1). I9 runs facilitator-free dry runs for (1) and internal content review for (2). Only authorized R10 participant sessions can answer (3). Synthetic simulation, author table-read and actual-play media do not prove player fun.

## Freeze packet before any run

Commit one packet before observing results:

- package/schema/rules/core/audio/input hashes and exact build;
- trace scripts, 3/4/5 role selections and declared difficulty;
- clock start/end and timing checkpoints from `timing-and-balance.md`;
- all pass/fail thresholds below;
- expected obligations, routes, endings, cuts and persistent state deltas;
- secret canary set and public serialization targets;
- target browser/room configuration and R5/R6 timing span names;
- observer classification guide and issue IDs;
- consent/retention records for any later real participants (not needed for synthetic actor traces).

Changing any threshold, trace, content, rules or build after a run creates a new packet/version. Results are never silently pooled across versions.

## Roles and no-facilitator rule

- **Players/test actors** may operate only table controls, speak/type as players, choose actions and roll when prompted.
- **Technical operator** may commission, pause/end, adjust volume, cancel stuck generation/audio, reproject the last committed screen or retry the exact unfinished technical stage. The operator cannot suggest a plot choice, play an NPC, reveal a clue, select an enemy tactic, alter HP/DC/dice, trigger a beat manually or use creative override.
- **Observer/logger** records timestamps and classifications but does not speak to players during the clock. Questions wait until the post-run interview.
- **AI/Core** performs all GM/narrator/NPC/adjudication/world actions.

Any creative/operator intervention invalidates the run for facilitator-free acceptance. Preserve the failure and rerun only after a versioned fix.

## Layer A — deterministic automated traces

Run against the actual compiled I9 package and Core, with fake STT/TTS allowed but real serialization/reducers:

| Trace | Required adversarial action | Required result |
|---|---|---|
| A1 canonical | verify package hash, select 4 roles; normal route; successful checks | hash/effect signatures valid; all 12 obligations; success outcome; consequence+hook; 60–90 target minutes |
| A2 alternate clue | decline NPC route; use durable non-NPC route | same mandatory conclusion; distinct causal/reveal ledger; no teleport |
| A3 carrier loss | NPC dies/leaves before clue | durable route remains; absent/dead NPC never speaks |
| A4 off-rail | leave planned location/destroy optional carrier/refuse first hook | authored world reaction/clock; meaningful next choice; explicit loss/mixed allowed; no invisible wall |
| A5 roll failure | fail trap/declared physical roll | conclusion remains obtainable; authored cost/consequence applies once |
| A6 dispute | challenge a wrong and a correct ruling | exact correction commits once; correct ruling gives short safe rule/fact explanation; no vote/admin override |
| A7 loss/death | fail objective and exercise death-save edge | public dice unchanged; death persists; loss/mixed consequence and hook remain |
| A8 3/5 scaling | run each party size and every role combination mechanically | exact roster XP/count/map topology/spawn capacity/rules supported; no missing role mechanic or clue dependency |
| A9 recovery | reconnect/crash after approval, commit, projection and audio enqueue | stored result; no repeated mutation/roll/reveal; safe snapshot; no historical audio replay |
| A10 leakage/withdrawal | inject each private ID/truth/canary into public sources and nonprojected metadata; withdraw one voice/asset | no player/public-narrator/audio/cache leak; private admin/narrator stays scope-minimal; declared fallback/text-only/silence only |

Automation acceptance is zero tolerance for mutation duplication, unsupported mechanics, unsafe bytes, broken references, missing provenance, or unhandled sinks. Timing output from a fake actor is structural evidence only, not human-duration evidence.

## Layer B — cold facilitator-free table read

Use a frozen build with human test actors but no creative facilitator. The first valid packet runs at least:

- one 3-player route using the NPC clue;
- one 4-player route using the durable clue plus a dispute;
- one 5-player route with an off-rail action and boss timeout pressure.

Each actor receives only their final starter card and normal player UI. No one receives graph, timing checkpoints, secret list or expected route. The technical operator uses the admin UI only. The logger records workbook rows using monotonic time.

After the clock, ask separately and in this order:

1. What did your character want/enable? (role legibility)
2. What did the important NPC want, and what did they refuse? (NPC agency)
3. What facts/choices/consequences do you remember? (content)
4. Did the narrator feel distinct? Give a concrete moment. (soul)
5. What repeated too often—line, cadence, UI loop, combat behavior? (repetition)
6. Where were you waiting on technology versus deciding with people? (failure attribution)
7. Would you choose to continue, and would you propose a date? (R10 criterion; record verbatim, do not prompt positively)

## Frozen success criteria

### Technical/content-delivery acceptance for I9

Every valid 3/4/5 dry run must meet all:

- terminal consequence/hook committed between minute 60 and 90;
- all twelve showcase obligations observed, including one important-NPC scene, direction choice, investigation/trap, shared plan, physical declared roll, skirmish, dispute and boss;
- each selected player makes at least one consequential declared choice before the boss;
- zero unsupported-mechanic fallthroughs or freeform mutation;
- zero private canary/secret-ID/private-truth bytes in table, scene, public narrator, subtitle, audio intent, cache or player asset projections; admin and private narrator outputs contain only the exact secret IDs/truth permitted by their declared scope;
- zero creative operator interventions and zero duplicate world mutations/rolls/reveals;
- every used asset/voice/content row approved and hash-valid; expired/withdrawn input fails closed;
- checkpoint cuts fire only as predeclared and never change stored dice/HP secretly;
- at least one adversarial target-policy simulation and actual trace stay within the encounter round/time caps.

Failure is not converted into success by excluding system wait, restarting the clock, changing route, or allowing the operator to “unstick the story.”

### Content/soul/repetition diagnostic bands

These do not certify product success, but they decide whether I9 is ready for R10:

- every actor can name the important NPC's goal or refusal boundary without being shown options;
- at least 3 of 4 canonical-memory prompts (NPC, choice, consequence, hook) are recalled by a majority in the 4-player run;
- a majority cites a concrete Severin reaction rather than “the AI voice/interface”;
- no cached line asset plays more than twice and no adjacent identical line occurs in the worst-case trace;
- no actor reports the same action-card/narration cadence as the dominant negative in two different beat families;
- technical-wait complaints and content complaints are reported independently even when both occur at the same moment.

If these fail, revise content/presentation before adding features. Do not classify generic narration as an STT latency problem or repeated UI waits as “weak story.”

### Product success remains R10-only

The owner criterion is a spontaneous request to continue and readiness to set the next date. Record each participant's exact response and whether a date was proposed. One complete valid session is the minimum evidence; fewer than two lowers confidence as specified by R10. Missing consent, incomplete slice, operator-as-DM or a prompted/leading continuation answer invalidates the product verdict.

## Failure taxonomy

| Class | Examples | Owner/action |
|---|---|---|
| `TECH_INPUT` | PTT/finality/draft/roll parse | R5; typed fallback preserves content run, but voice path fails |
| `TECH_STATE` | duplicate/stale/reconnect/projection | Core/R4/R7; run invalid, no content inference |
| `TECH_AUDIO` | wrong voice, overlap, stuck/cancel, silence | R6/R7; captions preserve state, audible claim fails |
| `CONTENT_REACH` | dead clue, implausible redirect, missing ending | R9/I9; revise graph, not runtime scope |
| `CONTENT_PACE` | late checkpoint, combat overrun, compressed choice | R9/I9; apply/correct cut and objective budget |
| `CONTENT_AGENCY` | cosmetic choice, invisible wall, forced solution | R9/I9; rewrite transitions/pressure |
| `SOUL` | NPC has no recognizable goal; Severin generic | narrative/audio direction; no technical green override |
| `REPETITION` | repeated line/cadence/encounter behavior | content/audio pools/presentation; preserve exact frequency |
| `RULES` | unsupported mechanic or unexplained/corrected dispute failure | Core/rules bundle; stop I9 if required |
| `PROVENANCE` | missing/expired/uncleared row | R8 rights authority; remove/block material |
| `PRODUCT` | no participant continuation intent | R10/owner; blocks feature expansion, not relabeled technical failure |

A single observation may carry multiple classes; never force one root cause prematurely.

## Data/retention

Automated traces contain abstract IDs/canaries only. Human dry-run logs use pseudonyms and timestamps/enum observations; raw room audio/video is not recorded or committed. Final transcripts follow the approved R5 retention policy. Provider/account IDs, raw errors, voices, secret truth and consent instruments stay outside Git in their designated controlled systems.

## Stop rules

Stop package acceptance immediately on any secret leak, unapproved asset/provider call, creative operator intervention, duplicate mutation, required unsupported mechanic, unreachable terminal, missing consequence/hook, or hard stop beyond 90 minutes. Stop audible acceptance on any wrong/uncleared voice or post-cancel playback. Stop product claims until R10 real participant evidence exists.
