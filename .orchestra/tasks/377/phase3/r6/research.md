# R6 — complete audible-output path research

Date: 2026-08-16  
Phase: 1, research only — **orchestrator-directed blocker fix complete; ready for planning approval**
Decision owner: product/audio/backend owners; rights and retention acceptance remains with the R8 authorities  
External activity: no provider account, paid call, real voice, deployment, or production mutation was used

## Answer

The decision-grade MVP baseline is a **caption-first hybrid path with one server-commissioned browser player**:

- cleared cached recordings handle normal combat speech; cleared local assets handle SFX and state-selected preauthored music;
- dynamic disclosed story speech is routed server-side to an explicit approved ElevenLabs voice and model, then relayed as bounded PCM to the sole R7 playback-lease holder;
- Severin Crow, each important NPC, and each generic archetype are immutable manifest entries with explicit fallbacks; unknown or uncleared routes become text-only rather than a provider-library guess;
- provider generation cancellation and browser playback cancellation are two independent required effects joined by stable line/context/playback identity and a room audio fence;
- reconnect restores projections, never sound; any partial/failed dynamic line remains captioned and requires an explicit audio-only retry that cannot call the game kernel;
- cost is measured per attempt and reconciled in provider-native units, but this research selects no subscription, dollar budget, or price policy;
- the current voice/audio inventory remains fail-closed under R8, so this design cannot make a real provider call or ship a literal asset until its provenance and retention gates pass.

The full alternative comparison is in [`alternatives-capabilities-matrix.md`](alternatives-capabilities-matrix.md), the exact identities/messages/state transitions are in [`playback-event-contract.md`](playback-event-contract.md), and the rights boundary is in [`provenance-boundary.md`](provenance-boundary.md).

## Question framing

- **Context:** the approved AI tabletop MVP has one authoritative game core, one audible browser client, Severin Crow as narrator, authored important-NPC voices plus generic archetypes, cached normal-combat lines, and state-driven preauthored music [L1][L2].
- **Change under test:** add a complete post-commit audible-output plane spanning voice/asset routing, ElevenLabs generation, one browser player, cache/SFX/music mixing, cancel, reconnect, privacy, provenance, failure, and observability.
- **Baseline:** captions and visual projections only, plus the incomplete R4 `AudioJob` and old R7 logical lease/stop contract [L2][L3][L4].
- **Measurable outcome:** a deterministic trace must route only disclosed text/approved sources; normal combat must make zero provider calls; exactly one current lease holder may play; duplicate/stale/late media must be silent; cancel must close the provider context and clear the client buffer; retry/reconnect must make zero kernel calls; metrics must omit plaintext/secret canaries. Provider/browser/acoustic claims not reproduced by the fake trace remain explicit future gates.

## Hypotheses and falsifiers

| Hypothesis | Why plausible | Evidence that would prove it wrong | Result |
|---|---|---|---|
| **H1 — a server-owned hybrid plane can keep game authority, voice routing, usage evidence, and cancellation coherent while one browser owns sound.** | R4 already makes audio a post-projection outbox; R7 already has one server-issued playback lease [L3][L4]. ElevenLabs exposes voice-bound streaming contexts and explicit context close [P1][P2]. | Any trace sends hidden text, makes live TTS for normal combat, permits two players, accepts a stale/duplicate/late chunk, changes world state on audio retry, or cannot stop provider and browser independently. | **LIKELY overall.** The synthetic oracle passed every stated logical case [M1]; real provider, browser, and room timing are unmeasured. |
| **H2 — provider/browser direct playback or automatic reconnect replay is simpler without weakening ownership.** | A browser can use a single-use provider WebSocket token, and reconnect replay can appear convenient [P8]. | Server-side identity/cost/cancel cannot be observed end-to-end, an old browser can retain audio after lease loss, or reconnect repeats already heard words. | **REFUTED as the MVP default by contract analysis.** Browser direct remains technically possible, but fragments ownership; automatic audio replay contradicts R7 projection-only reconnect [L4]. |
| **H3 — one cancellation signal or one generation/lease counter is sufficient.** | Provider `close_context` and R7 `minimum_generation` each sound like a stop mechanism [P2][L4]. | Provider-close cannot recall already delivered samples, or lease election and content cancellation advance independently. | **REFUTED.** Official provider material documents future context close, not withdrawal of browser buffers [P2]; R7 prose names an audio fence while its schema exposes only lease generation [L4][M2]. |
| **H4 — current provider/model latency figures are sufficient to set an MVP audio SLA.** | ElevenLabs publishes an approximately 75 ms Flash inference figure [P4]. | The figure excludes network/application/browser/acoustic path or varies with voice/model/load. | **REFUTED.** The provider explicitly excludes network/application components; no real call or target-room measurement was authorized [P4]. |

