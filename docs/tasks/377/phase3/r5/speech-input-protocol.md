# R5 reliable room speech-input protocol

- Status: selected MVP contract from Phase 1 research; implementation and real-room validation remain gated
- Selected capture route: browser → authenticated VPS speech proxy → one Deepgram WebSocket per PTT capture
- Activation: mandatory per-character press-and-hold `Мастер`; wake word deferred
- Identity model: logical character selection only; no diarization or physical-speaker identity
- Authority: speech produces an unapproved R4 draft input; only the existing versioned approval route may reach the game kernel

## 1. Observable contract

For one accepted activation:

> one server-bound actor + one capture ID + one ordered audio stream → zero or one immutable final input; any partial, ambiguous, stale, disconnected, or conflicting stream → zero inputs and an explicit retry/type fallback.

Speech input itself performs zero world mutations. Provider events, browser messages, transcript text, and detected numbers are data. The R4 coordinator remains the only path from a reviewed current draft to an internal typed kernel command.

## 2. Topology and trust boundaries

```text
per-character PTT button / selected actor
          |
          | input.capture.start (R7 authenticated room.v1 control socket)
          v
VPS input admission ---- server session actor allowlist + pending-roll lookup
          |                         |
          | capture accepted        +-- internal R6/R7 audio fence for barge-in
          v
room-input.v1 binary socket --------+------> per-capture Deepgram /v1/listen WS
          |                                      |
          | ordered PCM + input.audio.end        | interim/final/Metadata
          v                                      v
      VPS final assembler ----------------> durable final candidate
                                                   |
                                                   | idempotent R4 receive
                                                   v
                                     draft vN → correct/retry/approve
                                                   |
                                                   | current approval only
                                                   v
                                            unified game core
```

The browser never receives a Deepgram key or token on the selected route. The VPS authenticates to Deepgram with a server-only credential. The room audio WebSocket is separate from R7 projection/control traffic so audio backpressure cannot advance or block a projection cursor. It uses the same R8 session, exact Origin allowlist, single-use purpose ticket, and per-message/session revalidation. Neither room nor bearer appears in a URL.

## 3. User activation and actor binding

1. Before play, the admin diagnostics flow requests microphone permission over HTTPS, enumerates the selected input only after permission, and records the actual `MediaStreamTrack.getSettings()` values as enum/number diagnostics. Requested constraints are not assumed to have been honored.
2. Each allowed hero has a focusable `Мастер` button. Primary pointer down or keyboard Space/Enter begins; pointer/key release ends. Pointer cancel, lost capture, page hide, device end, or socket loss aborts.
3. The browser stops its current audio buffer locally before forwarding microphone samples. It sends `input.capture.start` with a requested `actor_id`, activation source, command ID and expected aggregate version. It sends no room, role, surface, purpose or pending-roll ID.
4. The VPS loads the R7 session and actor allowlist. It binds the actor, mints `capture_id`/`turn_id`/generation, reads the current pending roll, chooses `purpose=action|declared_roll`, persists an `armed` attempt, and returns `input.capture.accepted` plus a single-use audio-socket ticket.
5. Only the accepted capture can open `room-input.v1`. Actor/purpose cannot change after admission. A same-command retry returns the stored `input.capture.accepted|rejected` result; same ID/different body is an idempotency conflict. Rejection has no capture ID or audio ticket.
6. Ordinary room speech creates no capture, audio socket, provider stream, interim text or draft.

Wake-word activation is present in the schema only to keep a future adapter from inventing a second path. MVP clients emit only `activation_source=ptt`.

## 4. Capture and wire format

The browser uses `getUserMedia({audio:{channelCount:{ideal:1}, echoCancellation:true, noiseSuppression:true, autoGainControl:true}})` and an `AudioWorklet` to produce the selected protocol profile:

| Field | MVP value | Status |
|---|---:|---|
| encoding | `linear16` signed PCM | Deepgram-supported raw encoding; explicit request parameter |
| endianness | little | Deepgram `linear16` definition |
| sample rate | 16,000 Hz | supported provider/browser-SDK profile; target hardware must verify actual/resampled output |
| channels | 1 | canonical one-microphone product input |
| normal frame | 20 ms / 640 payload bytes | protocol choice, not a latency target; real browsers must measure scheduling/backpressure |

