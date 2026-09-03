# R6 exact audio and playback contract

Contract ID: `r6.audio.v2`. This is a research contract for future I6 code. Endpoint names and byte framing may change only if the fields, state transitions, identity rules, control barrier, and observable oracles below stay equivalent.

## Authority boundaries

1. The unified server core owns committed `turn_id`, `world_revision`, `presentation_id`, disclosed `text_event_id`, combat/scene events, and `music_state`.
2. The audio router owns line resolution, explicit voice/cache choice, provider generation attempts, cancellation epoch, cost/latency observations, and fallback outcome. It cannot call the game kernel.
3. ElevenLabs produces bytes for one server-selected cleared voice/model/context. It authorizes no state, routing, retry, or playback decision.
4. R7 owns the sole playback lease `(room_id, lease_id, lease_generation, consumer_id)`. Only that consumer may receive a playable speech, SFX, or music `media_ref`/chunk.
5. The browser leader owns the actual Web Audio graph and its bounded buffers. A server/provider status never proves that already delivered samples are silent.

Audio is post-commit and degradable. The caption/player-safe projection is publishable without audio, and a failed/cancelled/retried line never reopens `executing` or changes `world_revision` [L1][L2].

## Identity model

| Field | Created by | Lifetime and equality rule |
|---|---|---|
| `turn_id` | unified coordinator | immutable game-turn identity; never created/reused by audio |
| `presentation_id` | R4/R7 presentation outbox | one committed safe presentation; reproject gets new delivery IDs but does not create a new audio presentation |
| `text_event_id` | safe projection builder | exact disclosed caption/narration source; required before TTS |
| `line_id` | audio router | stable semantic speech-line identity, unique in room; survives provider/playback retry; never a text hash |
| `context_id` | TTS/local adapter | one generation attempt. Provider retry creates a new context. Cached playback uses a `local:` context so the same cancel code path applies |
| `generation_attempt` | audio router | monotonic per line; changes with provider generation retry |
| `playback_attempt_id` | audio router | monotonic per line; changes only for explicit replay/retry, not network redelivery |
| `media_id` / `media_ref` | audio media store/relay | immutable bytes/stream for one generation or approved cached asset |
| `chunk_seq` | media relay | starts at 1 within `context_id`, contiguous and monotonic; duplicate/lower sequence is a no-op |
| `event_id` | durable/app delivery layer | stable transport effect identity; a replay/live duplicate has the same ID and renders once |
| `audio_fence` | audio router / control reducer | monotonic per room; server increments it before cancel/pause/end/lease-loss control. Client `applied_control_fence` advances only after an authenticated control/stop/snapshot has synchronously performed its scoped clear; media never advances it |
| `lease_generation` | R7 lease service | monotonic playback-owner fence; independent from `audio_fence` |
| `operation_id` | admin/server control caller | idempotency identity for cancel/retry/volume/state change; exact replay returns stored result |

Payload text, audio hashes, provider request IDs, and timestamps are never dedupe identity. A deliberate repeat of the same words gets a new `line_id` or `playback_attempt_id` as appropriate.

## Mandatory client control barrier

Every commissioned client keeps `applied_control_fence`, initially obtained from an authenticated audio control snapshot. **No speech, chunk, SFX, or music handler may change it.** Media is playable only when its `audio_fence == applied_control_fence` and its exact lease/generation/consumer and other identities pass. Media with a lower fence is stale and dropped.

Media at `applied_control_fence + 1` is future-fence media. It may be retained only in a non-playing, non-decoded `future_control_wait` queue. It cannot enter the AudioWorklet ring, create/start an `AudioBufferSourceNode`, fetch a leader-scoped asset body, change gains/music state, or mark its event applied. The queue is exact and bounded:

- only the single next fence is eligible; a larger gap is rejected;
- at most `16` envelopes, `256 KiB` total retained bytes, and `250 ms` of streamed-speech chunks;
- asset-backed music/SFX/cache entries retain envelopes/media references only; their bytes are not fetched before the barrier;
- maximum monotonic wait is `250 ms`.