## Findings

### F1 — audio must remain post-commit and non-authoritative

R4 stores a safe projection/outbox after the authoritative world commit and enqueues audio after projection acknowledgement; projection/audio retry does not rerun the world command [L3]. The R6 input is therefore a server-only `audio.intent` that references committed `turn_id`, `world_revision`, `presentation_id`, and already-disclosed `text_event_id`. Audio cancel/retry/volume/music operations change audio-control state only.

**Confidence: CONFIRMED — tier 1 R4 synthetic fault measurements plus its accepted local contract.** R6 does not remeasure the database, but its fake retry/failure trace recorded `world_revision 7 → 7` and `kernel_calls=0` [M1].

### F2 — the hybrid source split is the smallest path satisfying the fixed product facts

Normal combat selects an immutable cleared cache asset and never invokes TTS; SFX and music are cleared local assets; only important disclosed story/narrator/NPC lines may use live TTS. The cache uses a persisted deterministic shuffle bag keyed by presentation, so duplicate delivery/restart returns the same `asset_id` while each cleared pool member is used once per cycle. Missing cache is text-only, not live generation.

**Confidence: CONFIRMED for deterministic routing in the synthetic trace; LIKELY for the product fit.** Two approved `combat.hit` assets were unique in the first cycle, a duplicate presentation returned the same asset, and provider calls for normal combat were `0` [M1]. Acoustic quality and the final authored pool size are unmeasured.

### F3 — ElevenLabs voice routing is socket/request routing, not a context property

The standard and multi-context ElevenLabs TTS WebSocket endpoints put `voice_id` in the URL path; multi-context messages carry `context_id` but do not select another voice [P1][P2]. Therefore R6 resolves an exact approved voice before transport selection and uses a voice-bound socket. Multiple active voice identities imply multiple possible sockets, while the MVP dispatcher permits at most one room-wide generating context to avoid overlapping speech and plan-specific concurrency assumptions.

Severin resolves only to `narrator.severin`; an important NPC resolves exact entity → its explicit cleared archetype fallback → text-only; a generic NPC resolves only through a finite cleared archetype entry. The provider Voice Library is not an implicit fallback because shared voices can become unavailable [P13].

**Confidence: CONFIRMED for the provider endpoint shape and synthetic explicit routing — tier 2 official API plus tier 1 fake trace.** The trace routed Severin explicitly, routed one blocked exact NPC voice to its declared `npc.guard` fallback, and degraded an unknown route to `text_only` [M1]. Final voices/quality are blocked by provenance and listening tests.

### F4 — server-owned multi-context WebSocket is the selected default, not a latency verdict

Multi-context WS provides an utterance/context close and permits contexts on a voice-bound connection [P2]. A server adapter keeps the long-lived key, manifest lookup, attempt record, close operation, and usage/latency identifiers in one authority. Server HTTP streaming remains a measured fallback because ElevenLabs advises HTTP streaming when complete text is already available and warns that WebSocket input buffering can add latency for that shape [P1][P3]. Browser-direct WS is feasible using a consumed, 15-minute single-use `tts_websocket` token, but is not selected because provider lifecycle would be split across the browser lease and server [P8].

**Confidence: LIKELY — tier 2 protocol documentation plus contract analysis, no provider measurement.** Authorized A/B traces can reverse WS versus HTTP without changing the line/player contract.

