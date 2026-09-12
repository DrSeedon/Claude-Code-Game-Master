# #377 — canonical implementation plan for the AI-table MVP

**Status:** Phase 2 planning only; implementation is not authorized by this document.  
**Canonical product source:** `docs/tasks/377/mvp-product-spec.ru.md`.  
**Accepted technical inputs:** `docs/tasks/377/research.md` and the merged Phase 3 `core`, `r4`, `r5`, `r6`, `r7`, `r8`, and `r9` packages.  
**Superseded baseline:** `docs/tasks/377/plan.md`. Its useful evidence is retained here, but its independent R1/R2/R3 workstreams are replaced by the reviewed Unified Core contract.

This plan authorizes no repository creation, product code, provider call, asset purchase, VPS change, production change, or participant session. Each such action starts only under the ticket and external gate named below.

## 1. Delivery outcome and fixed scope

The MVP is one finished 60–90-minute, 3–5-player physical-room game with six selectable level-3 heroes, no human GM, one shared push-to-talk microphone, physical player dice, public server-generated enemy dice, a shared 2D square-grid table, a separate cinematic scene display, and an operational admin display. One remote VPS is authoritative. Standard and unusual actions converge on one typed deterministic kernel; AI may propose a plan but cannot mutate state.

The implementation ends only after an isolated remote-VPS staging rehearsal and a consented R10 room playtest. Automated green checks are technical evidence, not a balance, fun, legal-clearance, latency, cost, provider-quality, or product-success claim.

The MVP explicitly forbids camera/CV or miniature tracking, 3D, random map generation, a full character builder, cross-setting character persistence, commerce/pricing/franchise workflows, offline/local authority, generative music, and a second master personality. None may become a dependency, placeholder subsystem, or “temporary” abstraction in the tickets below.

## 2. Concise decision ledger

| ID | Immutable decision for this delivery | Evidence / consequence |
|---|---|---|
| D1 | One remote-authoritative `RoomRunAggregate` is the only mutable story, tactical, roll, coordinator, and presentation-intent authority. | Unified Core. Narrative/tactical modules are pure; no separately committed story, board, roll, or projection authority. |
| D2 | Persistence is one SQLite authority using transactional current state, `(room_id, command_id)` dedupe/results, append-only non-canonical audit/domain rows, and transactional projection/audio outboxes. | R4. World/result/stage/audit/outbox commit together; provider/browser I/O stays outside the transaction. |
| D3 | Exact duplicate lookup and digest comparison precede current dynamic authorization/version/stage checks inside the command transaction; static session/surface admission precedes both. | Core + R4. Stored external results are player-safe summaries; same ID/different digest is a zero-mutation conflict. |
| D4 | Standard deterministic intents and unusual AI candidate plans produce one closed `ResolutionPlan`; one kernel validates the whole detached plan and applies all-or-nothing reducers. | Unified Core. No JSON Patch, arbitrary script/expression, Bash, SQL, filesystem, network, or generic tool escape. |
| D5 | `CampaignDefinition` v2 and `RulesetBundle(srd-5.2.1-mvp-1)` are immutable, content-addressed inputs pinned by each run. | Core + R9. No “latest,” mixed 5.1/5.2.1 behavior, or un-hashed timing/asset/story side files. |
| D6 | Players roll physical dice only against a persisted `PendingRoll`; confirmation is versioned/idempotent. The server rolls for enemies/world through injected RNG and persists the public face/modifier/total/result with its effect. | Product spec + Core/R5. No number in ordinary speech becomes a roll and no retry rerolls the world. |
| D7 | Side phases and classic initiative are schedulers over the same state and commands; mode locks after the first encounter action. | Core. Side phases remain an experiment, not a balance claim; classic is the tested fallback. |
| D8 | One-mic input is per-character press-and-hold PTT, browser → VPS proxy → one STT connection per accepted capture. PTT release is the boundary; partial/abnormal input produces no candidate. Typed input is always available. | R5. Wake word and diarization are outside MVP. No real speech is sent before consent/account/privacy gates. |
| D9 | Output is caption-first hybrid audio: cleared cached combat lines/SFX/state-selected music; dynamic disclosed story lines through a server adapter; one server-leased browser player. | R6. Provider close and browser clear are independent. Strict `audio_fence` control is applied before any higher-fence media; reconnect never replays speech/SFX. |
| D10 | Table, scene, and admin are real distinct browser applications receiving positive full projections from one projection batch; composite is a table-authority two-pane fallback. | R7 + Core. Cursor advances only after schema/reducer/render success. Admin is operational only and receives no world truth. |
| D11 | Production content is one original typed authored package. Every mandatory clue has two eligible routes including a durable non-NPC route; every terminal persists a consequence and continuation hook. | R9. AI improvises expression and eligible route choice, never authored truth. |
| D12 | A new organization-owned private repository starts with clean history. First-party literal DnD/Orchestra reuse is owner-authorized, but every literal row still requires exact blob/range, contributor closure, dependency/SBOM closure, fit, notices, and exclusion scans. | Later owner authorization supersedes only R8’s missing-first-party-grant premise. It does not clear other contributors, dependencies, assets, SRD/trademarks, voices, provider output, or personal data. |
| D13 | SRD 5.2.1 only, with exact official attribution and separate branding review. | Core/R8. The plan makes no legal-clearance claim; qualified provenance review remains an admission gate. |

Research evidence is calibrated honestly: Core, R4, R5, and R8 received completed Sol verdicts; R6 stopped after its prose-round ceiling with a self-verified strict-control-barrier fix; R7 exhausted reviewer attempts without a verdict; R9 stopped at its prose-round ceiling and then self-verified two state-integrity fixes. I6, I1/I2, and I7/I8 therefore carry explicit independent implementation-review and real-browser/Core-shaped falsification gates. Prior synthetic evidence is not substituted for them.

## 3. Future repository, stack, and boundaries

### 3.1 Chosen stack

- Python 3.12 application managed by `uv`; FastAPI/ASGI for HTTPS and WebSockets; Pydantic/JSON Schema for closed external records; standard `sqlite3` behind a single-writer repository boundary, WAL, foreign keys, and full-sync settings. Dependencies are selected and pinned afresh only after I0 admission.
- Browser-native TypeScript ES modules built by Vite; semantic HTML/CSS for cards/admin/scene, Canvas 2D for the square-grid board, Pointer Events for mouse/touch/pen, Web Audio + AudioWorklet for bounded playback/capture. No frontend framework is required for the three bounded applications.
- `pytest` for unit/integration/fault tests; Playwright-controlled Chromium plus the other target browsers selected by the staging owner for real DOM/canvas/audio/reconnect tests. The plan does not claim browser support before I12 records it.
- One server process owns room writes in MVP. Provider calls and outbox delivery are asynchronous tasks within the application process and use durable attempt/task rows before work. Multi-node/multi-writer operation is outside MVP.
- One OCI application image plus an isolated staging database/asset volume is the delivery artifact. The approved VPS owner chooses the installed compatible container runner and TLS reverse proxy only after I12 records the real host baseline; no current production service/configuration is imported.

### 3.2 Concrete future tree

