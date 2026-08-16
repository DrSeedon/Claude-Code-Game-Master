# R5 Phase 1 research — reliable shared-room speech input

- Task: #12 / R5, Phase 1 only
- Date: 2026-08-16
- Decision status: **select VPS speech proxy for the MVP safety contract; retain browser-direct as a measured optimization; omit wake word from MVP**
- Real provider/room status: **not run and not authorized**

## Question

**Context.** A browser table in one physical room has one shared microphone, a remote VPS authority, explicit per-character `Мастер` press-and-hold buttons, no diarization requirement, an approval-gated coordinator, and an AI that must not continuously intrude.[1][2]

**Change under test.** Add a speech adapter that binds a selected character before audio, produces provisional and final transcript states, supports correction/approval and explicitly declared physical rolls, interrupts current narration safely, and survives network/process failure without executing partial or duplicate input.

**Baseline.** The unsafe baseline is continuous cloud listening plus pause/number heuristics and immediate execution. The viable alternatives are browser-direct temporary-token streaming, a VPS relay with one provider stream per PTT capture, a warm VPS/provider stream, and record-then-transcribe.

**Deciding outcome.** The MVP contract passes only if ordinary room audio produces zero network audio and zero drafts; one accepted capture produces at most one immutable candidate for the bound actor; interim/partial/stale/duplicate/failing input produces zero world mutations; raw audio/interim text are not durable; reconnect/restart is deterministic; typed input remains available; and every latency component can be measured without inventing a target. Real acoustic quality and route latency are explicitly not decided by this source/synthetic phase.

The detailed result is split into `requirements-alternatives-matrix.md`, `speech-input-protocol.md`, closed `protocol-schemas.json`, and `probe-results.md`.

## Hypotheses considered and falsifiers

### H1 — VPS proxy is the most reliable MVP boundary

**Hypothesis.** Browser → VPS → one Deepgram stream per accepted PTT capture is the safest initial route because the VPS already owns room/actor authority and can own provider credentials, final-segment assembly, failure state, and the idempotent R4 handoff.[2][3]

**Falsifier.** Reject this choice if it cannot meet a numeric latency/reliability gate frozen before a representative room experiment, or if browser-direct meets that gate and every credential, log-redaction, actor-binding, finality, reconnect, correction, and no-partial oracle. No such measurement exists yet.

**Result.** **CONFIRMED for correctness/security fit; UNCERTAIN for user-perceived performance.** The selected route is a contract decision, not a claim that the extra relay is faster.

### H2 — Browser-direct is an equally reliable and faster default

**Hypothesis.** A temporary JWT lets a browser remove the browser→VPS audio relay leg and may reduce path latency.[5][10]

**Falsifier.** Reject as default if temporary credential scope/carrying headers cannot be proven absent from URLs/storage/logs, or if browser-owned final assembly and reconnect cannot pass the same fail-closed traces on every supported browser.

**Result.** **UNCERTAIN.** Deepgram explicitly supports short-lived direct client access and calls it useful for latency-sensitive applications, but its default token is a 30-second `usage::write` credential valid across `/listen`, `/speak`, `/read`, and `/agent`; no paired room measurement or browser log/reconnect evidence exists.[10] It remains a reopenable optimization, not the default.

### H3 — One warm provider stream is a better per-room primitive

**Hypothesis.** Reusing one Deepgram stream avoids per-capture handshake cost.

**Falsifier.** Reject if the end of capture N cannot be fenced from late/empty results before capture N+1 starts.

**Result.** **REFUTED for MVP.** Deepgram says a `Finalize` flush normally yields a `from_finalize` result but does not guarantee it when little audio is buffered.[8] A per-capture `CloseStream` instead processes cached data, sends final results and a summary `Metadata`, then terminates the socket.[7] That observable terminal is the cleaner capture fence; warm streaming can be reconsidered only with a measured barrier protocol.

### H4 — Record then transcribe is the simplest robust fallback

**Hypothesis.** A completed audio file gives an unambiguous utterance boundary and retry payload.

**Falsifier.** Reject if it creates a retained raw recording, loses provisional feedback, or conflicts with data minimization.

**Result.** **REFUTED for MVP.** It adds a raw-file lifecycle and delays processing until release. The chosen contract keeps only bounded memory and fails visibly instead of replaying audio.

## Findings and confidence

