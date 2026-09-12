# R9 I9 acceptance templates

These are fill-in acceptance records. They specify evidence and limits; they are not final names, biographies, dialogue, portraits, maps, stat blocks or campaign prose.

## Six level-3 starter-role templates

All six must pin exact `srd-5.2.1-mvp-1` rules references, use only mechanics covered by Core M4, include a cleared portrait/token row, and pass one golden test per visible feature. Final numbers/equipment/spells are authored in I9 and resimulated together.

### `guardian`

| Field | Acceptance value |
|---|---|
| fantasy/role | durable front line that makes ally protection legible |
| strengths | high visible defense; self-recovery or one burst turn |
| weaknesses | limited reach/control; burst resource is scarce |
| tactical hooks | hold a choke point; choose whether to protect or burst; at least one map objective rewards durability without requiring it |
| social hooks | duty/leadership prompt that invites another player's opinion; no authored answer |
| onboarding | `low`; 2–4 always-visible actions and ≤2 conditional choices; first-turn suggestion names move + basic attack + one signature option |
| rejection | passive “tank” whose optimal turn is always identical; feature requires unsupported marking/aggro mechanic |

### `fury`

| Field | Acceptance value |
|---|---|
| fantasy/role | high-pressure melee risk/reward striker |
| strengths | reliable melee damage; declared resilience window |
| weaknesses | exposed positioning/ranged limitation; resource choice has visible cost |
| tactical hooks | opt into risk for advantage/damage; decide when to commit limited state |
| social hooks | instinct/directness prompt that can conflict with caution without forcing conflict |
| onboarding | `low`; 2–4 always-visible and ≤2 conditional choices; risk consequence displayed before approval |
| rejection | hidden damage resistance; rage/duration cannot be expressed by pinned resources/effects |

### `shadow`

| Field | Acceptance value |
|---|---|
| fantasy/role | mobile scout and positional single-target striker |
| strengths | investigation/stealth competence; movement/bonus-action flexibility |
| weaknesses | lower durability; peak damage needs a visible eligibility condition |
| tactical hooks | choose position/advantage setup; at least one clue route recognizes skill without making the mandatory conclusion roll-gated |
| social hooks | suspicion/underworld-access prompt with an explicit refusal boundary |
| onboarding | `medium`; ≤4 always-visible and ≤3 conditional choices; UI explains why signature damage is/isn't eligible |
| rejection | freeform hiding with no LOS rule; mandatory clue available only to this role |

### `beacon`

| Field | Acceptance value |
|---|---|
| fantasy/role | healer/support who can stabilize a bad round |
| strengths | healing/downed recovery; one visible concentration/support choice |
| weaknesses | limited slots/uses; concentration opportunity cost |
| tactical hooks | heal now versus advance objective; support another player's planned action |
| social hooks | empathy/conviction prompt that elicits NPC motive; no guaranteed persuasion outcome |
| onboarding | `medium`; curated prepared list only, ≤5 always-visible and ≤3 conditional choices; exact slot/concentration state displayed |
| rejection | full spell list; healing assumed by encounter balance when this role may be unselected |

### `arcanist`

| Field | Acceptance value |
|---|---|
| fantasy/role | ranged area/control specialist |
| strengths | area choice and range; one visible terrain/effect interaction |
| weaknesses | low durability; slots/concentration constrain repetition |
| tactical hooks | place one authored area template; distinguish damage from control objective |
| social hooks | knowledge/curiosity prompt that offers context, never the sole core clue |
| onboarding | `medium`; curated prepared list, ≤5 visible and ≤3 conditional choices; preview exact cells/targets before approval |
| rejection | spell/effect lacks a golden Core fixture; arbitrary terrain patch or model-authored damage |

### `voice`

| Field | Acceptance value |
|---|---|
| fantasy/role | social/support generalist who amplifies allies |
| strengths | social breadth; finite ally-support resource/reaction |
| weaknesses | lower direct damage; support timing requires attention |
| tactical hooks | spend support before/after a declared trigger exactly as pinned rules allow; help execute a shared plan |
| social hooks | negotiation/performance prompt tied to an NPC goal, with honest refusal/failure consequences |
| onboarding | `medium`; ≤4 visible and ≤3 conditional choices; reactions are opt-in with a short timeout and never silently spent |
| rejection | “face” role makes other players spectators; support requires unavailable private channel or unsupported interruption |

### Cross-role acceptance

- exactly six unique roles, all level 3; party sizes 3–5 may choose any distinct subset;
- every role has at least one useful action in social/investigation and both combats, but no required clue/ending depends on one role;
- first-turn card fits one screen and identifies fantasy, 2 strengths, 1 weakness and 3 suggested actions;
- one player decision per hero is recorded before the boss in every showcase dry run;
- no role has more than 5 always-visible or 4 conditional tactical choices in the MVP UI;
- no role invalidates side phases; any initiative-dependent feature has a tested side-phase interpretation and classic fallback;
- provenance rows cover text, rules excerpts/data, name, portrait, token and any generated inputs separately.

## Map acceptance row

Required fields/evidence:

| Category | Required |
|---|---|
| identity | `map_id`, semantic version, art asset ID/hash, provenance ID |
| grid | width/height 8–64; 5 feet/cell; origin/orientation; pixel-to-cell transform |
| authority layers | explicit blocked/opaque cells, light rectangles, spawn anchors and objective cells; pixels/path names carry no rules |
| spawns | exact 3/4/5 party anchors and every enemy variant; no overlap/blocker/out-of-bounds |
| reachability | golden route from each party spawn to each required objective under every authored terrain state; negative blocked-corner fixtures |
| visibility | symmetric LOS fixtures where required; cover boundaries; unrevealed art/metadata absent from player projection |
| enemy closure | each roster item resolves to a closed XP/footprint/HP/AC/initiative/actions/attack/damage/mechanics/spawn template; XP sum and actor count fit budget and anchor capacity |
| timing | furthest required route does not consume an unintended extra round at each party size |
| presentation | table art, scene image and token refs are distinct; one-screen fallback declared |
| provenance | author/source/master/inputs/hash/grant/uses/terms/attribution/reviewer all approved |

Reject a visually finished map if pixels are the only collision/LOS source, spawn variants are improvised at runtime, or a hidden label/layer leaks through client bytes.

## NPC acceptance row

Required:

- stable `entity_id`, important/generic class and initial Core lifecycle;
- 1–4 prioritized goals, desired states, refusal boundaries and pressure responses;
- public facade fact, exact known secret IDs and minimum adjudicator scopes;
- at least two response strategies for a supported player approach; these are policies, not scripted dialogue;
- clue-carrier role and the durable alternate if this NPC dies/leaves/refuses;
- deterministic state transitions and consequence IDs;
- exact logical voice key, cleared fallback or `text_only`;
- public portrait/token/scene refs and separate approved provenance rows;
- test: dead/absent NPC cannot speak or satisfy present-carrier requirements, while the mandatory conclusion remains reachable.

## Voice acceptance row

Use the full R6 `voice_manifest`; minimum content-side fields are `voice_key`, character/archetype scope, locale, exact fallback, provenance record and status. Admission additionally requires:

- signed rights/consent for recording, voice-model creation, synthesis, editing, caching, distribution and public performance;
- provider/account/plan/terms snapshot, territory, start/end, retention and withdrawal process;
- server-only provider voice reference; no raw ID in content/browser/model input;
- pronunciation/emotion audition against only cleared, non-secret lines;
- withdrawal rehearsal cancels generation/playback, finds linked outputs and activates only the declared cleared fallback/text-only;
- important NPCs never silently fall back to a random library voice; Severin always falls back to text-only.

## Combat-line pool acceptance row

Each pool key is `(voice_key, event_key, locale, ruleset_id, script_version)` and includes only approved content-addressed cached masters.

Required event coverage is at least `hit`, `miss`, `critical`, `death`, `spell`, player-phase start/end and world-phase start/end where the encounter emits them. I9 may merge event keys only if Core emits the merged key deterministically.

Acceptance oracle:

1. replay the worst-case bounded encounter trace from the Core simulator;
2. durable shuffle-bag selection gives every approved asset once before reuse;
3. no adjacent identical line, and no asset plays more than twice in that trace;
4. pool size is therefore `max(3, ceil(worst_case_event_uses / 2))`, capped by changing event cadence—not by exceeding six variants per key without narrative-lead approval;
5. each line is one short reaction, contains no rules claim or hidden fact, and does not block the next legal action;
6. normal combat performs zero live TTS calls; a missing/withdrawn pool is text-only;
7. recording→script and recording→voice relationship rows close; script, voice identity, generated/recorded master and transformations are individually approved and checksummed.

## Music/SFX acceptance row

- key by state/event, never by freeform AI text;
- music states are only `silence/exploration/danger/conversation/combat/boss/victory/loss`;
- composition and master are separate rows joined by a typed master→work relationship; loop/stem/edit/public-performance/distribution rights are explicit;
- SFX row includes original library/recording, edit permission, source/master hash and attribution;
- exact loudness/peak/format limits are selected by R6/I8 acoustic testing; R9 does not invent them;
- missing/withdrawn asset means silence, not filesystem/provider search;
- target-room mix must pass R6 G9 before launch.

## Generic asset acceptance row

Every binary/text asset joins:

`asset_id → exact path → sha256 → provenance_id → source work/input rows → rights/grant → reviewer decision`.

The build rejects unknown extensions, hash drift, unapproved/expired/withdrawn rows, blank/`unknown`/`UNASSIGNED` evidence, inaccessible terms snapshots, and any generated asset lacking provider/account/model/time/prompt-input/reference provenance. Concept references never become production assets by redrawing or prompting “in the style of.”

## Row-level provenance checklist

| Field | Fail-closed question |
|---|---|
| material identity | exact type/title/path/blob/hash/version? |
| origin | original, commissioned, CC0, CC BY, stock, generated or exact SRD 5.2.1 source? |
| authorship/ownership | named author/provider and written rights-owner/assignment evidence—not Git metadata alone? |
| license/grant | valid SPDX expression or exact custom `LicenseRef`; commercial hosted, modification, distribution/sublicense/public-performance scope as applicable? |
| dependency/input closure | every font/model/sample/reference/prompt/source work linked; recording→script/voice and music-master→work predicates close and withdrawal propagates? |
| time/place | creation/generation date, territory, term/expiry and terms snapshot? |
| permitted uses | modify, hosted runtime, distribution, cache, synthesis, public performance and marketing separately stated? |
| attribution | title/author/source/license plus modification notice where applicable; exact SRD 5.2.1 statement included? |
| privacy/personality | voice/likeness consent, enrollment sample retention/deletion and withdrawal path? |
| build/runtime | checksum matches, status approved, route fails closed on expiry/withdrawal? |
| review | reviewer belongs to the frozen qualified set; decision/evaluation date/evidence location present? |

First-party code reuse permission does not answer any creative-content, third-party code, adventure text, map, voice, music, SFX, font, model input or provider-output row. Closed adventures and show transcripts remain `AVOID_LITERAL`; structural study is documented by citation only.