```text
pyproject.toml                 # Python/runtime/test dependencies, selected fresh
uv.lock
package.json                  # TypeScript/Vite/Playwright build dependencies, selected fresh
package-lock.json
contracts/
  command.schema.json
  core.schema.json
  projection.schema.json
  speech.schema.json
  audio.schema.json
server/ai_table/
  domain/aggregate.py         # RoomRunAggregate and immutable pinned identities
  domain/commands.py          # closed intents/envelopes/results
  domain/operations.py        # closed ResolutionPlan operation algebra
  domain/rules/               # srd-5.2.1-mvp-1 pure resolvers and two schedulers
  domain/narrative.py         # pure NarrativePolicy and ending/consequence evaluation
  application/admission.py    # static session/capability then R4 admission order
  application/coordinator.py  # lifecycle, attempts, approval, recovery actions
  application/kernel.py       # plan validate/apply; no I/O
  application/projections.py  # table/scene/admin + internal PresentationBundle
  application/content.py      # CampaignDefinition v2 compile/lint/hash
  persistence/sqlite.py       # RoomRunRepository and migrations
  adapters/http.py            # commissioning, no-store bootstrap, health
  adapters/ws.py              # projection/control/overlay transport
  adapters/stt.py             # R5 proxy port + fake/Deepgram adapters
  adapters/adjudicator.py     # typed private candidate-plan port + fake/real adapter
  adapters/narrator.py        # safe PresentationBundle-only port
  adapters/tts.py             # R6 fake/ElevenLabs adapters
  presentation/audio.py       # router, attempts, cache, fences, lease integration
web/src/
  shared/                     # closed transport, reducers, reconnect, session, audio graph
  table/                      # board, hero/PTT/action card/roll/overlay UI
  scene/                      # art, portrait, subtitle, activity/result UI
  admin/                      # lifecycle/health/volume/cancel/reproject/retry UI
  composite/                  # atomic table+scene layout, no new authority
campaigns/mvp/                # I9 authored records and compiled definition
assets/cleared/               # I10 approved content-addressed binaries only
assets/manifests/             # maps/portraits/voices/cache/music/SFX manifests
provenance/                   # row gate, relationships, notices, SBOM, decisions
deploy/staging/               # OCI recipe, isolated config template, runbook, rollback
tests/{delivery,unit,integration,browser,content,security,e2e}/
tools/{provenance_gate.py,content_lint.py,verify_ticket.py}
```

No file discovery or filename convention is authority. Runtime references use typed IDs and hashes. Provider IDs, keys, secret truth, raw transcripts, and source asset receipts remain server-side or in their controlled evidence system, never browser payloads.

### 3.3 Load-bearing interfaces

```python
class RoomRunRepository(Protocol):
    def transact(self, room_id: RoomId, command_id: CommandId,
                 request_digest: Digest,
                 decide: Callable[[RoomRunSnapshot], TransactionDecision]) -> CommandResult: ...
    def load_committed(self, room_id: RoomId, aggregate_version: int) -> RoomRunSnapshot: ...

class GameKernel(Protocol):
    def plan_standard(self, snapshot: RoomRunSnapshot, intent: StandardIntent) -> ResolutionPlan: ...
    def validate(self, snapshot: RoomRunSnapshot, plan: ResolutionPlan,
                 definition: CampaignDefinitionV2, rules: RulesetBundle) -> ValidatedPlan: ...
    def apply(self, detached: RoomRunAggregate, plan: ValidatedPlan) -> KernelOutcome: ...

class PrivateAdjudicator(Protocol):
    async def propose(self, attempt: AdjudicationAttempt,
                      context: ScopedPrivateContext,
                      operations: ClosedOperationSchema) -> ResolutionPlan: ...

class ProjectionPort(Protocol):
    def build_family(self, snapshot: RoomRunSnapshot) -> ProjectionFamily: ...
    def build_presentation(self, snapshot: RoomRunSnapshot) -> PresentationBundle: ...

class ProjectionDeliveryPort(Protocol):
    def acknowledge(self, cursor: ProjectionConsumerCursor,
                    rendered: ProjectionEventId) -> CursorResult: ...

class SpeechProvider(Protocol):
    async def open_capture(self, admitted: CaptureAttempt) -> SpeechStream: ...

class NarratorProvider(Protocol):
    async def render(self, presentation: PresentationBundle) -> SafeNarrationLine: ...

class TtsProvider(Protocol):
    async def generate(self, attempt: SpeechLineAttempt) -> AsyncIterator[AudioChunk]: ...
    async def close_context(self, context_id: ContextId) -> None: ...
```

`TransactionDecision` contains the next aggregate, immutable safe result, audit/domain rows, and outbox tasks. `RoomRunRepository.transact` is the only persistence path for game transitions. `GameKernel`, `NarrativePolicy`, rules resolvers, projection builders, and content compiler contain no database/provider/browser I/O.

Command handling is fixed in this order:

1. TLS/session/origin/CSRF or one-time WS-ticket, size/rate, surface and coarse capability checks bind authority from server state; authority-looking client fields reject.
2. Begin one database transaction and look up `(room_id, command_id)`.
3. Exact digest returns the byte-equivalent stored safe result; changed digest returns conflict.
4. A new ID checks dynamic actor/control, aggregate/draft/plan/attempt/pending-roll versions, stage, and nonce.
5. Resolve the immutable approved plan; revalidate every operation against one detached aggregate and pinned hashes.
6. Apply all reducers, public world roll, consequences/endings, and presentation intent to the detached aggregate.
7. Atomically store aggregate/result/mutation ledger/audit+domain rows/projection task; acknowledge only after commit.
8. Projection worker builds one same-version positive family. Player projection failure keeps the last safe family and emits only a safe admin error.
9. Every successful visible render acknowledges and advances only its own durable `(room_id, surface, consumer_id, schema_version, reducer_version)` cursor. A table/composite table acknowledgement cannot advance scene, admin, or any other consumer cursor; a failed consumer therefore receives its own missed snapshot on reconnect.
10. The designated table/composite table acknowledgement separately satisfies the presentation gate and may enqueue post-commit audio work. Projection-cursor advancement does not grant audio authority: delivery still requires the current playback lease and `audio_fence`, and audio can never call the kernel.

## 4. Oracle, review, and change protocol for every ticket

I0 provisioning is allowed to create an empty remote repository, but it is not product implementation. Its first root commit is the I0 oracle/scaffold only. For I0 and every later ticket:

1. Commit the named test and minimal importable interfaces before implementation.
2. Run the exact RED command. It must collect and exit non-zero on the named missing behavior, not on import/configuration failure.
3. An independent reviewer records the command, output, failing assertion, and correspondence to the ticket AC. The oracle, fixtures, helpers, config, and selection remain immutable for that implementation attempt.
4. Implement in a separate commit; run the named delivery command and affected regression/security/browser checks.
5. If the oracle is wrong, stop the attempt. Replace it only in a new oracle-only commit after independent review and a fresh observed RED; do not edit/skip/xfail/weaken it inside the attempt.
6. Apply the then-current `codex-debate` route using recorded changed files/consumers, author runtime metadata, exact AC, named command/output, risk floor, and independence evidence. Security, persistence, protocol, migration, and shared-delivery work has a Sol floor regardless of size. Prior research reviews do not certify future code.
7. Tag the accepted commit and retain the previous immutable deploy artifact. Schema migration rollback restores the pre-migration backup only if no newer world commit exists; never overwrite newer authoritative state with an old snapshot.