### 1. Authority must be bound before audio, independent of voice identity

The product fixes one shared microphone and explicitly does not require diarization; the selected hero/PTT button supplies logical actor intent.[1] R8 makes the server authoritative for room, role, actor allowlists and capabilities, and forbids client-supplied authority fields.[3] R7 already treats the table/composite as a server-projected consumer with resumable state rather than an authority source.[4]

**CONFIRMED — primary local product/security/interface artifacts agree.** `input.capture.start` therefore contains a requested `actor_id`, activation source, command ID and expected version only. The VPS validates and freezes actor, purpose, pending-roll identity, capture ID, turn ID and generation before an audio ticket exists. No diarization field enters the contract.

### 2. PTT release, not silence, is the user utterance boundary

Deepgram marks provisional results with `is_final:false`, finalizes audio segments with `is_final:true`, and warns that long utterances may yield multiple final segments before one `speech_final:true`; complete text requires concatenating final segments.[5][6] Deepgram also permits `endpointing=false`.[5] The product already supplies a deliberate press/release boundary.[1]

**CONFIRMED — product primary source plus provider primary API/guide.** Interim text is ephemeral feedback; every final segment is deduplicated and accumulated; `speech_final` is only UI evidence; ordered PTT release sends `CloseStream`. `Metadata` is necessary but only the subsequent normal provider close freezes at most one final candidate. Partial or abnormal close, including one after Metadata, creates no candidate.

### 3. One provider connection per capture makes failure ownership explicit

`CloseStream` is documented to process cached data, send remaining results plus summary metadata, and terminate the WebSocket.[7] A disrupted Deepgram connection requires a new WebSocket session; buffered audio can be lost or delayed, send rate is capped at 1.25× real time, and timestamps restart at zero.[9]

**CONFIRMED — two provider primary documents plus deterministic trace M1.** An active capture is never reconstructed across a provider/control/audio disconnect. The attempt becomes failed, memory partials are discarded, old-generation events are ignored, and the UI offers explicit Retry or Type. A new press receives a new capture ID. Fake-provider traces for disconnect and Metadata-then-abnormal-close produced zero candidates/drafts, while a complete event and its `InputAttempt.candidate_event_id` were persisted together before a simulated restart replayed the same R4 receive once.[M1]

### 4. The exact audio profile is supported, but browser fulfillment remains unmeasured

Deepgram requires explicit encoding and sample rate for raw/headerless audio and defines `linear16` as signed 16-bit little-endian PCM.[11] Its latency guide says chunk size trades buffering delay for overhead and recommends 20–100 ms streaming buffers.[18] The W3C capture specification exposes sample/channel/echo/noise/AGC constraints and actual settings, but non-required constraints are not guaranteed.[16] Web Audio defines `AudioWorkletNode`/`AudioWorkletProcessor` for audio processing in a worklet scope.[17]

**CONFIRMED for protocol capability; UNCERTAIN for target devices.** The MVP protocol chooses mono linear16/16 kHz/little-endian and normal 20 ms (640-byte) frames. Twenty milliseconds is an engineering profile, not a user latency target. Actual/resampled device output, scheduler stability and backpressure bounds require later browser measurements.

### 5. Russian streaming capability exists now but acoustic quality is unknown

Deepgram's current model table lists Nova-3 Russian `ru` and says models otherwise default to English unless language is specified.[12]

**LIKELY — current provider primary documentation, not a real account/room measurement.** The request must set `model=nova-3&language=ru` explicitly and recheck availability at implementation. No claim is made about D&D vocabulary, multi-person room accuracy, echo or distance.

### 6. Speech remains an approval-gated input, including physical rolls

R4's coordinator contract makes immutable draft versions, current approval, dedupe and one typed kernel command the only mutation path.[2] The product requires speech transcription to be corrected/approved and physical results to bind to the current pending roll rather than treating any number as a roll.[1]

**CONFIRMED — primary local contracts plus deterministic trace M1.** `speech.finalized` calls idempotent R4 `receive:{capture_id}`; correction creates v+1 and invalidates the old nonce; only exact current approval executes. The fake traces produced zero world mutations from speech alone, rejected `У меня 17 стрел`, accepted explicit `Бросок — 17` as a candidate, used structured `roll.declared_correct` to set 18, rejected stale draft and pending-roll revision approvals, and committed exactly once under duplicate current approval.[M1] This captures a declaration, not honesty.