A gap, timeout, or bound overflow discards the whole future queue and emits `audio.control_gap`; the media remains silent and the server returns an authoritative control snapshot. Current-fence old media is not changed merely by future media or gap detection; an independent lease deadline still stops it fail-silent when applicable.

Only `audio.stop`, lease/pause/end control, or `audio.control_snapshot` may advance the fence. The client applies one control in a synchronous reducer transition:

1. close media admission;
2. validate control identity and next fence (`audio.control_snapshot` alone may authoritatively jump a gap);
3. perform the entire scoped clear while `applied_control_fence` still has its old value;
4. set `applied_control_fence` to the control fence;
5. drain only matching queued media whose lease remains current, in priority/FIFO order, then reopen admission.

Thus reordered fence `N+1` media cannot overlap fence `N` audio: old media remains until the control arrives; the control clears old media first; only afterward can buffered/replayed fence `N+1` media start.

## Server-side `SpeechLine`

The durable line record is exact:

```json
{
  "schema_version": 1,
  "room_id": "room-1",
  "turn_id": "turn-9",
  "world_revision": 17,
  "presentation_id": "presentation:turn-9:17",
  "text_event_id": "text:turn-9:1",
  "line_id": "line:presentation-turn-9-17:1",
  "speaker": {
    "role": "narrator",
    "entity_id": "narrator:severin",
    "archetype": null
  },
  "source": "tts",
  "text_ref": "safe-text:text:turn-9:1",
  "voice_key": "narrator.severin",
  "provider": "elevenlabs",
  "provider_voice_id": "server-only-reference",
  "model_id": "eleven_flash_v2_5",
  "asset_id": null,
  "context_id": "ctx:line-presentation-turn-9-17-1:a1",
  "generation_attempt": 1,
  "playback_attempt_id": "play:line-presentation-turn-9-17-1:a1",
  "status": "generating",
  "priority": 80,
  "audio_fence": 6,
  "replay_policy": "explicit_only",
  "retention": {
    "policy_id": "owner-approved-value-required",
    "text_expires_at": "owner-approved-value-required",
    "generated_media_expires_at": "owner-approved-value-required",
    "attempt_telemetry_expires_at": "owner-approved-value-required",
    "deletion_disposition_id": "owner-approved-value-required",
    "withdrawal_inventory_id": "inventory:line-presentation-turn-9-17-1"
  }
}
```

Required enums:

- `source`: `cache | tts | text_only`.
- `status`: `pending | generating | ready | playing | completed | cancel_requested | cancelled | interrupted | failed_text_only`.
- `speaker.role`: `narrator | npc | enemy` (player speech is never synthesized).
- `replay_policy`: only `explicit_only` in MVP.

Provider voice/model IDs and rights references are server-side. `SpeechLine` keeps a reference to the authoritative retained safe caption rather than a duplicate plaintext field. The adapter materializes plaintext in memory only after the disclosure, rights, retention, and lease gates pass, then releases it after the provider request. An explicit retry may rejoin `text_ref` only while the source retention policy still permits it. Generated media and attempt telemetry are inventory-linked by `line_id/context_id`, the retention object, and the voice/asset provenance record; cached media additionally uses the asset manifest. Missing/expired policy values block provider I/O and persistence. Browsers already receive caption/subtitle text through R7 projection; the audio channel does not create a second text authority.

## Routing contract

The router evaluates in this order and stores the resolved result once:

1. Reject if `text_event_id` is absent, text is not disclosed, or the safe projection failed. No provider or cache lookup follows.
2. If a normal combat domain event declares `audio_policy=cache_only`, resolve `(speaker voice_key, event_key, locale, ruleset/content version)` to an approved cache pool. Use the persisted shuffle-bag assignment. A missing pool/asset becomes `text_only`; live TTS is forbidden on this path.
3. Otherwise resolve voice: exact `entity_id` route → explicit archetype route → entry’s explicit `fallback_voice_key` chain → `text_only`. Any missing/unapproved/cyclic entry becomes `text_only`; never choose a random provider voice.
4. Severin has `fallback=text_only`. An important NPC may fall back only to the predeclared cleared archetype in its roster. A generic NPC may fall back to a cleared generic voice.
5. Store source, voice/model/asset, line/context/playback IDs, and manifest versions before provider or browser work.

The cache shuffle bag is durable audio-control state, not world state. Each approved asset appears once per cycle before reuse; the next cycle is a deterministic permutation. The chosen `asset_id` is stored under `presentation_id/line_id`, so retry/restart cannot choose a different joke.

## Unified-core input

The core emits a server-only `audio.intent` after the safe presentation gate:

```json
{
  "schema_version": 1,
  "kind": "audio.intent",
  "event_id": "audio-intent:turn-9:17",
  "room_id": "room-1",
  "turn_id": "turn-9",
  "world_revision": 17,
  "presentation_id": "presentation:turn-9:17",
  "text_event_id": "text:turn-9:1",
  "speaker_role": "narrator",
  "entity_id": "narrator:severin",
  "archetype": null,
  "event_key": "phase.world.summary",
  "audio_policy": "dynamic_allowed",
  "locale": "en",
  "ordinal": 1
}
```

`audio_policy` is `cache_only | dynamic_allowed | text_only`. Normal `hit/miss/critical/death/spell` events use `cache_only`; an authored exception must be a distinct important presentation event, not a runtime override hidden in the audio adapter.

The audio router joins `text_event_id` to the already disclosed text. The intent never carries a model prompt, world-secret field, arbitrary voice ID, raw provider payload, or typed game command.

## Provider adapter contract

For `source=tts`:

1. Select the socket bound to the stored `provider_voice_id`; open it server-side if absent. A room has at most one generating context across all voice sockets.
2. Use `pcm_24000`, mono S16LE, explicit stored `model_id`, `context_id`, and `enable_logging` value. Never rely on provider defaults for voice/model/retention mode.
3. Send complete sentence chunks and `flush=true` at sentence boundaries. Do not split SSML tags or stream individual model tokens.
4. Normalize provider frames to `{context_id, chunk_seq, encoding, sample_rate_hz, channels, duration_ms, audio_bytes}`. Provider frames for unknown/closed/stale context, non-monotonic sequence, or lower `audio_fence` are discarded and counted.
5. `is_final` marks provider completion only. It does not prove browser playback completion.
6. On cancel, send `{context_id, close_context:true}` after the durable cancel fence exists. Provider close/error/timeout is not treated as proof of client silence.

The provider may deliver an error or close without a useful terminal frame. Normalize errors to:

- `auth_or_permission`;
- `invalid_request_or_voice`;
- `quota_or_rate_limit`;
- `concurrency_limit`;
- `provider_busy_or_5xx`;
- `transport_closed`;
- `protocol_error`.

Any error before first audio yields `failed_text_only`. Any error after first audio sends/records `audio.stop`, clears remaining buffers, and yields `interrupted`; it does not automatically restart words the room may already have heard. Provider reconnect is for future lines. Only explicit admin audio retry creates a new generation/playback attempt.

## Leader playback messages

R7 `audio.play` is extended as follows; all fields are required:

```json
{
  "protocol_version": 1,
  "kind": "audio.play",
  "event_id": "audio-play:line-1:a1",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "audio_fence": 12,
  "presentation_id": "presentation:turn-9:17",
  "line_id": "line:1",
  "context_id": "ctx:line-1:a1",
  "playback_attempt_id": "play:line-1:a1",
  "text_event_id": "text:turn-9:1",
  "source": "tts",
  "priority": 80,
  "encoding": "pcm_s16le",
  "sample_rate_hz": 24000,
  "channels": 1,
  "max_buffer_ms": 250,
  "media_ref": "media:line-1:a1"
}
```