### F5 — provider cancellation and audible cancellation are separate obligations

`close_context` prevents further useful generation for that provider context, but official documentation does not promise that bytes already delivered to an application/browser are recalled [P2]. The browser must independently apply an authenticated stop control that clears its matching bounded PCM ring/scheduled sources first and commits the higher `applied_control_fence` second; media never advances that fence. W3C specifies that `AudioScheduledSourceNode.stop(0)`/a past time stops immediately in the render timeline and that AudioWorklet processing uses finite render quanta; neither fact proves physical speaker silence at a wall-clock deadline [B1][B2].

**Confidence: CONFIRMED for logical separation and fake state; UNCERTAIN for physical no-echo.** The probe closed the provider context, reduced a `120 ms` fake buffer to `0`, and dropped one injected late provider chunk [M1]. A real browser/worklet/speaker loopback test remains mandatory.

### F6 — content cancellation and lease election require independent monotonic fences

R7 uses a monotonically increasing playback lease generation and a maximum client buffer of 250 ms [L4]. Its prose also says cancel increments an audio fence, but `AudioPlay` and `AudioStop` currently expose only lease generation/`minimum_generation` [L4][M2]. A content cancel can occur without electing a new client; a lease loss can occur without changing a line. R6 therefore requires both `lease_generation` and `audio_fence` on every audible lane—speech/chunks, SFX, music, and stop—plus stable semantic/delivery identity.

The selected client rule is a strict control barrier: playable media requires `audio_fence == applied_control_fence`; media never advances the fence. Only next-fence media may wait, without playback/decoding/fetch, within `16` envelopes, `256 KiB`, `250 ms` speech, and `250 ms` wait. Control clears its scope before committing the fence, then admits exact-current waiting media. Gap/overflow/timeout discards the wait queue and requests a control snapshot. A lease-loss `all_audio` stop clears every source; a stale old-leader music/SFX event is rejected by lease/fence just like speech.

**Confidence: CONFIRMED for the selected fake transition — tier 1 synthetic reordering plus direct schema inspection [M1][M2].** Future fence N+1 speech/music/SFX remained non-playing while old N media stayed active; the N+1 control recorded old lanes cleared before drain and only then activated new lanes. Physical/browser timing remains G2/G3.

### F7 — reconnect restores safe visual state and future audio only

R7 treats application replay/gaps across WebSocket reconnect as explicit projection behavior; a new document rehydrates a safe snapshot, and `reproject_last_safe` must not enqueue audio [L4]. R6 consequently never resends historical speech or SFX on reconnect. Lease loss fences/stops all local audio and interrupts any unfinished line. A successor receives future speech/SFX plus one freshly leased idempotent rendering of the current persistent `music_state_id`, starting its cleared loop from zero. An owner-triggered audio retry keeps the semantic `line_id/text_event_id/presentation_id`, but creates a new generation context and playback attempt only after prior close/stop disposition and current-lease admission.

**Confidence: CONFIRMED as the selected cross-contract behavior — accepted R7 design plus the fake stale/duplicate trace.** Generations `[1,2]` selected only `scene-b`; stale generation and duplicate speech events were rejected, the former leader's music/SFX were cleared, stale music/SFX events were rejected, the successor reconstructed `danger` music, and it replayed zero old SFX [M1]. Real disconnect timing is unmeasured.

### F8 — browser playback ownership needs one graph and explicit priority/ducking policy

The R7 lease holder owns one Web Audio graph with separate streamed speech, cached speech, critical/ordinary SFX, and music lanes. Selected priority is control `100`, speech `80`, critical SFX `70`, ordinary SFX `50`, music `10`. Speech is single-file FIFO; ordinary SFX alone may coalesce/drop under overload. State-driven preauthored music crossfades between one old/new pair and cannot block speech.

Initial duck/crossfade values (`music=0.25`, `SFX=0.50`, `80 ms` attack, `250 ms` release, `1,000 ms` music crossfade) are configuration candidates, not acoustic findings. The fake player proved only gain state transitions `.25/.50 → 1.0/1.0` [M1].