Every binary message has the 36-byte header in `protocol-schemas.json`: `R5A1`, 16-byte capture UUID, generation, frame sequence, browser monotonic timestamp, then little-endian samples. Server checks capture/generation/contiguous sequence/non-empty even payload/profile before forwarding only the PCM payload to Deepgram.

The browser keeps only an in-memory queue while the audio/provider sockets open or experience backpressure. The implementation must declare and enforce capture-duration, queued-byte and provider-open bounds before a real-room run; this research does not invent those numeric product limits. Exceeding any bound aborts instead of spilling audio to disk.

The server opens a separate Deepgram Nova streaming request for each capture with an explicit versioned configuration equivalent to:

```text
/v1/listen
  ?model=nova-3
  &language=ru
  &encoding=linear16
  &sample_rate=16000
  &channels=1
  &interim_results=true
  &endpointing=false
  &punctuate=true
  &smart_format=true
  &mip_opt_out=true
```

`nova-3` currently documents Russian `ru` support, but model/config availability and recognition quality must be rechecked and measured before implementation. PTT release is the only utterance boundary; `speech_final`/`UtteranceEnd` may improve UI feedback but never split or submit a held capture.

## 5. Input-attempt state machine

```text
                valid audio socket + first frame
 armed ------------------------------------------> capturing
   |                                                   |
   | timeout/socket loss/cancel                        | ordered input.audio.end(released)
   v                                                   v
 failed/cancelled                                  finalizing
                                                       |
                           abnormal close/conflict     | final segments + terminal Metadata
                                      |                v
                                      +----------->  ready
                                                       |
                                                       | candidate already persisted;
                                                       | idempotent R4 receive, then stored ack
                                                       v
                                                   submitted
```

Durability uses two closed records from `protocol-schemas.json`: `$defs.InputAttempt` and the full `$defs.SpeechFinalized` event. In one local database transaction, the adapter inserts `SpeechFinalized` by `event_id`, sets `InputAttempt.candidate_event_id` to that row, and changes the attempt to `ready`. The event contains the exact text, final/segment/provider identities and frozen authority fields needed to reconstruct the R4 request. `InputAttempt` contains no raw audio or interim text; `ready|submitted` requires a non-null candidate reference, while every pre-ready/failed/cancelled state requires null.

| State on process restart | Recovery |
|---|---|
| `armed`, `capturing`, `finalizing` | mark `failed/server_restart`, discard memory, show retry/type; do not reconnect provider or submit partial |
| `ready` with referenced, schema-valid `speech.finalized` | load the event by `candidate_event_id`, verify all duplicated authority/identity fields against the attempt, then issue the same R4 `receive`; exact retry returns stored result |
| `submitted` | read the stored R4 command result/current draft; never resubmit a new turn |
| `failed`, `cancelled` | terminal; a user action creates a new capture ID |

## 6. Interim, final and terminal semantics

- `is_final:false`: overwrite an in-memory provisional string for optional captions. It is never logged, persisted, sent to R4, parsed as a roll, or retained across reconnect.
- `is_final:true`: append one immutable segment keyed by `(provider_request_id,start,duration,channel_index)`. Exact duplicate is a no-op. Same key/different text is `conflicting_final_segment` and fails the capture.
- `speech_final:true` or `UtteranceEnd`: pause evidence only. Multiple such events may occur while the player still holds PTT.
- `input.audio.end(released)`: ordered after the last PCM frame on `room-input.v1`; VPS sends Deepgram `CloseStream`.
- Deepgram terminal `Metadata` is necessary but not sufficient. Only the subsequent normal provider close freezes the complete set. Concatenate final segments by audio position, discard empty segments, then atomically persist one `speech.finalized` event plus the attempt's `candidate_event_id`/`ready` transition. Metadata followed by abnormal close fails and discards partials. A `from_finalize` result is not the terminal oracle because Deepgram says it is not guaranteed when little audio is buffered.
- Provider error, abnormal close, missing Metadata, request-ID change, frame gap, empty final, or server/client disconnect: fail and discard every partial. Late events for failed/old generations are audited by IDs/error enum and ignored.
- Pointer/key cancellation emits ordered `input.audio.end(reason=cancelled)` when possible, stores terminal `cancelled`, returns `input.capture.cancelled`, and never asks Deepgram to finalize a candidate.

The stable internal handoff uses:

```text
turn_id              = server-minted value returned at capture admission
command_id           = receive:{capture_id}
event_id             = speech-final:{capture_id}
final_transcript_id  = transcript:{capture_id}:1
```