Only the current leader receives a usable `media_ref`. Every chunk carries the same lease, line, context, playback, media and fence identity plus `chunk_seq`, `duration_ms`, `eof`, and bytes. The browser may play/decode a command or chunk only if all identities equal its current active record, the event/sequence is unseen/next, and `audio_fence == applied_control_fence`. A next-fence envelope/chunk follows the bounded non-playing wait rule above; a stale/gapped/overflow frame is dropped and cannot advance the fence.

The relay envelope is exact; binary framing may carry `audio_bytes` outside JSON but it must authenticate the same header:

```json
{
  "protocol_version": 1,
  "kind": "audio.chunk",
  "event_id": "audio-chunk:ctx-line-1-a1:7",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "audio_fence": 12,
  "presentation_id": "presentation:turn-9:17",
  "line_id": "line:1",
  "context_id": "ctx:line-1:a1",
  "playback_attempt_id": "play:line-1:a1",
  "media_ref": "media:line-1:a1",
  "chunk_seq": 7,
  "encoding": "pcm_s16le",
  "sample_rate_hz": 24000,
  "channels": 1,
  "duration_ms": 80,
  "eof": false,
  "audio_bytes": "binary-frame-or-base64"
}
```

`event_id` is stable for `(context_id, chunk_seq)`. The relay rejects a gap/non-monotonic provider sequence rather than inventing missing silence; the browser never advances a seen marker for a rejected or future-waiting frame. It marks the event applied only after the matching control fence has been applied and the frame is admitted.

`audio.stop` is broadcast to every commissioned surface and is exact:

```json
{
  "protocol_version": 1,
  "kind": "audio.stop",
  "event_id": "audio-stop:operation-55",
  "operation_id": "operation-55",
  "scope": "speech_identity",
  "lease_generation_floor": 8,
  "audio_fence": 13,
  "line_id": "line:1",
  "context_id": "ctx:line-1:a1",
  "playback_attempt_id": "play:line-1:a1",
  "reason": "cancelled"
}
```

Reasons: `cancelled | provider_failed | lease_lost | stale_generation | session_paused | session_ended`. `scope` is `speech_identity | all_audio`. `speech_identity` requires all three speech IDs and clears only that speech attempt; `all_audio` requires them all to be null and clears speech, cached speech, SFX, both music sources, queued current media, and gain automation. Lease loss, pause, and end always use `all_audio`. The control reducer clears the scope first and only then commits the higher `applied_control_fence`; it drains eligible future-wait media afterward.

After clearing, the current/former leader sends `audio.stopped` with operation, identity, fence, highest accepted chunk sequence, `buffered_ms=0`, and outcome. This ack is operational evidence only: cancel remains idempotent and does not wait on a dead browser. Physical no-echo is proved later with a real audio loopback measurement.

```json
{
  "protocol_version": 1,
  "kind": "audio.stopped",
  "event_id": "audio-stopped:operation-55:scene-b",
  "operation_id": "operation-55",
  "scope": "speech_identity",
  "consumer_id": "scene-b",
  "lease_generation": 8,
  "audio_fence": 13,
  "line_id": "line:1",
  "context_id": "ctx:line-1:a1",
  "playback_attempt_id": "play:line-1:a1",
  "highest_accepted_chunk_seq": 7,
  "buffered_ms": 0,
  "outcome": "stopped"
}
```

`audio.control_snapshot` is the only control allowed to jump a detected fence gap. It is leader-targeted, contains no playable asset, and uses the same clear-before-fence reducer:

```json
{
  "protocol_version": 1,
  "kind": "audio.control_snapshot",
  "event_id": "audio-control-snapshot:scene-b:13",
  "room_id": "room-1",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "audio_fence": 13,
  "scope": "all_audio",
  "reason": "gap_recovery",
  "current_music_state_id": "music-state:17"
}
```