**Confidence: CONFIRMED for deterministic state logic; UNCERTAIN for intelligibility, clipping, timing, and room acoustics.** I8 must tune these on target hardware.

### F9 — failure fallback is caption-first and never automatically replays partial speech

Before-first-audio auth, voice, quota/rate, concurrency, provider 5xx, transport, or protocol failure becomes `failed_text_only`. After-first-audio failure becomes `interrupted`, clears the browser, and remains captioned; the system does not guess how many words were physically heard. Provider reconnect prepares future lines only. Cached speech/SFX/music remain locally available during TTS failure. Missing/withdrawn asset is silent/text-only, never generated on demand. ElevenLabs documents 4xx request/auth, 5xx provider, and distinct 429 rate/concurrency cases, which R6 normalizes without exposing provider bodies [P12].

**Confidence: CONFIRMED for selected fallback/state transition in the fake; LIKELY for the error mapping.** The injected `concurrent_limit_exceeded` ended at `failed_text_only`, attempt `2`, with zero kernel calls [M1]. Real provider frames/close ordering remain a gate.

### F10 — latency must be decomposed end-to-end before thresholds are chosen

ElevenLabs' approximately 75 ms Flash figure is model inference only; its documentation says network, application, model/voice complexity, and load contribute to end-to-end delay, while streaming mainly improves perceived latency [P4]. R6 records queue wait, connect, send, first provider audio, first relay, play command, first AudioWorklet quantum, provider final, playback completion, cancel request, and stop acknowledgement. Physical first/last audible sample requires a target-browser speaker-to-loopback capture.

**Confidence: CONFIRMED for what the provider figure excludes; UNCERTAIN for MVP latency.** No live provider/browser/room call was permitted, so this research intentionally sets no TTFA, completion, or cancel-silence SLA.

### F11 — cost can be observable without making a price decision

ElevenLabs documents per-generation HTTP response metadata including character cost/request/trace identifiers and a workspace usage endpoint reporting credits over time/product groupings [P5][P6]. R6 records one attempt row containing model/voice/format, character count, a keyed content HMAC and key ID, cache hit, request/trace IDs when exposed, provider-native credit/cost fields when exposed, bytes/chunks, timings, retry, and outcome. An unkeyed short-line hash is forbidden because it is dictionary-recoverable. R6 stores `unknown` rather than estimating a missing WebSocket cost, then reconciles aggregate workspace usage.

The probe serialized three fake attempt rows with line text and the secret canary absent and `cost_policy_selected=false` [M1]. No dollar budget, plan/tier, cache-spend threshold, session cost ceiling, or acceptable price/performance value is selected here.

**Confidence: CONFIRMED for available official observability surfaces and synthetic redaction; UNCERTAIN for per-WS attribution/reconciliation until an approved provider trace.**

### F12 — default provider retention prevents an unconditional zero-retention claim

ElevenLabs says TTS input/output retention is enabled by default. Zero Retention Mode is available only to select Enterprise customers, is API-only via `enable_logging=false`, and does not cover voice-cloning samples; default deletion can retain backups up to 30 days and some limited logs can remain [P7]. API keys must remain secret/server-side; the provider explicitly advises against browser exposure of long-lived keys [P9]. R6 sends only the already-disclosed line, never hidden prompt/world fields, and logs only identifiers/count/hash.

**Confidence: CONFIRMED — tier 2 official provider privacy/auth documentation.** Actual account entitlement, region, data terms, retention configuration, deletion rehearsal, and performer enrollment path are unresolved owner gates.

### F13 — current voices/assets are unusable literals until R8 provenance closes

R8 found no voice/audio asset, performer consent, stock receipt, provider plan evidence, or generation-time terms snapshot; its transfer rows `FUTURE-VOICE-01` and `FUTURE-ASSET-01` are `AVOID_LITERAL` [L5]. R6 therefore begins with an empty approved roster. Severin, important NPCs, generic archetypes, cached combat lines, music, and SFX all require immutable manifests joining identity/work/master, source, checksum, permissions, attribution, term/territory, retention, and withdrawal.