Text or content hashes are not identities. The R4 dedupe lookup occurs before stage/version checks.

## 7. Draft review, correction and approval

For an action capture, `speech.finalized` invokes R4 `receive` and the model/deterministic normalizer creates the canonical human-readable card. R5 does not add a second approval state.

- **Approve:** the existing R7/R8 body remains only `turn_id`, current `draft_version`, and current single-use approval nonce. No actor/room/plan/command/arguments may be supplied.
- **Correct action text:** R7 message `draft.correct{command_id,turn_id,expected_draft_version,replacement_text}` creates immutable version `v+1`, invalidates the former nonce, and returns to `awaiting_approval`.
- **Correct a declared total:** `roll.declared_correct{command_id,turn_id,expected_draft_version,pending_roll_id,declared_total}` supplies a structured integer for the current roll draft. Server session owns room/actor; turn and pending-roll identity must match; the operation creates v+1 and rotates the nonce. Generic replacement text cannot correct a roll.
- **Repeat:** reject the current draft, keep its audit identity, and create a fresh PTT capture/turn. No old audio or partial transcript is replayed.
- **Duplicate/stale:** exact duplicate returns the stored result; same command ID with another body is an idempotency conflict; stale version/nonce is a stored rejection.

The table projection must visibly distinguish provisional caption, finalizing, draft awaiting review, retryable input failure and disconnected/typed fallback. Provisional text must never look approved.

## 8. Physical declared-roll contract

R5 never decides that a number is a roll from text alone.

1. At capture admission, the server asks unified core for the current player-visible `pending_roll` for the bound actor. If present, the attempt freezes `{pending_roll_id, actor_id, expected_aggregate_version}` and purpose `declared_roll`; otherwise purpose is `action`.
2. A declared-roll transcript must contain an explicit locale marker such as `бросок` or `результат` and exactly one deterministically parsed integer total. Provider smart formatting is not trusted to supply the integer; the locale-versioned parser and closed `roll.declared_correct` control handle the value.
3. `У меня 17 стрел` has no marker and produces `unrecognized_roll_declaration`, not a roll or action draft. Ambiguous/multiple/out-of-parser values also require retry or structured correction.
4. The server builds `roll.declared_candidate{pending_roll_id,actor_id,declared_total,draft_version,source_final_transcript_id}`. It does not validate honesty.
5. Correction creates a new immutable version. Approval rechecks the same current pending roll and aggregate/world version. The core consumes `pending_roll_id` once and returns the stored result on exact duplicate.

The pending-roll query and consumption are server/core interfaces. No browser field can create a pending roll, select its ID, supply a dice formula/DC/AC, or bypass review.

## 9. Interruption / barge-in

Pressing PTT is also an input-focus request:

1. The local table/composite audio controller immediately stops and drops its current buffer before forwarding microphone frames.
2. After `input.capture.start` admission, the VPS selects the current R7/R6 `line_id/context_id` from server state, closes further provider generation, increments the room audio fence, and sends `audio.stop` to all clients. The browser does not name an arbitrary line/context.
3. Late chunks with the old fence are dropped. The cancelled narration remains visible as text. Already committed game state is unchanged; interruption never calls or retries the kernel.
4. If authority is disconnected, the browser may stop local playback but cannot start a cloud capture or local game action. Typed/capture controls remain disabled until R7 rehydrates.

## 10. Failure and reconnect matrix

| Failure | User-visible state | Durable result | Recovery |
|---|---|---|---|
| permission denied / prompt ignored | microphone unavailable; typed input available | safe enum only | explicit diagnostics/retry; never loop prompts |
| no device / device unreadable / actual settings incompatible | microphone unavailable | safe enum and capture ID if admitted | select/fix device or type |
| control socket lost before admission | disconnected | no attempt | R7 rehydrate; new press only |
| audio socket fails/gaps/backpressure bound exceeded | input failed | attempt `failed`, no transcript/draft | discard memory; explicit retry/type |
| Deepgram handshake/provider error | provider unavailable | attempt `failed`, no transcript/draft | explicit retry/type; do not switch route mid-capture |
| disconnect after interim/final segment, after Metadata but before normal close, or on abnormal close | partial discarded | attempt `failed`, no candidate/draft | new capture; late provider event ignored |
| restart after persisted complete candidate but before R4 ack | finalizing/recovering | `ready` candidate | retry exact `receive:{capture_id}` |
| draft projection/render fails | prior safe R7 projection stays | R4 draft remains stored | R7 resync/reproject; do not recapture or execute |
| stale correction/approval/pending roll | visible conflict | stored rejection | rehydrate current card/roll; new version or capture |
| STT unavailable for the session | text-only degraded mode | no synthetic draft | authenticated final-text path preserves MVP play |