All future commands below deliberately use an absolute private-project path and an isolated `uv` environment:

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT \
  uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q <named-node>
```

## 5. Integrated dependency graph, parallel work, and serial spine

```text
I0 private repo + executable row gate
  └─ I1 durable text turn + actual table/scene/admin browsers
       ├─ I2 one-kernel board: standard + unusual
       │    ├─ I3 SRD tranche A: core rules + guardian/fury/shadow
       │    │    ├─ I4 SRD tranche B: beacon/arcanist/voice + bundle closure
       │    │    │    └─ I8 Core-shaped encounter calibration
       │    │    └─ I5 one-mic PTT + physical roll
       │    └─ I7 CampaignDefinition v2 compiler + synthetic authored vertical
       │         └───────────────────────┘
       └─ I6 strict audio plane + real browser control barrier

I4 + I7 + I8 ──> I9 original campaign/heroes/maps/encounter records
I0 + I6 + I9 ──> I10 cleared production art/voices/cache/music/SFX
I5 + I6 + I9 + I10 ──> I11 integrated 60–90-minute facilitator-free slice
I11 + staging/provider/consent authorities ──> I12 isolated remote-VPS room staging
I12 ──> R10 consented physical-room playtest and separate verdicts
```

Safe parallelism, assuming file ownership is split as named:

- After I1, I2 and I6 can run in parallel: kernel/board files and audio/browser-player files do not overlap.
- After I2, I3 and I7 can run in parallel: rules files and content compiler/narrative files are distinct; their shared schemas are frozen by I2 and changed only through a reviewed compatibility ticket.
- I5 may run after I3 while I4 and I7 continue; it consumes the pending-roll interface without editing the rules bundle.
- I9 content and I10 binaries/manifests remain separate until I11. A logical reference is not asset admission.

Creative sourcing/contract preparation may start after I6/I7 under I0 controls, but I10 implementation acceptance waits for I9's frozen briefs and logical IDs. No asset worker edits runtime code or authored truth.

No duration estimate exists, so “critical path” here means the minimum serial dependency-depth spine, not a calendar promise:

`I0 → I1 → I2 → I3 → I4 → I8 → I9 → I10 → I11 → I12 → R10`.

I5, I6, I7, and I10 are still mandatory; they run off the spine and must join before I11. If any parallel owner needs a shared contract file, that change is serialized through the upstream contract owner rather than merged concurrently.

## 6. Implementation and experiment tickets

### I0 — create the private repository and executable admission gate

- **Owner:** repository/security lead; qualified IP/legal reviewer owns row decisions; organization owner owns host configuration.
- **Depends on:** explicit implementation approval; named destination legal entity, organization, bootstrap administrator, and qualified reviewers. No code ticket precedes I0.
- **Outcome:** create a new empty organization-owned private repository; make one exact-hash/time-bounded bootstrap push containing only fresh scaffolding, the immutable I0 oracle, and gate interface; revoke bootstrap authority; implement an executable row-level provenance/reuse/dependency/secret gate before any product-code push.
- **Future files/symbols:** `provenance/policy.json`, `provenance/materials.tsv`, `provenance/relationships.tsv`, `provenance/dependencies.cdx.json`, `provenance/notices/`, `tools/provenance_gate.py::{verify_tree,verify_row,verify_dependency_closure}`, `.gitignore`, `CODEOWNERS`, `tests/delivery/test_i0_repo_boundary.py`.
- **Inputs:** R8 two-gate repo baseline/threat model; Core reuse matrix; owner authorization for owner-controlled first-party DnD/Orchestra expression. Every literal candidate records exact repository/commit/blob/range/hash, all authors, grant coverage per author, dependency/data/fixture closure, intended hosted use, notices, modifications, destination test, and reviewer decision. Assets, voices, SRD, branding, provider output, and participant data use separate rows and are never inferred from code authorization.
- **RED oracle committed first:** named test collects against an importable `NOT_IMPLEMENTED` gate with one fully closed synthetic owner-authorized positive row plus an incomplete owner-authorized row, a mixed-contributor row, an uncleared dependency, an SRD row without attribution, and a secret/campaign blob. The observed RED must be the closed positive row not being admitted while every incomplete/forbidden row remains rejected; a deny-all implementation cannot satisfy the oracle.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/delivery/test_i0_repo_boundary.py::test_i0_private_repo_and_row_gate_fail_closed`.
- **Measurable AC:** remote API proves private organization ownership and the allowlisted principals; bootstrap authority is revoked; protected-branch/required-review/secret-scan negative rehearsals pass; fresh SBOM/lock selection is recorded; the gate rejects every incomplete negative row and accepts only a fully synthetic closed row; repository object scan contains no DnD/Orchestra/campaign/secret/DB/audio/concept-image blob unless an accepted exact row names it; clean status and restore evidence are recorded.
- **Failure/rollback:** before product code, archive evidence and delete/recreate the empty target if privacy/history/host policy is wrong; never “clean” a contaminated history. Revoke credentials and rotate any exposed secret. The new repository remains recoverable from the first off-provider mirror.
- **Security/privacy/IP boundary:** no product source, existing test, campaign state, provider profile/key, speech, database, deploy config, or binary enters the bootstrap. First-party authorization does not waive contributor, dependency, asset, SRD, trademark, privacy, retention, or notice checks.
- **Stop/falsification:** unknown entity/ownership, non-private visibility, unexpected principal, missing reviewer/assignment evidence, unavailable non-bypassable scanning, incomplete literal row, failed mirror/restore, or any prohibited object stops before the first product-code push.

### I1 — durable text turn through actual table, scene, and admin browsers