**Confidence: CONFIRMED — direct current-tree/legal-route evidence from accepted R8 [L5].** Technical provider availability cannot upgrade this state.

## Exact selected lifecycle

```text
R4 world commit
  → safe allowlisted presentation reduced + acknowledged
  → durable audio.intent(text_event_id, event/speaker/audio_policy)
  → persist SpeechLine + voice/asset/manifest choice + attempt/fence identity
     ├─ cache_only → approved asset media_ref
     ├─ dynamic_allowed → approved voice → provider context → normalized PCM relay
     └─ missing/blocked/failure → text_only
  → audio.play only to exact current R7 lease holder
  → browser bounded mixer → audio completion/stop telemetry

cancel/pause/end/lease loss
  → durable audio_fence first
  → provider close and browser audio.stop as independent idempotent effects
  → all late provider/server/browser frames discarded

reconnect
  → projection snapshot/replay only; no historical audio
```

The exact JSON fields and state machine are normative in [`playback-event-contract.md`](playback-event-contract.md).

## Synthetic experiment

### Method and predeclared pass/fail

`audio_routing_probe.py` is a deterministic in-memory fake router/provider/player. It performs no network, audio device, browser, provider, repository, or production mutation. The oracle fails if any of these occur:

1. normal combat calls the provider or changes its cached asset on duplicate;
2. undisclosed text reaches the provider;
3. an uncleared/missing voice is guessed instead of explicit fallback/text-only;
4. cancellation leaves fake buffered duration, omits provider close, accepts a late chunk, or calls the kernel;
5. a stale lease or duplicate `audio.play` is accepted, any former leader retains/accepts music or SFX, or a successor replays old SFX/fails to reconstruct current music;
6. audio retry/failure changes world revision or calls the kernel;
7. metrics contain line plaintext/secret canary, accept an unkeyed/unknown content-derived field, or select a cost policy;
8. explicit retry starts provider I/O before old close/stop disposition or without one unambiguous lease.
9. future-fence speech/music/SFX starts before matching control, old media clears before control, control drains before its scoped clear completes, future buffering exceeds its bounds without gap recovery, or telemetry lacks any required identity/retention field.

### Reproduction

```bash
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output --frozen python -m unittest discover -s docs/tasks/377/phase3/r6 -p 'test_audio_routing_probe.py' -v
env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output --frozen python docs/tasks/377/phase3/r6/audio_routing_probe.py
```

Recorded result: `16` tests, `OK`; structured output is [`probe-results.json`](probe-results.json). Key observations were provider calls for normal combat `0`; cancel buffer `120 → 0 ms` in the same fake call; late provider chunks dropped `1`; leader generations `[1,2]`; stale and duplicate speech plays `false`; a second active speech line was rejected until the first stopped; old-leader music/SFX cleared and stale deliveries failed; successor music state was `danger`, old SFX replay count was `0`, and future SFX played. In the adversarial reordering, `3` fence N+1 speech/music/SFX events waited, none started, old N media stayed active, the control observed old lanes cleared before drain, then only new lanes were active with `0` pending; a seventeenth future envelope cleared the bounded wait queue and emitted one gap request. Retry world revision stayed `7 → 7`, kernel calls stayed `0`, retry admission failures made zero new provider starts, and required telemetry retention/deletion fields plus the content-field allowlist were enforced [M1].

**Evidence tier:** tier 1 direct deterministic measurement, limited to this fake protocol. It proves state/identity logic only, not ElevenLabs behavior, browser scheduling, codec/network behavior, audible silence, audio quality, or cost accuracy.

## Provider failure matrix