Neither the R7 reconnect nor provider reconnect auto-resends audio, approval, correction or a failed final. This intentionally chooses a visible retry over silent duplicate/partial submission.

## 11. Privacy, consent and retention

| Data | Application handling | Provider/third-party boundary |
|---|---|---|
| raw room PCM | memory only in active browser/VPS/provider buffers; never file, DB, log, trace, crash attachment, Git or backup; drop immediately on terminal/failure | transferred to Deepgram only during accepted PTT; `mip_opt_out=true`; applicable regional endpoint |
| interim transcript | memory-only provisional UI; no audit or persistence | transient provider response; never forwarded to model/core |
| final transcript and corrections | stored as the R4 versioned turn/draft input needed for review, idempotency and recovery; included in campaign deletion/export policy | Deepgram documentation says the transcript response is the retrieval point, but customer-data retention is governed by the account agreement; do not infer zero provider retention |
| operational metadata | IDs, byte/frame counts, monotonic spans, provider request ID, model/config version, enum errors, hashed session/device identity; no content | request/usage metadata may exist under provider/account terms |
| consent | record the disclosed processor, purpose, route, region, retention/deletion policy and every participant's consent before real room audio | real participant audio remains blocked until the DPA/account/retention snapshot is accepted |

Deepgram's API currently exposes `mip_opt_out=false` by default, so the adapter must set `true` explicitly and record the request configuration. Official documentation also exposes request logs for up to 90 days and says customer-data retention/deletion follows the business agreement. These facts prohibit a generic “zero retention” promise. Before the first real-room request, record the exact account plan, DPA/data-processing role, regional endpoint, model-improvement setting, content/request-log retention, deletion process and incident owner.

The browser shows a clear microphone-active indicator in addition to the browser's own permission indicator. No wake-word listener runs in MVP.

## 12. Latency budget and instrumentation (no invented target)

No numeric user latency target was supplied, and no real browser/VPS/provider call was authorized. The contract therefore fixes **spans and attribution**, not a pass number.

| Span | Clock / endpoints | What it isolates |
|---|---|---|
| `capture_local_start` | browser monotonic: PTT down → first PCM frame | permission reuse, audio graph/worklet startup |
| `control_admission` | browser monotonic: start send → accepted receive | room WS/VPS admission and pending-roll lookup |
| `audio_ingress_first` | server monotonic: accepted → first valid PCM | audio-socket ticket/handshake plus browser→VPS path |
| `provider_open` | server monotonic: provider connect start → open | DNS/TCP/TLS/WS/provider handshake |
| `first_interim` | browser end-to-end and server subspans | early feedback only; never authorization |
| `audio_tail` | server monotonic: ordered audio end received → last PCM forwarded | queue/backpressure at release |
| `provider_finalize` | server monotonic: `CloseStream` send → terminal Metadata | STT tail/finality |
| `candidate_to_draft` | server monotonic: candidate commit → R4 draft commit | assembler, normalizer/model and persistence |
| `draft_projection` | server/browser correlated IDs: outbox ready → successful visible render/ack | R7 delivery/reducer/render |
| `release_to_draft_visible` | same browser monotonic: PTT release → card visible | user-observed system total |
| `transcript_lag` | provider-recommended audio cursor minus latest transcript cursor | streaming backlog independent of wall-clock sync |

Human speaking duration, time spent reading/editing the card, and approval decision time are reported separately and are not hidden inside provider latency.

The later authorized room experiment must alternate browser-direct and proxy paths over the same cleared utterance/noise/network matrix; record all raw spans; report failures plus p50/p95 distributions; freeze the numeric usability/non-inferiority gate before observing results; and never select a route by a provider marketing number or mean alone. Correctness/security gates below remain zero-tolerance regardless of speed.

## 13. Required interfaces to R4, unified core, R7 and R6

### R4 coordinator