- **Owner:** backend/reliability lead; browser projection lead accepts rendering/capabilities.
- **Depends on:** I0.
- **Outcome:** one typed text intent travels through session admission, versioned action card, approval, a minimal `advance_clock` kernel plan, one SQLite commit, same-version projection family, and three real browser applications. Duplicate approval/restart resumes delivery only.
- **Future files/symbols:** `domain/aggregate.py::RoomRunAggregate`, `application/admission.py::CommandAdmission`, `application/coordinator.py::TurnCoordinator`, `persistence/sqlite.py::SqliteRoomRunRepository`, `application/projections.py::build_projection_family`, `adapters/{http,ws}.py`, `web/src/{table,scene,admin,composite}/`, `tests/integration/test_i1_text_room.py`, `tests/browser/test_i1_three_surfaces.py`.
- **Inputs:** R4 current-state/dedupe/outbox state machine; Core admission order; R7 positive projections/capabilities/reconnect; R8 session/origin/replay threat cases. Fake model/narrator only.
- **RED oracle committed first:** crash injection at receive/draft/approve/execution/commit/outbox/ack; exact and conflicting duplicates; wrong surface/cross-room/expired ticket; render exception; secret canary; three Playwright pages and composite atomic pairing. First failure is one duplicate/restart causing other than one world mutation and one stored result.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/integration/test_i1_text_room.py::test_i1_duplicate_approve_restart_three_real_surfaces`.
- **Measurable AC:** zero world revision before approval; exact duplicate returns identical safe result; changed digest conflicts; crash-before commit has zero effect; crash-after commit never calls the kernel; table shows card/approve and public clock result, scene shows public result/activity, admin shows only stage/health/recovery; all same-batch versions render; each table/scene/admin/composite consumer advances only its own durable `(room, surface, consumer_id, schema, reducer)` cursor after successful render; a table acknowledgement leaves a failed scene/admin cursor unchanged and that consumer receives its missed snapshot on reconnect; scene/admin cannot approve; no canary/private plan/transcript bytes reach any browser.
- **Failure/rollback:** migration has forward check and pre-migration backup; application rollback uses the previous image against a compatible schema. Projection failure retains last safe UI and repair state; it never rolls back the committed world.
- **Security/privacy/IP boundary:** Secure/HttpOnly/SameSite session, exact Origin, CSRF/single-use non-URL WS ticket, no-store bootstrap/projections, server-owned room/role/consumer/actors, no secrets in admin. Synthetic content only.
- **Stop/falsification:** separate world store, ack-before-commit, cursor-before-render, client authority, denylist projection, content-hash dedupe, whole-turn retry, or browser-only protocol harness without visible surfaces returns to architecture review.

### I2 — one typed kernel for standard and unusual board actions

- **Owner:** game-kernel lead; table interaction lead owns Canvas/Pointer delivery.
- **Depends on:** I1.
- **Outcome:** a visible square-grid table executes a deterministic move and an unusual authored terrain/effect proposal through the same `ResolutionPlan` validator/reducer/transaction; temporary planning arrows/markers remain non-canonical.
- **Future files/symbols:** `domain/{commands,operations}.py::{StandardIntent,ResolutionPlan,Operation}`, `application/kernel.py::GameKernel`, `domain/board.py::{Grid,Pathfinder,LineOfSight}`, `adapters/adjudicator.py::PrivateAdjudicator`, `web/src/table/{board,interaction,overlays}.ts`, `tests/integration/test_i2_kernel_board.py`, `tests/browser/test_i2_pointer_board.py`.
- **Inputs:** reviewed Unified Core M1/M2/M5/M6 and R7 Pointer/overlay contracts. The adjudicator is fake and produces only closed plans.
- **RED oracle committed first:** legal/illegal move, occupancy/corner/LOS/resource fixtures; unknown/generic operation; operation-N failure; stale/cancelled provider attempt; plan-digest/card binding; duplicate unusual commit; reveal/terrain secret canary; mouse/touch/pen/cancel; overlay TTL/reconnect.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/integration/test_i2_kernel_board.py::test_i2_standard_and_unusual_actions_share_one_atomic_kernel`.
- **Measurable AC:** standard path makes zero model calls; unusual candidate cannot access I/O or invent IDs/rules/numeric damage; both enter the same validator; all operations validate detached before any reducer; exact one terrain/effect/world transition; invalid/unknown plan leaves state hash unchanged; visible token/cells/areas update on the table and public result on scene; admin sees no plan/truth; overlays reconnect/expire without aggregate/world change.
- **Failure/rollback:** a failed plan stores a safe rejection; schema/operation revision rolls forward only with compatibility fixtures. Roll back application code, not a committed board revision.
- **Security/privacy/IP boundary:** only scoped private adjudicator context; public narrator is not the adjudicator; no arbitrary patch/script/tool; player projections are positive schemas.
- **Stop/falsification:** a second narrative/tactical authority, partial multi-operation effect, model/client-authored path/result/visibility, missing resolution binding, or browser-filtered secret state reopens the Core decision.

### I3 — SRD 5.2.1 rules tranche A and three level-3 starters

- **Owner:** game-systems lead; provenance reviewer owns SRD/attribution rows.
- **Depends on:** I2.
- **Outcome:** implement the shared rules foundation plus `guardian`, `fury`, and `shadow` profiles as visible playable mechanics on the board, not merely data records.
- **Future files/symbols:** `domain/rules/{bundle,d20,turns,grid,hp,death,conditions,initiative}.py`, `domain/rules/profiles/{guardian,fury,shadow}.py`, `domain/rolls.py::{PendingRoll,Resolution,ResolutionEffect,PublicWorldRoll}`, `tests/rules/test_i3_rules_tranche_a.py`, `tests/browser/test_i3_three_starters.py`.
- **Inputs:** Core M3/M4; exact official SRD 5.2.1 inventory admitted by I0; no 5.1 or closed rule source.
- **RED oracle committed first:** fixed RNG vectors; +2 proficiency at level 3; action/bonus/reaction/movement double-spend; grid/path/LOS/range; HP/temp/resistance and exact effect consumption; death-save transition table; public enemy retry; side/classic cursor basics; golden visible features for guardian (fighting style, Second Wind, Action Surge, Champion critical), fury (Rage, resistance/damage, Reckless Attack, Danger Sense/Frenzy interpretation), and shadow (Expertise, Sneak Attack eligibility, Cunning Action, Thief movement/object interaction subset).
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/rules/test_i3_rules_tranche_a.py::test_i3_core_rules_and_three_level3_profiles_close`.
- **Measurable AC:** every listed mechanic has one golden UI-visible case and one zero-mutation rejection; physical pending rolls consume once; enemy face/modifier/total/result is same-transaction public evidence and retry never rerolls; side/classic accept the same legal intent and reject wrong actors; no unsupported condition/action is approximated.
- **Failure/rollback:** unsupported feature is explicitly `unsupported_in_mvp`; remove/change a prepared feature only by a new bundle version and content compatibility check. Stored rolls are immutable.
- **Security/privacy/IP boundary:** exact SRD source/version/section/transformation/attribution rows; no D&D branding or closed books; injected RNG is server-only and no secret die fudging exists.
- **Stop/falsification:** any mechanic needs mixed rules versions, generic expressions, hidden roll change, client-computed legality, or cannot be represented through the I2 kernel.

### I4 — SRD 5.2.1 rules tranche B and complete six-starter bundle

- **Owner:** game-systems lead; UI owner accepts curated choice load.
- **Depends on:** I3.
- **Outcome:** add `beacon`, `arcanist`, and `voice`; close curated spell/area/concentration/condition/rest resources and both encounter schedulers into one hashed `srd-5.2.1-mvp-1` bundle for all six profiles.
- **Future files/symbols:** `domain/rules/{spells,areas,concentration,resources,rests}.py`, `domain/rules/profiles/{beacon,arcanist,voice}.py`, `contracts/rules-bundle.schema.json`, `tests/rules/test_i4_rules_bundle.py`, `tests/browser/test_i4_six_starters.py`.
- **Inputs:** I3 bundle; Core M3/M4 and R9 starter acceptance templates; admitted SRD rows.
- **RED oracle committed first:** beacon spell slots/DC/healing/Bless concentration/Preserve Life; arcanist spell attack/save/area/Sculpt Spells/concentration/terrain effect; voice Bardic Inspiration/skills/healing-control/Cutting Words reaction; concentration replacement/break, areas/targets, reset cadence, no-healer fixtures, all six selection/onboarding cards, side-phase interpretation or forced classic fallback for initiative-sensitive features.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/rules/test_i4_rules_bundle.py::test_i4_six_level3_profiles_and_curated_srd_bundle_close`.
- **Measurable AC:** exactly six distinct level-3 profiles; every visible feature has a golden test and supported operation; only the curated spell/condition/damage set is advertised; no role is mandatory for a clue or recovery; UI choice caps from R9 templates hold; bundle hash, engine version, attribution, and operation inventory are reproducible.
- **Failure/rollback:** reduce a prepared profile’s advertised mechanics rather than pretending support; any change creates a new bundle hash and reruns all content/calibration compatibility.
- **Security/privacy/IP boundary:** same SRD/branding gate as I3; no full character builder, full spell catalogue, or cross-setting profile schema.
- **Stop/falsification:** a profile requires an untested operation, silent mechanic approximation, hidden difficulty adjustment, healer assumption, or unversioned bundle change.