The client reports a gap/timeout/bound failure without advancing its fence:

```json
{
  "protocol_version": 1,
  "kind": "audio.control_gap",
  "event_id": "audio-control-gap:scene-b:12:15",
  "room_id": "room-1",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "applied_control_fence": 12,
  "received_media_fence": 15,
  "discarded_envelopes": 3,
  "reason": "fence_gap"
}
```

Gap reasons are `fence_gap | wait_timeout | event_bound | byte_bound | speech_duration_bound`. The message is operational recovery input only and cannot mutate world state or grant playback authority.

## Browser player and mixer state machine

One `AudioContext` contains independent gain lanes:

```text
streamed speech (PCM AudioWorklet ring) ─ speechGain ┐
cached speech (tracked AudioBufferSourceNodes) ──────┤
critical/ordinary SFX ─ sfxGain ─────────────────────┼─ masterGain ─ destination
music A/B loop sources ─ musicGainA/B ───────────────┘
```

Web Audio scheduled sources expose `stop(when)`; a `when` of 0 or before current time stops immediately in the rendering timeline [B1]. The AudioWorklet contract exposes a message port and renders in finite quanta (default 128 frames in the cited specification) [B2]. These primitives support a bounded app queue, but they do not prove a physical speaker stops at a particular wall-clock millisecond.

On `audio.stop`, the browser synchronously:

1. closes media admission and records any cancelled speech identity without advancing the fence;
2. for `speech_identity`, removes/zeros only the matching streamed queue/ring, calls `stop(0)` on the matching cached-speech source, and releases its ducking;
3. for `all_audio`, removes/zeros every active current-fence stream/queue, calls `stop(0)` and disconnects every scheduled speech/SFX/music source, cancels all gain automation, and resets gains/state to silence;
4. commits the control's `audio_fence` as `applied_control_fence`, then drains matching future-wait media whose lease is still exact;
5. reopens admission and emits `audio.stopped` with the applied scope and zero pre-control buffered duration.

Do not close the whole `AudioContext` to cancel one line; music/SFX are independent. Audio must be unlocked by user activation before candidacy. If not unlocked, if buffer/clock bounds cannot be established, or if lease validity is ambiguous, the client fails silent.

### Queue and ducking

| Priority | Class | Scheduling rule |
|---:|---|---|
| 100 | control | executes before all media; stop/pause/end clears/fences as scoped |
| 80 | speech | exactly one active line; stable FIFO by presentation order; new lines do not barge in unless an explicit cancel operation precedes them |
| 70 | critical SFX | may overlap speech; never delays or cancels speech |
| 50 | ordinary SFX | bounded polyphony; duplicate event IDs render once; overload may coalesce/drop this class only |
| 10 | music | one state with two-source crossfade; never blocks speech/SFX |

Initial configuration: speech attack ducks music to gain `0.25` and SFX to `0.50` in `80 ms`; release returns both to `1.0` in `250 ms`; music transitions use a `1,000 ms` equal-power crossfade. These are provisional configuration values subject to I8 acoustic tuning.

`music.set_state` is a leader-scoped rendering of durable scene state, not a broadcast asset command:

```json
{
  "protocol_version": 1,
  "kind": "music.set_state",
  "event_id": "music-delivery:music-state-17:lease-8",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "audio_fence": 13,
  "presentation_id": "presentation:turn-9:17",
  "music_state_id": "music-state:17",
  "music_state": "danger",
  "track_id": "music.danger.01",
  "manifest_version": "audio-2026-08-16.1",
  "media_ref": "media:music-danger-01",
  "crossfade_ms": 1000,
  "start_policy": "loop_from_zero"
}
```

The server maps canonical states `silence | exploration | danger | conversation | combat | boss | victory | defeat` to a cleared `track_id`; the AI/browser cannot submit asset paths. Only the exact current consumer receives the leader-scoped `media_ref`. Playback acceptance requires exact current lease ID/generation/consumer, `audio_fence == applied_control_fence`, approved manifest/media identity, and unseen `event_id`; next-fence music waits as an unfetched envelope behind the control barrier. Ambiguity fails silent. The next admitted state cancels the prior crossfade from its current gains and converges to one loop.