| Failure point | Stored outcome | Audible/browser action | Recovery | Game state |
|---|---|---|---|---|
| missing/blocked voice or cache | `text_only` | no play; caption remains | fix/approve a future manifest; no automatic backfill | unchanged |
| auth/permission/invalid voice before audio | `failed_text_only` | no play | operator fixes provider/route; optional explicit audio retry | unchanged |
| quota/rate/concurrency/5xx before audio | `failed_text_only` | no play | backoff only for future jobs; optional explicit retry | unchanged |
| transport/provider error after audio | `interrupted` | fence, stop, clear, restore ducking | no automatic repetition; caption remains | unchanged |
| cancel races late provider chunks | `cancelled` | provider close and browser stop independently; late identity/fence drops | duplicate cancel returns stored result | unchanged |
| browser lock/lease ambiguity/buffer cap | `failed_text_only` or `interrupted` | fail silent | acquire/unlock a future lease; never resend history | unchanged |
| reconnect/new leader | unfinished line `interrupted` | old leader stops by fence/deadline; successor gets future sound only | explicit audio retry if desired | unchanged |
| missing/withdrawn music/SFX | operational asset error | silence for that channel | approve a replacement manifest version | unchanged |

## Falsification gates before I6/I8 can claim completion

| Gate | Required production-shaped experiment/evidence | Reject the design/claim when… |
|---|---|---|
| **G1 provider protocol** | approved fake-first then real trace for standard WS, multi-context WS, and HTTP with full saved frames/headers; voice/model/context/close/error cases | documented fields differ, a context selects the wrong voice, close cannot be correlated, late data bypasses fence, or adapter relies on defaults |
| **G2 end-to-end cancel** | Chromium-family target browser with AudioWorklet ring + cached source, injected cancel at multiple buffer boundaries, speaker-to-loopback measurement | any post-cancel sample exceeds the owner-approved deadline, buffer exceeds 250 ms, a late chunk becomes audible, or stop ack falsely substitutes for physical evidence |
| **G3 one audible client** | two clients, lease grant/renew/cooperative release/crash/partition/clock uncertainty; reorder N+1 speech/music/SFX before N+1 control; record both speaker outputs; verify new leader reconstructs current music only | any future media starts before applied control equality, old/new overlap, stale generation/fence plays, old SFX replays, current music does not reconstruct safely, successor starts before safe not-before, or ambiguity produces sound instead of silence |
| **G4 reconnect/replay** | disconnect before/after first chunk/final/cancel; new document and intact reconnect | any automatic historical sound, duplicate word, world command, or cancelled line resurrection occurs |
| **G5 latency** | ≥3 production-shaped iterations per selected Severin/important/generic voice and model/transport, cold/warm, target region/browser/network; report distributions and raw traces | selected transport/model misses owner-set thresholds or provider claim cannot be mapped to physical first audible sample |
| **G6 cost reconciliation** | per-attempt observations joined to workspace usage over a fixed test window, including failure/cancel/retry/cache | credits cannot be attributed/reconciled within owner-set tolerance, plaintext leaks into telemetry, or an unknown cost is guessed |
| **G7 retention/privacy** | current provider agreement/region/plan; observed `enable_logging`; deletion/ZRM rehearsal; sampled logs/traces/caches | hidden data is transmitted/logged, entitlement is assumed, provider/app deletion boundaries are unprovable, or enrollment samples lack an approved retention path |
| **G8 provenance/withdrawal** | every voice/work/master row approved; checksum/build gate; revoke one voice and one asset end-to-end | unapproved/raw/random provider IDs play, linked outputs cannot be inventoried, withdrawal leaves future/in-flight playback, or fallback is uncleared |
| **G9 acoustic mix** | target-room speech + combat SFX + each music state; clipping/intelligibility/duck/crossfade evaluation | speech is masked, clipping occurs, queue priority changes game timing, or state transition fails to converge |

Failure of G1–G4 changes the architecture or blocks audible launch. Failure of G5/G9 changes transport/model/mixer configuration. Failure of G6–G8 blocks provider/asset admission; it does not authorize choosing a price or legal policy inside engineering.

## Interfaces and affected future work

### Unified core / R4