### 7. Barge-in is an audio fence, never a game rewind

R7 assigns the active audio lease/fence to server state and does not allow a client to name arbitrary cancellation targets.[4] R4 commits game state independently from presentation.[2]

**CONFIRMED — local primary interface contracts plus deterministic trace M1.** PTT down first drops local buffered playback; accepted admission makes the VPS resolve and cancel the current line/context, increment the fence, and reject late chunks. It never calls or replays the kernel. The synthetic trace fenced the exact active playback while leaving world mutations at zero.[M1]

### 8. “No app recording” is enforceable; “zero provider retention” is not supported

The application can specify no raw/interim fields in durable records and can exclude content from logs. Deepgram's request parameter `mip_opt_out` defaults to false, so opt-out must be explicit.[5] Deepgram documents request/log visibility for up to 90 days.[13] Its privacy notice says customer-data retention/storage/deletion follows the business agreement and describes Deepgram as processor/customer as controller for GDPR purposes.[14] An EU endpoint is available.[15] A separate getting-started page says Deepgram does not store transcripts, which is narrower than the account-level customer-data language.[19]

**CONFIRMED — multiple provider primary sources reveal the qualification, and M1 validates only the local fake-record shape.** The product may promise no application recording: raw PCM and interim text are memory-only and absent from DB/file/log/backup, with final reviewed text following campaign retention. It must not promise generic zero provider retention. Real audio is blocked pending consent plus an exact account/DPA/region/model-improvement/request-log/content-retention/deletion snapshot.

### 9. Wake word is not an MVP transport mode

The product makes PTT mandatory and wake word optional, while the AI must not continuously intrude.[1]

**CONFIRMED — fixed product fact.** MVP clients emit only `activation_source=ptt`. A later detector may emit the same untrusted activation locally only when an allowed actor is already selected; ambient audio must remain on device and PTT remains. A cloud/server wake listener would be a new privacy/product decision.

### 10. No numeric latency promise is justified

The product sources provide no numeric user target.[1] Deepgram recommends client-side end-to-end measurement, distinguishes transcript lag from end-of-turn latency, and says its published ranges vary by network, acoustic environment and setup; it recommends percentile reporting.[18]

**CONFIRMED that the budget must be symbolic; UNCERTAIN for all numeric performance.** The protocol names monotonic spans from PTT down through capture, admission, provider open/interim/finalize, R4 draft and R7 render. A later authorized paired route experiment must freeze its usability/non-inferiority threshold before data, alternate the same cleared traces, and report failures plus p50/p95. Provider marketing ranges are context, not acceptance criteria.

## Provider/browser capability evidence matrix

| Capability | Primary evidence | Contract implication | Confidence |
|---|---|---|---|
| Live auth and result envelope | `/v1/listen` accepts API key or JWT; result includes `start`, `duration`, `is_final`, `speech_final`, `from_finalize` and request metadata.[5] | VPS uses a server-only key; assembler binds request/capture/generation. | CONFIRMED |
| Browser-direct auth | Temporary JWT default TTL is 30 s, valid only for initial WS connection, with broad `usage::write` voice API coverage; browser WS may carry it in `Sec-WebSocket-Protocol`.[5][10] | Direct is possible but has extra token issuance, scope and redaction gates. | CONFIRMED |
| Interim/final segmentation | Interim may change; multiple `is_final` segments must be concatenated; `speech_final` alone is insufficient.[6] | Interim never reaches core; finals are deduped; release is boundary. | CONFIRMED |
| Terminal capture close | `CloseStream` finishes cached audio, returns results and summary Metadata, then terminates.[7] | One provider WS per capture; Metadata is necessary and the subsequent normal close is the terminal oracle. | CONFIRMED |
| Warm-stream flush | `Finalize` normally signals `from_finalize` but the signal is not guaranteed with little buffered audio.[8] | Reject warm shared stream until another measured fence exists. | CONFIRMED |
| Reconnect | New connection/session is required; loss/delay and timestamp reset must be handled.[9] | Fail active attempt; no silent resume or replay. | CONFIRMED |
| Keepalive | Idle streams need text KeepAlive every 3–5 s to avoid a 10 s timeout.[20] | Another reason not to keep a warm MVP stream; per-capture watchdog still handles provider-open silence. | CONFIRMED |
| Raw audio | Raw packets require encoding/sample rate; linear16 is 16-bit little-endian signed PCM.[11] | Closed mono/16 kHz/linear16 wire profile; validate every frame. | CONFIRMED |
| Russian | Nova-3 lists `ru`; default language is English without an explicit value.[12] | Pin `language=ru`; revalidate model/account and measure acoustics. | LIKELY |
| Browser capture | Constraints and actual settings exist; ideal/non-required constraints are not guaranteed.[16] | Request echo/noise/AGC, record actual settings, fail unsupported profile. | CONFIRMED |
| Processing | AudioWorklet defines a separated audio-processing scope.[17] | Prefer worklet PCM extraction over irregular recording blobs; still benchmark. | CONFIRMED |
| Privacy/region/logs | Explicit MIP opt-out exists; request logs may be visible 90 days; customer-data terms are contractual; EU endpoint exists.[5][13][14][15] | No zero-retention claim; require consent/account evidence before real audio. | CONFIRMED |