### I5 — one-mic PTT proxy, approval, and physical-roll declaration

- **Owner:** speech-input/browser lead; R4 owner accepts handoff/dedupe; privacy owner controls real-audio admission.
- **Depends on:** I3 (I4 may proceed in parallel).
- **Outcome:** actual table/composite PTT controls bind a selected hero before audio, stream bounded PCM through the VPS speech proxy, create at most one reviewed action/party-plan/roll draft, and preserve typed fallback. Ordinary room speech performs no capture or network work.
- **Future files/symbols:** `adapters/stt.py::{SpeechAdapter,SpeechProvider,DeepgramProvider,FakeSpeechProvider}`, `application/speech.py::{CaptureAttempt,FinalAssembler}`, `web/src/table/{ptt,capture,roll-card}.ts`, `web/src/shared/capture-worklet.ts`, `contracts/speech.schema.json`, `tests/integration/test_i5_speech_roll.py`, `tests/browser/test_i5_ptt.py`.
- **Inputs:** approved R5 contract; I3 pending-roll port; I1 session/capability transport; fake provider by default. `AudioCancellationPort.cancel_current_for_input` is a fake until I6 joins.
- **RED oracle committed first:** zero ambient audio; admission duplicate/conflict/cross-room actor; actor/purpose freeze; ordered PCM profile/frame/gap/backpressure; interim/final/Metadata/normal-close versus abnormal-close; restart `armed/capturing/finalizing/ready/submitted`; corrections/nonces; shared plan; “17 arrows” rejection and marked roll acceptance/correction; late generation; typed fallback; PTT cancel/barge-in with zero kernel calls.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/integration/test_i5_speech_roll.py::test_i5_ptt_partial_restart_and_roll_confirmation_fail_closed`.
- **Measurable AC:** one accepted capture produces zero or one immutable final candidate; only Metadata plus normal close can make it ready; raw/interim audio/text never persists/logs; ready candidate/event persist atomically and retry exact R4 receive; current approved roll consumes one pending ID; reconnect never auto-resends; table visibly distinguishes provisional/finalizing/review/error/typed; scene gets no player speech and admin gets enums/timing only.
- **Failure/rollback:** fail the capture, discard memory, show explicit Retry/Type; never reconnect/replay active audio or switch routes mid-capture. Voice feature flag can disable to typed input without state migration.
- **Security/privacy/IP boundary:** selected route has no browser provider credential; raw PCM memory-only; operational logs contain IDs/counts/spans/enums, not content; `mip_opt_out`/region/account/DPA/retention/deletion and participant consent are unresolved real-call gates.
- **Stop/falsification:** continuous cloud listening, wake word/diarization dependency, raw recording, partial submission, long-lived browser key, real call without gate, auto-approval, number-only roll, or speech/cancel calling the kernel.

### I6 — caption-first audio plane and strict browser control barrier

- **Owner:** audio/backend lead; browser-audio lead owns Web Audio reducer; provenance/privacy owners accept manifests/provider data route.
- **Depends on:** I1.
- **Outcome:** post-commit safe presentations route to deterministic cached speech/SFX/music or fake dynamic TTS; exactly one leased browser plays; strict `audio_fence` control clears old lanes before admitting higher-fence media; caption/text-only remains complete.
- **Future files/symbols:** `presentation/audio.py::{AudioRouter,SpeechLine,AudioFence,PlaybackLease}`, `adapters/tts.py::{TtsProvider,FakeTtsProvider,ElevenLabsProvider}`, `web/src/shared/{audio-reducer,audio-worklet,mixer}.ts`, `contracts/audio.schema.json`, `assets/manifests/{voice,asset}.json`, `tests/integration/test_i6_audio.py`, `tests/browser/test_i6_audio_barrier.py`.
- **Inputs:** R6 `r6.audio.v2` including post-ceiling strict barrier; R7 lease; I1 presentation/outbox. Synthetic cleared assets and fake PCM only until I10/I12.
- **RED oracle committed first:** cache shuffle/retry stability and zero TTS on normal combat; explicit voice/fallback/text-only; wrong/undisclosed input; all speech/SFX/music exact lease+consumer+fence identities; reordered next-fence media before stop; clear→commit fence→drain with no `await`; queue gap/timeout/count/byte/speech-duration bounds; lease loss/re-election; provider close + browser stop; late chunks; explicit retry disposition; reconnect music-only reconstruction; telemetry required fields and forbidden plaintext/unkeyed hash.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/browser/test_i6_audio_barrier.py::test_i6_reordered_control_cannot_overlap_old_and_new_audio`.
- **Measurable AC:** actual browser test proves future-fence speech/music/SFX do not decode/fetch/play before control; scoped/all-audio clear precedes fence commit; old lease/fence events stay silent; projection acknowledgement alone never makes audio eligible; every delivery rechecks the current playback lease and `audio_fence`; one leader; cancel closes provider fake and zeroes browser buffers without world revision/kernel call; reconnect replays no speech/SFX and freshly renders only current music; missing route degrades; telemetry excludes text/secrets and leaves cost unknown when provider does.
- **Failure/rollback:** disable dynamic TTS and/or all audio while retaining captions; explicit audio retry creates a new context/playback attempt only after old close/stop disposition. Never roll back game state for audio.
- **Security/privacy/IP boundary:** only disclosed `text_ref`; server credentials; approved immutable voice/asset manifest; retention/deletion/withdrawal references mandatory; no cost plan, real voice, or provider-quality claim.
- **Stop/falsification:** media advances fence, multiple leaders, unbounded buffer/clock uncertainty, provider-only cancellation, reconnect speech replay, hidden text/telemetry leak, random/provider-library fallback, or any audio path invokes kernel.

### I7 — CampaignDefinition v2 compiler and synthetic authored vertical