- Extend R4 `AudioJob` with `presentation_id`, exact speaker/source/voice/asset/model/manifest identities, generation and playback attempts, `audio_fence`, terminal/interrupted/text-only states, and attempt telemetry.
- Enqueue `audio.intent` only after successful safe projection acknowledgement; join text by `text_event_id` server-side.
- Keep audio-control storage/outbox separate from the world revision while preserving idempotent `operation_id` results.
- Never put hidden world fields, model prompts, raw provider bodies, provider secrets, voice IDs, or asset paths in browser-facing projections.

### R7 surfaces

- Preserve the one-current-lease rule, max `250 ms` buffer, fail-silent ambiguity behavior, projection-only reconnect, and no-audio reproject.
- Add an independent `audio_fence` and exact lease/generation/consumer to `audio.play`, chunks, `sfx.play`, `music.set_state`, and `audio.stop`; do not repurpose lease generation.
- Implement `applied_control_fence` as an equality barrier. Media cannot advance it; only authenticated stop/lease/pause/end/snapshot control clears then commits it. Bound next-fence wait and add `audio.control_gap`/authoritative snapshot recovery.
- Add stable `event_id`, `playback_attempt_id`, source/format/buffer fields and operational `audio.stopped` acknowledgement.
- Send usable media only to the current leader, but broadcast scoped stops/fences to every commissioned surface. On election, reconstruct only the current persistent music state; never replay historical speech/SFX.

### R8 and I8

- R8 supplies accepted provenance/rights/retention decisions; current `AVOID_LITERAL` rows remain blocking.
- I8 produces immutable cleared voice/asset manifests, offline cached combat lines, preauthored music/SFX, acoustic measurements, and provider comparison traces.
- Neither may weaken the stable identity/fence/reconnect contract; model, codec, ducking, and assets are replaceable configuration.

## Counter-evidence, limits, and reversible decisions

1. Server HTTP streaming may outperform multi-context WS when the entire line is available; official guidance explicitly makes this plausible [P1][P3]. The selected adapter boundary keeps this reversible.
2. Browser-direct WS can remove one relay hop and uses provider single-use tokens [P8]. It remains unselected because no authorized end-to-end latency advantage has been measured and it weakens centralized cancellation/cost evidence.
3. Multi-context supports up to five contexts per connection [P2], but R6 intentionally serializes speech. If later dialogue requires overlap, the one-audible-line product behavior and ducking contract must be reopened with an audible oracle rather than silently using the provider limit.
4. The fake player reports logical buffer clearing, not audio-device silence. AudioWorklet render quanta, OS buffers, Bluetooth, speakers, and room echo are outside the measurement [B2].
5. Provider documentation is primary but time-sensitive and not a contractual entitlement. Account plan, region, rate limits, model availability, terms, and retention must be snapshotted at authorized test/deploy time.
6. Voice quality, pronunciation, emotion, language coverage, cached-line repetition tolerance, mix intelligibility, and exact latency are not measured. The architecture supports their tests but does not claim their result.
7. R7 is an old read-only worktree artifact, not merged main. Its lease/cursor evidence is used as the assigned interface input, while R6 explicitly records the audio-fence schema gap rather than treating its prose as implemented truth [L4].
8. **Resolved after the second-round ceiling by explicit orchestrator direction:** R6 now selects equality with an already-applied control fence; media cannot advance it. The fake delivers N+1 speech/music/SFX before N+1 `all_audio`, proves none starts and old media remains, then proves the synchronous control clears old lanes before admitting the wait queue. This fix has adversarial self-review but no fresh model verdict: `Sol Round 2 NEEDS WORK before orchestrator-directed fix; no fresh model verdict due prose ceiling`. See `self-review-control-barrier.md` and `codex-review.md`.

## Sources and evidence

### Local/canonical