## Counter-evidence and unresolved uncertainty

- Deepgram itself presents temporary-token direct access as useful for latency-sensitive untrusted clients.[10] The selected proxy adds a real network relay and transient VPS audio exposure. No measurement currently shows that this cost is negligible.
- A per-capture provider connection pays connection setup. A warm stream could be faster; it is rejected only because the available terminal marker is weaker, not because it was measured slower.
- Provider documentation that “does not store transcripts”[19] argues for a narrow low-retention interpretation, while the provider privacy notice makes customer-data treatment agreement-specific[14] and request logs exist[13]. The conservative contract preserves both facts instead of silently choosing the convenient one.
- Synthetic traces now cover admission idempotency/rejection, duplicate/conflicting finals, cancellation, Metadata-then-abnormal-close, atomic candidate reference, ready restart replay, roll revision/correction and duplicate approval. They still cannot validate provider conformance, recognition quality, browser audio behavior, reverse-proxy logging or real database crash recovery.[M1]
- Physical roll marker/parser vocabulary, integer domain, capture-duration cap, queue/backpressure cap, retry UX, supported browser versions and the numeric route gate remain inputs to the later implementation/authorized experiment. Inventing values in Phase 1 would hide product decisions.

## Falsification/release gates

The authoritative detailed list is in `speech-input-protocol.md §15`. The load-bearing gates are zero audio outside accepted activation; actor/purpose immutable after admission; zero browser provider credential on the proxy route; no interim/partial/abnormal-close submission; no duplicate final/draft/approval; no reconnect/restart replay; ordinary numbers never become rolls; speech and barge-in never mutate game state; no raw audio or interim text in durable/log/backup paths; and no real participant audio before consent plus provider-account evidence.

Failure of any correctness/privacy gate blocks voice and leaves authenticated typed input as the MVP fallback. Proxy latency alone can reopen route selection only after a paired experiment with a threshold frozen before observation; speed never waives correctness.

## Interfaces and affected future surfaces

- **R4 coordinator:** internal `speech.finalized`; deterministic `receive:{capture_id}`; immutable `draft.correct` and structured `roll.declared_correct`; current-version approval; dedupe before stage checks. The complete schema-valid event and the attempt's `candidate_event_id`/`ready` state are persisted in one local transaction before the idempotent R4 call, so restart loads the exact payload and retries by identity rather than share a cross-component transaction.
- **Unified core:** read-only `pending_roll_for_actor(actor_id)` and approved `declare_physical_roll{pending_roll_id,actor_id,declared_total,approved_draft_version}`; deterministic, locale-versioned parser; one-time consumption.
- **R7:** table/composite capabilities and projections for capture health, provisional/finalizing/review/error/typed fallback; closed JSON control messages plus separate `room-input.v1` binary socket; scene gets no player speech; admin gets safe enums/timing only; reconnect never resends active capture or commands.[4]
- **R6 audio:** internal `cancel_current_for_input(room_id,capture_id)` resolves the current provider line/context, increments the server fence, stops clients, and never changes world state.

No future product file, private repository, provider account, deployment or production state was created or changed in this phase.

## Review gate inputs