- **Owner:** content-platform/narrative-system lead; Core owner accepts schema migration; provenance owner accepts admission mechanics, not content rights.
- **Depends on:** I2.
- **Outcome:** implement the closed R9 content compiler/linter/hash and a sanitized story/NPC/clue/off-rail fixture that drives the real I2 kernel and projections. This is runtime/content tooling, not production campaign prose or assets.
- **Future files/symbols:** `application/content.py::{CampaignCompiler,CampaignLinter,canonical_hash}`, `domain/narrative.py::{NarrativePolicy,EndingEvaluator}`, `contracts/campaign-definition-v2.schema.json`, `tests/content/test_i7_definition_v2.py`, `tests/integration/test_i7_story_kernel.py`, sanitized `tests/content/fixtures/abstract-package/`.
- **Inputs:** Core definition/operation contracts; R9 content contract/handoff; R8 provenance relation model. R9’s post-review-ceiling effect-reference/idempotency and terminal-consequence fixes are mandatory RED cases, not assumed proof.
- **RED oracle committed first:** closed schema/hash mutation; every operation-specific reference/subject kind/signature; all four idempotency scopes same/different instance; DNF; bounded reachable-state exploration; obligations/timing classification; exact success/loss/mixed priority; terminal consequence+hook same commit; alternate/durable clue and carrier loss; NPC absent/dead; reveal dominance; positive public/private serializers; topology/LOS/spawn; provenance expiry/withdrawal/relationships.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/content/test_i7_definition_v2.py::test_i7_compiler_closes_effects_reachability_secrets_and_terminal_consequences`.
- **Measurable AC:** authoritative package fields are inside one hash; no runtime “latest”; every dangling/mismatched mutation fails; same-scope effect replays reject and next declared scope succeeds; each terminal contains declared consequence/hook; off-rail/carrier-loss trace preserves a meaningful next choice without truth change/teleport; only `public_fact` reaches public surfaces; synthetic blocked provenance cannot ship.
- **Failure/rollback:** reject compilation/admission and keep prior definition hash; a running room never migrates silently. New schema requires an explicit migration rehearsal or new run.
- **Security/privacy/IP boundary:** sanitized abstract fixture only; no closed adventure/show transcript/current campaign/concept image; private adjudicator scope and public narrator projection stay separate.
- **Stop/falsification:** un-hashed sidecar authority, natural-language trigger authority, generic patch, unresolved effect, terminal without consequence, unsafe serializer, unbounded graph, or production prose/assets entering this tooling ticket.

### I8 — Core-shaped encounter calibration before production acceptance

- **Owner:** game-systems/calibration lead; content lead observes but cannot change frozen bands after results.
- **Depends on:** I4 and I7.
- **Outcome:** create actual Core simulations over all six implemented profiles, real rules/operations, authored test maps/objectives, both schedulers, 3/4/5-player combinations, declared and adversarial target policies. Reject the R9 initial “normal” synthetic envelope as a baseline; find evidence for a candidate or stop production encounter acceptance.
- **Future files/symbols:** `tools/calibrate_encounters.py::{freeze_protocol,run_matrix}`, `tests/calibration/test_i8_core_calibration.py`, `tests/calibration/fixtures/`, `docs/evidence/calibration/{freeze,results}.json`.
- **Inputs:** pinned I4 bundle, I7 compiler, R9 timing/balance model and its recorded failed normal envelope. XP labels are ceilings/inputs only, never balance evidence.
- **RED oracle committed first:** test marks `r9-normal-stat-only` as `REJECTED_BASELINE`; demands immutable pre-run bands, every legal distinct-role combination, fixed seeds, declared plus focus-fire policies, objective/round-cap outcomes, public rolls, map/LOS/resources, no-healer cases, alpha/death/down/TPK/round/system-time cells, and side/classic comparison. Initial RED is missing actual Core matrix evidence.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/calibration/test_i8_core_calibration.py::test_i8_core_matrix_precedes_any_production_encounter_acceptance`.
- **Measurable AC:** freeze artifact predates result; every required cell reports pass/fail and raw counts; no hidden stat/die changes; objective resolves at named legal round boundary; candidate encounter references exact rules/map/templates; at least one candidate meets the pre-frozen correctness/timing/risk bands or the ticket returns a failure verdict and blocks I9. No simulation result is called fun or balanced beyond its exact bands.
- **Failure/rollback:** calibration data is append-only by protocol version; failed candidates remain recorded. Revise encounter templates/objectives or reduce scope, then create a new freeze/version—never tune thresholds post hoc.
- **Security/privacy/IP boundary:** deterministic original/synthetic fixtures, no provider/player data or closed content; exact rules/provenance hashes.
- **Stop/falsification:** missing cell/policy, post-hoc band, use of failed R9 normal envelope, random/merciful-only policy, HP-kill-only exit after cap, hidden scaling, or no candidate passing all frozen gates.

### I9 — author the original campaign, heroes, maps, and accepted encounters

- **Owner:** narrative/content lead; game-systems lead signs encounter references; no runtime engineer edits production truth to satisfy code.
- **Depends on:** I4, I7, and a passing I8 candidate.
- **Outcome:** author one original typed campaign candidate: six named level-3 heroes, immutable truth/secrets/NPC goals, clues/routes/beats/redirects/endings, two authoritative map topologies/art briefs, investigation/trap, shared-plan/roll/dispute beats, skirmish, boss, consequence, and hook. Binary art/audio/voices are only logical requirements here and remain unadmitted until I10/I11.
- **Future files/symbols:** `campaigns/mvp/{package,truth,npcs,clues,beats,redirects,outcomes,effect-templates,encounters,enemy-templates,starter-roles,presentation}.json`, `assets/maps/briefs/`, `tests/content/test_i9_authored_definition.py`, `docs/content/authoring-evidence.json`.
- **Inputs:** I7 compiler; I4 rules bundle; I8 accepted calibration envelope ID and frozen results; R9 timing/acceptance templates. No closed adventure or actual-play expression.
- **RED oracle committed first:** exact six roles, twelve obligations, 60–90 compiled non-refusal traces, alternate/durable clues, off-rail/refusal/loss, all operations/mechanics, map topology/LOS/light/spawn, calibrated exact 3/4/5 rosters/objectives/round caps, player-safe serializers, ending consequence/hook, and logical asset requirements. It fails on the absent authored definition.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/content/test_i9_authored_definition.py::test_i9_original_definition_is_reachable_timed_and_core_supported`.
- **Measurable AC:** one hashed definition candidate passes semantic/reachability/security/mechanic/map checks; all encounter rows cite the I8 accepted envelope and exact templates; all six heroes use tested I4 mechanics and no clue depends on one; compiled timing fits structurally; content/source rows identify original authorship. Status is `content_ready_not_release_ready` until I10 assets and I11 full provenance/dry run pass.
- **Failure/rollback:** cut/merge/rewrite content under a new package hash; never expand runtime, invent an operation, weaken the oracle, or modify a running room. Failed authored versions remain evidence.
- **Security/privacy/IP boundary:** original prose/topology only; no binaries, current campaign data, concept-reference redraw/style prompt, unidentified source, D&D branding, raw voice, closed adventure/map/character/show text.
- **Stop/falsification:** uncalibrated encounter, unsupported mechanic, dead clue, forced teleport/wall, timing miss, missing consequence/hook, secret leak, or unproven original authorship.

### I10 — admit production art, maps, portraits, voices, cached lines, music, and SFX

- **Owner:** creative-production lead; qualified provenance/legal and privacy reviewers decide admission; audio lead only validates technical compatibility.
- **Depends on:** I0, I6, and I9. Sourcing/contract preparation may overlap earlier work, but final admission waits for I9's frozen briefs and logical IDs.
- **Outcome:** create/commission/license and admit the original campaign’s production binaries and performer/provider routes without changing runtime or story truth.
- **Future files/symbols:** `assets/cleared/{maps,portraits,voices,cache,music,sfx}/`, `assets/manifests/{maps,portraits,voice,asset}.json`, `provenance/{materials,relationships}.tsv`, `tests/content/test_i10_assets.py`, controlled off-Git consent/receipt/terms evidence references.
- **Inputs:** I0 row gate; R8/R6/R9 provenance and withdrawal contracts; I6 format/voice/cache interfaces; I9 logical requirements as they stabilize. Real provider generation or voice enrollment requires separate written budget/data/provider approval and performer consent before each class of call.
- **RED oracle committed first:** unknown/hash drift/expiry/withdrawal/disallowed use/unqualified reviewer; recording→script→voice/cache and music-master→work relationship closure; SRD/content separation; Severin/important-NPC declared fallback; cache worst-trace shuffle/repetition; missing asset fail-silent; withdrawal inventory and deletion route. It fails because no production rows are yet admitted.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/content/test_i10_assets.py::test_i10_every_production_asset_voice_and_relationship_is_cleared`.
- **Measurable AC:** every shipped byte has exact path/hash/origin/rights/uses/term/territory/attribution/reviewer; performer rights cover recording/model/synthesis/edit/cache/distribution/public performance and withdrawal; provider/account/terms/retention evidence matches any generated output; cache pools make zero live TTS and meet the R9 repetition oracle; withdrawal rehearsal selects only declared cleared fallback/text-only/silence and locates linked outputs.
- **Failure/rollback:** remove the blocked/withdrawn byte and all dependants from the build; activate only declared cleared fallback. Reissue manifests/hashes; never search provider/library/filesystem randomly.
- **Security/privacy/IP boundary:** consent instruments/enrollment recordings/receipts and provider secrets remain encrypted outside Git; Git contains cleared deliverables and opaque evidence references only. No first-party code permission extends to these rows.
- **Stop/falsification:** no qualified evidence, public-library voice as sole brand identity, unapproved provider call, concept/closed-content input, unknown generated inputs/terms, unresolved relationship, or inability to withdraw/delete.