- **[L1] Tier 2 product input:** `docs/tasks/377/mvp-product-spec.ru.md` on `main`.
- **[L2] Tier 2 accepted research/plan:** `docs/tasks/377/research.md` and `docs/tasks/377/plan.md` on `main`.
- **[L3] Tier 1 local measured design:** `docs/tasks/377/phase3/r4/coordinator-adr.md`, `state-machine.md`, `command-event-schemas.json`, `probe-results.json`, and review artifact on `main`.
- **[L4] Tier 1 synthetic / tier 2 contract evidence:** read-only `surface-contract.md`, `reconnect-cursor-protocol.md`, `wireflows.md`, `transport-schemas.json`, and probe evidence under `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-three-surfaces/docs/tasks/377/phase3/r7/`.
- **[L5] Tier 2 accepted legal/security route plus direct inventory:** `docs/tasks/377/phase3/r8/ip-route.md`, `transfer-manifest.tsv`, and review artifact on `main`.
- **[M1] Tier 1 direct R6 synthetic measurement:** [`audio_routing_probe.py`](audio_routing_probe.py), [`test_audio_routing_probe.py`](test_audio_routing_probe.py), and [`probe-results.json`](probe-results.json), reproduced with the exact commands above.
- **[M2] Tier 1 direct schema inspection:** R7 `surface-contract.md:101` names an audio fence, while `transport-schemas.json:326–353` defines `AudioPlay`/`AudioStop` without one and uses `minimum_generation` for stop.

### Official primary documentation opened 2026-08-16

- **[P1] Tier 2:** ElevenLabs, [standard TTS WebSocket API](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input).
- **[P2] Tier 2:** ElevenLabs, [multi-context WebSocket guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/multi-context-web-socket) and [API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-multi-stream-input/).
- **[P3] Tier 2:** ElevenLabs, [latency optimization](https://elevenlabs.io/docs/api-reference/reducing-latency).
- **[P4] Tier 2:** ElevenLabs, [latency concepts](https://elevenlabs.io/docs/eleven-api/concepts/latency), [models](https://elevenlabs.io/docs/overview/models), and [real-time TTS guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts).
- **[P5] Tier 2:** ElevenLabs, [API introduction and generation cost tracking](https://elevenlabs.io/docs/api-reference/introduction).
- **[P6] Tier 2:** ElevenLabs, [workspace usage analytics](https://elevenlabs.io/docs/api-reference/analytics/workspace/usage).
- **[P7] Tier 2:** ElevenLabs, [Zero Retention Mode](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode).
- **[P8] Tier 2:** ElevenLabs, [single-use token API](https://elevenlabs.io/docs/api-reference/tokens/create).
- **[P9] Tier 2:** ElevenLabs, [API authentication](https://elevenlabs.io/docs/api-reference/authentication).
- **[P10] Tier 2:** ElevenLabs, [models, concurrency and priority](https://elevenlabs.io/docs/overview/models).
- **[P11] Tier 2:** ElevenLabs, [TTS output formats](https://elevenlabs.io/docs/overview/capabilities/text-to-speech).
- **[P12] Tier 2:** ElevenLabs, [API errors](https://elevenlabs.io/docs/eleven-api/resources/errors).
- **[P13] Tier 2:** ElevenLabs, [Voice Library](https://elevenlabs.io/docs/eleven-creative/voices/voice-library).
- **[P14] Tier 2:** ElevenLabs, [voice-cloning overview](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning).
- **[B1] Tier 2 standards source:** W3C, [Web Audio API 1.0](https://www.w3.org/TR/webaudio-1.0/).
- **[B2] Tier 2 standards source:** W3C, [Web Audio API 1.1](https://www.w3.org/TR/webaudio-1.1/).

## Research conclusion

The hybrid server-owned direction is **LIKELY and ready for Phase-2 planning approval**. The control-barrier, cancellation/identity/cache/retry/privacy state claims are **CONFIRMED only within the synthetic oracle**, now including the reviewer-found media-before-control reordering and bounded-gap path. The prior Sol artifact honestly remains `NEEDS WORK` because the prose ceiling forbade a third model verdict; the orchestrator selected the strict barrier and the closure evidence is the exact contract, 16-test fake, recorded trace, and adversarial self-review. Provider timing/cost reconciliation, real browser buffer stop, physical one-speaker no-echo, voice quality, acoustic mix, retention entitlement, and provenance remain **UNCERTAIN or blocked** until G1–G9. Those gates are fail-silent/text-only and require no owner price-policy choice.