- **Changed artifacts:** `research.md`, `requirements-alternatives-matrix.md`, `speech-input-protocol.md`, `protocol-schemas.json`, `synthetic_probe.py`, `test_synthetic_probe.py`, and `probe-results.md`. Future consumers are the browser capture/room-input client, VPS speech adapter/provider socket, R4 coordinator, unified core pending-roll API, R7 table/composite projections and reconnect, R6 audio fence, and operations/privacy configuration.
- **Author metadata:** `gpt-5.6-sol`, Orchestra full-cycle worker runtime (`research-room-input`), as reported by the live agent registry on 2026-08-16.
- **Acceptance criteria:** compare all viable routing/lifecycle alternatives; select or explicitly gate a route; specify activation/actor binding, codec/framing, interim/final terminal semantics, correction/approval, declared physical roll, barge-in, privacy/retention, reconnect/restart/fallback, wake-word deferral, latency instrumentation without an invented target, provider capability evidence, deterministic synthetic falsification, and explicit R4/core/R7/R6 interfaces; make no paid/real provider call and no product/deployment mutation.
- **Named mechanical check:** `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT uv run --project /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-room-input --frozen pytest -p no:cacheprovider -q docs/tasks/377/phase3/r5/test_synthetic_probe.py` → `3 passed in 0.13s`. `python -m json.tool` under the same frozen project prefix exited 0 for `protocol-schemas.json`; two probe processes were byte-identical.
- **Routing:** high-risk floor applies because this research defines an externally consumed protocol plus auth/privacy/persistence/admission boundaries. The deterministic probe was authored with the artifact and is not an independent oracle. Canonical route: one targeted Sol review; no skip/Luna substitution.

## Sources

Local primary inputs:

1. `docs/tasks/377/mvp-product-spec.ru.md` and `docs/tasks/377/research.md` — fixed MVP/product facts.
2. `docs/tasks/377/phase3/r4/coordinator-adr.md`, `state-machine.md`, `fault-matrix.md` — merged coordinator authority, idempotency and draft/approval behavior.
3. `docs/tasks/377/phase3/r8/remote-authority-threat-model.md` — merged room/role/actor/session authority and logging boundary.
4. Read-only old R7 evidence: `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-three-surfaces/docs/tasks/377/phase3/r7/surface-contract.md`, `reconnect-cursor-protocol.md`, `wireflows.md`, `capability-matrix.md`.

External primary sources, all fetched 2026-08-16:

5. Deepgram, [Live Audio API reference](https://developers.deepgram.com/reference/speech-to-text/listen-streaming).
6. Deepgram, [Configure Endpointing and Interim Results](https://developers.deepgram.com/docs/understand-endpointing-interim-results).
7. Deepgram, [Close Stream](https://developers.deepgram.com/docs/close-stream).
8. Deepgram, [Finalize](https://developers.deepgram.com/docs/finalize).
9. Deepgram, [Recovering From Connection Errors & Timeouts](https://developers.deepgram.com/docs/recovering-from-connection-errors-and-timeouts-when-live-streaming-audio).
10. Deepgram, [Token-Based Auth](https://developers.deepgram.com/guides/fundamentals/token-based-authentication).
11. Deepgram, [Encoding](https://developers.deepgram.com/docs/encoding).
12. Deepgram, [Models & Languages Overview](https://developers.deepgram.com/docs/models-languages-overview).
13. Deepgram, [Logs & Usage Data](https://developers.deepgram.com/docs/using-logs-usage).
14. Deepgram, [Privacy Policy](https://deepgram.com/privacy).
15. Deepgram, [Data Privacy Compliance](https://developers.deepgram.com/trust-security/data-privacy-compliance).
16. W3C, [Media Capture and Streams](https://www.w3.org/TR/mediacapture-streams/).
17. W3C, [Web Audio API](https://www.w3.org/TR/webaudio-1.0/).
18. Deepgram, [Measuring STT Latency](https://developers.deepgram.com/docs/measuring-streaming-latency).
19. Deepgram, [Getting Started with Live Streaming Audio](https://developers.deepgram.com/docs/live-streaming-audio).
20. Deepgram, [Audio Keep Alive](https://developers.deepgram.com/docs/audio-keep-alive).

Measurements:

- **M1:** `probe-results.md`, `synthetic_probe.py`, `test_synthetic_probe.py`, and `protocol-schemas.json` in this directory. The final run was 3/3 tests, 26/26 checks, nine attempts, four drafts, zero pre-approval world mutations, one declared-roll commit, two ignored late events, zero network/provider calls and zero raw-audio files.