### I11 — integrate and accept the facilitator-free 60–90-minute slice

- **Owner:** integration lead; narrative, rules, browser, audio, security, and provenance owners each sign only their boundary.
- **Depends on:** I5, I6, I9, and I10 (I4/I7/I8 flow through I9).
- **Outcome:** one frozen build/package runs hero and Severin selection → important NPC/direction → investigation/trap → shared plan/physical roll → skirmish → rules dispute → boss → persistent consequence/hook through actual table, scene, and admin browsers, with fake-provider degradation and real-runtime boundaries.
- **Future files/symbols:** `campaigns/mvp/definition.compiled.json`, `application/session_flow.py`, `tests/e2e/test_i11_vertical_slice.py`, `tests/content/test_i11_campaign_package.py`, `docs/content/{dry-run-freeze,dry-run-results}.json`, `docs/rehearsal-runbook.md`.
- **Inputs:** all dependency commits/hashes; R9 main package oracle and facilitator-free protocol. The technical operator has only admin controls and cannot act as GM.
- **RED oracle committed first:** R9 full package assertions plus ten automated adversarial traces; fast-forward every durable stage; provider loss/text-only; duplicate/reconnect/crash; dispute correction/explanation; side/classic mode; canaries/withdrawal; actual 3/4/5 cold dry-run workbook; separate technical/content/soul/repetition fields. It fails on the not-yet-integrated package/build.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/e2e/test_i11_vertical_slice.py::test_i11_full_slice_is_restartable_secret_safe_and_provider_degradable`.
- **Measurable AC:** automated A1–A10 traces pass; no duplicate mutation/roll/reveal/audio authority; standard combat uses no model/live TTS; all three real surfaces and composite converge; typed/text-only path completes; every valid cold 3/4/5 facilitator-free run commits all twelve obligations, consequence, and hook in 60–90 minutes; each player acts consequentially before boss; operator uses no creative override; content/soul/repetition diagnostics are recorded separately and meet the frozen R9 readiness bands. No product/fun claim is made.
- **Failure/rollback:** classify each observation; technical fallback may preserve a content trace but does not green the failed subsystem. Fix content/runtime under a new freeze packet; never change thresholds or exclude waits post hoc.
- **Security/privacy/IP boundary:** only admitted content/assets; no participant/provider data needed for automated traces; human internal dry-run uses pseudonyms and no raw audio/video recording.
- **Stop/falsification:** secret leak, unsupported mechanic, duplicate effect, unapproved asset, creative operator, timing miss, missing obligation/consequence/hook, content/soul/repetition readiness failure, or non-MVP feature dependency.

### I12 — isolated remote-VPS staging and target-room rehearsal

- **Owner:** release/reliability lead; VPS/security owner authorizes infrastructure; provider/data/budget authorities and every participant authorize real external audio.
- **Depends on:** I11 plus explicit `APPROVE STAGING`; real STT/TTS steps additionally require provider-account/retention/region/deletion approval, budget approval, cleared voices/assets, and participant consent.
- **Outcome:** deploy the immutable I11 OCI artifact to an isolated non-production service/domain/database/secret set on the remote VPS; exercise three physical browser surfaces, target microphone/speakers, real network interruption, backup/restore, and—only after its gates—the real provider routes.
- **Future files/symbols:** `deploy/staging/{Containerfile,compose-or-runner-config.example,runbook,rollback}.md`, `tests/security/test_i12_remote_authority.py`, `tests/e2e/test_i12_staging_room.py`, `docs/evidence/staging/{freeze,results,restore,security}.json`.
- **Inputs:** I11 artifact/hash; R8 threat model/repo baseline; R5/R6/R7 real-browser/provider gaps. Before observation, decision owners freeze supported browsers/devices, capture/queue bounds, clock/lease measurements, acoustic method, and any usability/non-inferiority latency/reliability gate. This plan invents no numeric latency SLA.
- **RED oracle committed first:** remote table/scene/admin Playwright/device contexts; exact role/actor/cross-room/replayed ticket/direct-command negatives; all crash/reconnect stages; same-version projection; one audio leader; strict cancel loopback; internet loss; log/backup/secret scans; migration/restore; provider/fallback spans. It fails before staging endpoint/evidence exists.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/e2e/test_i12_staging_room.py::test_i12_remote_three_surface_room_recovers_with_one_audio_leader`.
- **Measurable AC:** isolated TLS service and secrets; no production/shared DB/key/config; negative authority tests have zero mutation; restore produces the same committed aggregate/outbox/cursors; table/scene/admin on target devices reconnect; internet loss visibly disables authority; only one audible client; provider close and physical/browser buffer stop are separately observed; real STT/TTS results and p50/p95 named spans are reported if authorized, without a marketing-derived SLA; sanitized staging packet is ready for R10.
- **Failure/rollback:** stop admission, cancel provider/audio, preserve DB, roll application back to prior compatible image, or restore only from a rehearsed backup with no newer commits. DNS/TLS/service changes use the VPS owner’s audited reversible runbook.
- **Security/privacy/IP boundary:** least privilege, exact Origin/CSP/no-store/log redaction, server-only keys, no raw room audio/video retention, consent/account evidence, approved content only. No current production or Orchestra runtime is touched.
- **Stop/falsification:** missing authority/isolation/rollback, client secret, cross-room or capability bypass, secret log/projection, unrecoverable DB, unbounded audio/clock ambiguity, wrong/uncleared voice, failed frozen room gate, or absent consent/provider evidence. Do not proceed to R10 in text-only staging merely to bypass required room presentation.