After leader election, the server issues a **fresh leased rendering event** for the current `music_state_id` at the new lease generation/current fence. The successor starts the loop from zero; it does not replay speech or ephemeral SFX. The former leader has already received/locally enforced `all_audio` stop and rejects the fresh event by lease identity. Duplicate delivery to the current leader is a no-op.

`sfx.play` is exact and leader-scoped:

```json
{
  "protocol_version": 1,
  "kind": "sfx.play",
  "event_id": "sfx:combat-result-99",
  "lease_id": "lease:8",
  "lease_generation": 8,
  "consumer_id": "scene-b",
  "audio_fence": 13,
  "presentation_id": "presentation:turn-9:17",
  "sfx_key": "combat.critical",
  "asset_id": "sfx.combat.critical.01",
  "manifest_version": "audio-2026-08-16.1",
  "media_ref": "media:sfx-combat-critical-01",
  "priority_class": "critical_sfx",
  "gain": 1.0
}
```

The same exact lease/consumer/fence/manifest/event acceptance rule applies. Missing/unapproved asset is silent and logged; it never triggers generated SFX in MVP. SFX is ephemeral: reconnect/election never replays it. Room-wide `all_audio` stop clears all active/scheduled SFX; any late event at an old lease/fence is dropped.

## Cancel, retry, reconnect, and replay

### Cancel transaction and fan-out

1. The authority resolves the current line/context server-side; an admin body does not inject them.
2. In one audio-control transaction, store `operation_id`, increment `audio_fence`, set line `cancel_requested/cancelled`, and enqueue provider-close plus `audio.stop` tasks. Return the stored result on duplicate operation.
3. Execute provider close and browser stop independently and retry each technical task idempotently.
4. Every provider/client frame at a lower fence or for the cancelled identity is a durable/metric late drop.
5. Audio cancellation changes no world/aggregate revision and never calls the game kernel.

### Retry

- Automatic per-line retry is disabled. It risks repeated audible words and unobserved extra provider usage.
- An explicit `audio.retry` request is persisted only for a stored `failed_text_only | interrupted | cancelled` line whose disclosed text, retention, and manifest routes still validate.
- Provider I/O is delayed in `retry_waiting_for_audio_admission` until the previous provider-close task is `completed | superseded_by_confirmed_socket_close`, every former-leader stop task is `acknowledged | superseded_by_lease_expiry_and_buffer_bound`, the current audio fence is durable, and exactly one unlocked/unambiguous current lease exists. A dead browser never blocks forever: expiry plus the R7 buffer/clock guard supplies the terminal disposition. While waiting there is no new context, provider call, playable media, or cost row.
- After admission, retry keeps `line_id/text_event_id/presentation_id/world_revision`, increments generation and playback attempts, allocates a new `context_id/media_ref/event_id`, and records a separate cost row.
- Retry does not reproject, approve, execute, reroll, or call the kernel.

### Reconnect

- Socket reconnect resumes R7 projection only. It never replays `audio.play`, retry, cancel, approval, or game action [L3].
- Lease/socket loss increments the fence, stops all local audio by deadline, closes current provider context, and marks an incomplete line `interrupted`.
- A new leader begins with future speech/SFX only. Past speech needs an explicit retry and past SFX is never replayed. The server sends one fresh leased/idempotent rendering of the current persistent music state at the new generation/fence. Silence/captions are preferred to overlap or duplicated words.
- `reproject_last_safe` intentionally rerenders visuals but enqueues no audio [L3].

## Latency and cost telemetry

One record per generation/playback attempt stores no line text:

```text
room_hash, turn_id, presentation_id, line_id, context_id, playback_attempt_id,
source, voice_key, model_id, output_format, input_character_count,
cache_hit, queue_enter_ms, queue_start_ms, provider_connect_start/end_ms,
provider_send_ms, first_provider_audio_ms, first_relay_ms, play_command_ms,
first_worklet_quantum_ms, provider_final_ms, playback_complete_ms,
cancel_requested_ms, browser_stopped_ms, chunks/bytes, retries, outcome/error_class,
text_hmac_sha256, telemetry_key_id, retention_policy_id, deletion_disposition_id,
provider_request_id?, provider_trace_id?, provider_character_cost?, workspace_credit_bucket?
```

`text_hmac_sha256` uses a rotated server-only observability key identified by `telemetry_key_id`; an unkeyed short-line hash is forbidden because it permits dictionary recovery. The HMAC is for correlation only and is never a line/event identity.

Derived metrics are queue wait, cold connect, provider TTFA, relay, browser scheduling, end-to-first-quantum, completion, and logical cancel-to-stop-ack. The provider’s ~75 ms Flash figure excludes network/application overhead and is not used as a pass threshold [P1]. Physical first/last audible sample requires target-browser speaker-to-loopback measurement after external-provider/staging approval.

Cost observability records provider-native credits/character cost when supplied and reconciles workspace usage. It deliberately chooses no dollar budget, subscription tier, cache-size spend policy, or acceptable cost per session.

## R4 and R7 compatibility deltas

The old R4/R7 artifacts are evidence, not files to mutate here. I6 must close these exact deltas before implementation:

1. R4 `AudioJob` lacks `presentation_id`, voice/source/asset/model, generation/playback attempts, fence, completion/interruption/text-only states, and observability. Extend it without moving audio into the world transaction.
2. R7 prose names an audio fence, but its `AudioPlay`/`AudioStop` schema exposes only lease generation / `minimum_generation`. Lease election and content cancellation are different monotonic dimensions. Add explicit `audio_fence` to speech, SFX, music, chunks, and stops; do not overload lease generation.
3. R7 `AudioPlay`, `music.set_state`, and `sfx.play` need exact current lease/generation/consumer, stable `event_id`, current `audio_fence`, manifest identity, and leader-scoped `media_ref`; speech additionally needs `playback_attempt_id` and source/format/buffer fields.
4. Add operational `audio.stopped` acknowledgement. It informs admin recovery but never grants authority or blocks cancel completion indefinitely.
5. Keep R7’s 250 ms maximum buffer, server lease, generation fence, fail-silent ambiguity rule, projection-only reconnect, and no-audio reproject behavior unchanged.
6. Implement `applied_control_fence` as a strict reducer barrier: media requires equality and never advances it; next-fence media waits only within the exact bounds above; stop/control/snapshot clears first, commits the fence second, and admits waiting media last. Add `audio.control_gap`/`audio.control_snapshot` recovery.

Any implementation that omits these deltas cannot prove cancel/reconnect identity with the R6 oracle and must stop at the R6/R7 gate.

## Sources

- **[L1]** `docs/tasks/377/phase3/r4/coordinator-adr.md`, accepted R4 decision, especially durable audio jobs and post-projection audio outbox.
- **[L2]** `docs/tasks/377/phase3/r4/state-machine.md` and `command-event-schemas.json`, audio retry/cancel versus world execution.
- **[L3]** read-only R7 `surface-contract.md`, `reconnect-cursor-protocol.md`, `wireflows.md`, and `transport-schemas.json` in `/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-three-surfaces/docs/tasks/377/phase3/r7/`.
- **[P1]** ElevenLabs, [latency concepts](https://elevenlabs.io/docs/eleven-api/concepts/latency).
- **[B1]** W3C, [Web Audio API 1.0 — `AudioScheduledSourceNode.stop`](https://www.w3.org/TR/webaudio-1.0/).
- **[B2]** W3C, [Web Audio API 1.1 — AudioWorklet/render quantum](https://www.w3.org/TR/webaudio-1.1/).