- Accept internal `speech.finalized` only from the server speech adapter.
- Use `turn_id` and `receive:{capture_id}` exactly; dedupe before current-stage/version checks.
- Persist final input/draft and return a stored result before R5 marks `submitted`.
- Implement `draft.correct` and structured `roll.declared_correct` as immutable v+1 operations; invalidate the former nonce.
- Recover `ready` only by loading its referenced immutable `speech.finalized`, validating the attempt/event identity tuple, and retrying `receive:{capture_id}`; never reconstruct text from attempt metadata.
- Provider/audio retry and failure never call `commit_world`.

### Unified core

- Read-only `pending_roll_for_actor(actor_id)` returns the public request identity/version/allowed total domain needed by input admission; it exposes no secret DC/plan field not already disclosed by product rules.
- The approved typed command `declare_physical_roll{pending_roll_id,actor_id,declared_total,approved_draft_version}` consumes the pending roll once under expected revision and returns the stored result on duplicate.
- The parser is deterministic and locale-versioned. Model output may suggest a parse but cannot authorize it.
- Honesty and physical-speaker identity remain out of scope.

### R7 surfaces/transport

- Add table/composite-only capabilities `input.capture`, `draft.correct`, `roll.declared_correct`, and `draft.repeat`; scene/admin cannot invoke them.
- Add closed JSON messages from `protocol-schemas.json` to the control contract and a separately commissioned `room-input.v1` binary socket. Server context owns room, role, consumer and allowed actors.
- Table projection adds input health/state, provisional caption visually marked as provisional, current bound actor, finalizing/error/typed fallback, and a declared-roll review card. Scene receives none of the raw/interim/final player speech. Admin receives enums/timing buckets only, never text/audio/provider tokens.
- R7 reconnect restores stored R4 draft/input health but never resumes an active capture or resends a client command.
- PTT barge-in calls the server-owned R7 audio fence; it does not grant table `audio.cancel` over arbitrary IDs.

These are behavioral requirements for the future private repository. The old R7 worktree is evidence only and was not modified.

### R6 output/audio

- Expose an internal `cancel_current_for_input(room_id,capture_id)` operation that resolves the current `line_id/context_id`, closes provider generation, increments the fence and broadcasts stop.
- Return only an idempotent safe result to R5. Cancellation never changes game state and late chunks are rejected by the new fence.

## 14. Optional later wake word

Wake word is deliberately omitted from MVP. A later experiment may add a local browser/WASM detector behind the same `input.capture.start` event only if:

- ambient audio never leaves the device before activation;
- a server-known allowed actor is already selected; otherwise detection only prompts for selection and opens no cloud stream;
- PTT remains present and fully functional;
- the detector/version/model and local CPU/memory are disclosed;
- false activations, misses, barge-in behavior, room speaker echo, noise and reconnect are measured on a consented/cleared room corpus with thresholds frozen before scoring.

A server/cloud wake-word listener would continuously transfer room speech and contradicts the selected privacy/AI-nonintrusion boundary; it requires a new explicit product/privacy decision, not a quiet adapter change.

## 15. Falsification and release gates

### Hard correctness/security gates

Any one stops I2/release:

- audio bytes without an accepted PTT/wake activation;
- actor/purpose changes after capture admission or cross-room/disallowed actor acceptance;
- any long-lived provider key or temporary provider token in the selected proxy browser, URL, storage, trace or log;
- interim/partial/abnormal-close transcript reaching R4;
- duplicate/conflicting final producing more than one input;
- reconnect/restart auto-submitting audio, approval or correction;
- ordinary numeric speech becoming a roll, stale pending roll accepted, or duplicate approval recording twice;
- raw audio written to disk/log/backup/Git or transcript/token in operational logs;
- speech/cancel/retry invoking the kernel before exact current approval;
- real participant audio without recorded consent and provider retention/account evidence.

### Route-reopening gates

Keep the proxy if it passes correctness and no numeric product target exists. Reopen browser-direct only when a paired, predeclared real-room experiment shows the proxy misses the frozen usability/latency/reliability gate, browser-direct meets it, and browser-direct also passes token scope/expiry/redaction, cross-browser auth, finality, reconnect and no-partial oracles. If both routes fail, voice remains blocked and authenticated typed input is the MVP fallback.

### Wake-word gate

No real-room corpus/threshold/consent evidence → omit. Any false-activation/miss/privacy/actor-binding/demo-complexity gate failure → omit. Omission never removes PTT.