### R10 — consented physical-room product and side-phase playtest

- **Owner:** product-experiment lead; game-systems lead owns side-phase verdict; privacy owner validates consent/retention; product owner receives the frozen evidence and decides post-MVP direction.
- **Depends on:** accepted I12 staging packet; an independently approved protocol freeze before recruitment opens; and a separate participant-admission record after recruitment but before any microphone, provider, or session activity.
- **Outcome:** freeze the experiment protocol, admit only actually recruited and consented participants, then run the polished slice in the physical room without a human GM; preserve separate technical, content, soul, repetition, product, and side-phase verdicts.
- **Future files/symbols:** `docs/experiments/r10/{protocol,protocol-freeze,participant-admission,observations,verdict}.md`, `tests/delivery/test_r10_freeze.py`; consent instruments and actual participant records remain in the controlled non-Git system and are referenced opaquely.
- **Inputs:** canonical product criterion; R9 dry-run/failure taxonomy; I12 exact build/room/provider/browser hashes and limitations. Target is 2–3 complete sessions; one valid complete session is minimum evidence, and fewer than two explicitly lowers confidence.
- **RED oracle committed first:** one immutable lifecycle oracle uses synthetic records and fails until (a) the protocol freeze—build/content hashes, consent form/version, unchanged questions, clock, observer guide, technical/content/soul/repetition/product/side-phase fields, invalidation rules, retention policy, and evidence/decision owners—is signed before recruitment opens, and (b) each actual participant admission, created only after recruitment, contains that participant's consent reference and is accepted before microphone, provider, or session activity. It rejects fabricated pre-recruitment participant references and any room I/O before admission.
- **Delivery command:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /ABS/PRIVATE/PROJECT --frozen pytest -q tests/delivery/test_r10_freeze.py::test_r10_freeze_packet_and_verdict_preserve_separate_failure_classes`.
- **Frozen success criteria:** **technical**—a valid 60–90-minute run, no duplicate/secret/authority failure, and failures attributed to input/state/audio/UI separately; **content**—required choices/obligations/consequence/hook delivered and participants can recall the important NPC goal/refusal plus at least three of NPC/choice/consequence/hook by the R9 majority rule; **soul**—a majority cites a concrete Severin moment rather than only “the AI/voice/interface”; **repetition**—no adjacent cached repeat or asset over twice in the bounded trace and no dominant cadence complaint across two beat families; **product**—participants spontaneously ask to continue and are ready to propose/set the next date; **side phases**—participation, phase duration, alpha/focus behavior, waiting, and initiative-feature impact are reported against the pre-frozen comparison, with classic fallback evaluated separately.
- **Measurable AC:** protocol-freeze timestamp precedes recruitment-open; every participant-admission timestamp follows recruitment and precedes all microphone/provider/session events, references the exact consent form/version, and fails closed on withdrawal; exact participant responses and missing data are preserved; invalid sessions are excluded with reason, not silently rerun/pooled; each verdict has evidence and confidence; technical green cannot overwrite content/soul/repetition/product failure; side-phase-only failure selects the tested classic fallback rather than rewriting the product hypothesis.
- **Failure/rollback:** stop the session safely through admin controls; retain canonical state and sanitized observations; fix under a new build/freeze. A failed product criterion blocks feature expansion and is not relabeled a technology issue.
- **Security/privacy/IP boundary:** explicit informed consent before microphone/provider use; pseudonymous minimal notes; no raw audio/video in Git; transcript/provider retention follows the accepted policy and deletion owner; no participant identity in product telemetry.
- **Stop/falsification:** missing/withdrawn consent, operator acts as GM, incomplete slice, unapproved build/provider/asset, changed threshold/question after observation, leading continuation prompt, collapsed failure classes, or a fun/product claim from synthetic/internal evidence.

## 7. Loud unresolved real-world gates

| Gate | Evidence/decision owner | Required evidence before action | If absent or negative |
|---|---|---|---|
| Destination organization/legal entity and contributor instruments | organization owner + qualified IP/legal reviewer | named entity, owners, assignments/agreements, qualified reviewer set | I0 stops before bootstrap/product push. |
| Literal reuse row | provenance reviewer + relevant contributor/licensor | exact blob/range/authors/grants/dependencies/notices/fit/exclusion scan | behavioral rewrite or avoid; owner authorization alone is insufficient. |
| Fresh dependencies | security + provenance reviewers | exact pins/hashes, direct/transitive licenses/notices, vulnerability/SBOM result, intended hosted use | dependency is not added. |
| SRD/branding | qualified reviewer | exact 5.2.1 inventory/hash/attribution/modification record and product branding decision | rules/content build stops; no inferred D&D brand right. |
| R6/R7/R9 unconfirmed research seams | implementation code reviewer for I6/I1–I2/I7–I8 | immutable RED plus Sol-floor implementation review and real browser/Core evidence | affected ticket stops; prior self-review is not called independent. |
| Encounter bands and candidate | game-systems lead | pre-run I8 freeze, full actual-Core matrix, failures and accepted candidate ID | I9 cannot accept a production encounter. |
| Production content/art/audio/voice | content owner + qualified provenance/privacy reviewers | original/commission/grant rows, relationships, hashes, terms, consent/withdrawal | I10/I11 stop or use declared text-only/silence only where the desired slice still remains valid. |
| Deepgram account/room route | provider/data/budget authorities + participants | current model/account/region/DPA/retention/log/deletion/opt-out evidence, consent, frozen measurement protocol | no real speech call; typed input only, I12/R10 not voice-accepted. |
| ElevenLabs account/voice route | provider/data/budget authorities + performer/participants | paid-use entitlement if required, terms/retention/ZRM truth, voice consent/rights, deletion/withdrawal, frozen A/B protocol | no real generation/enrollment; captions/cached cleared assets only, audio acceptance may stop. |
| Numeric latency/reliability/usability threshold | product/experiment lead before real observation | signed protocol naming spans, cohort/devices and pass rule | measurements may be descriptive only; no route/SLA success claim. |
| Cost policy | budget/product owner | explicit approved budget/policy, if any | usage is measured in provider-native units/unknown; no purchase or cost claim. |
| Staging VPS | VPS/security/release owners | isolated service/domain/DB/secrets, TLS/origin/logging, backup/restore/rollback, target device matrix | I12 does not deploy. |
| R10 human sessions | product-experiment/privacy owners and every participant | frozen packet, consent, recruitment validity, retention/deletion | no session or product verdict. |

## 8. MVP completion and global stop conditions

The MVP is ready for owner evaluation only when I0–I12 delivery commands, affected regressions, required review records, provenance gates, I11 facilitator-free evidence, and I12 isolated staging rehearsal are green, and the exact R10 packet is frozen. It is product-successful only if R10’s separate product criterion is met; no technical artifact can assert that earlier.

Stop the delivery and return to the named decision owner if any implementation requires a second canonical store, unapproved mutation, browser/admin filtering of secret state, whole-turn retry after possible commit, mixed projection family, cursor-before-render, model-authored generic effect, hidden/changed die, audio-triggered kernel call, unbounded/ambiguous audio ownership, unpinned content/rules, uncalibrated production encounter, uncleared content/asset/voice, creative admin override, or any forbidden MVP feature.
