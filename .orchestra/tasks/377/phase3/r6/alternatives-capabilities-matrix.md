# R6 alternatives and capability matrix

Status: research decision, no real provider calls. “Selected” below is an architectural default for I6, not a provider-plan, price, or deployment purchase.

## Decision

Use a hybrid audible path:

1. Normal combat speech, SFX, and music are cleared preauthored/pre-generated assets served by the application and mixed in the single R7 playback leader. They make zero runtime TTS calls.
2. Important story/narrator/NPC lines use a server-owned ElevenLabs adapter. The default transport is one on-demand multi-context WebSocket per active `voice_id`, with at most one context generating room-wide. The server relays `pcm_24000` signed 16-bit little-endian mono chunks to the current R7 leader and retains provider credentials, provider cancellation, usage telemetry, and late-chunk rejection.
3. Every line is caption-first. Provider failure, missing cleared voice/asset, lease uncertainty, reconnect, or cancellation leaves the committed text/board visible and degrades to text-only; none calls the game kernel. Speech, SFX, and music all carry the same exact current lease/generation/consumer plus the independent room audio fence.
4. `eleven_flash_v2_5` is the low-latency default candidate for dynamic lines; `eleven_multilingual_v2` is the quality comparator. The voice manifest fixes the model per voice after an authorized recorded comparison. The architecture does not depend on either model, and v3 is not accepted for this WebSocket path because the official real-time guide says that endpoint does not support it [P4].
5. Browser media requires `audio_fence == applied_control_fence`. Media never advances the fence. Next-fence envelopes wait without playback/fetch within `16` events, `256 KiB`, `250 ms` speech, and `250 ms` time; only control clears old lanes, commits the fence, then admits waiting media. Overflow/gap/timeout fails silent and requests a control snapshot.

The selected proxy path is based on authority/cancellation observability, not an unmeasured speed claim. Browser-direct TTS remains a reversible contingency if a later authorized room measurement proves a material end-to-end advantage while retaining the same R7/R6 identities and cancel oracle.

## Transport alternatives

| Alternative | Streaming / voice routing | Provider-side cancel | Browser hard stop | reconnect/replay | secrets, retention, cost | failure behavior | Verdict |
|---|---|---|---|---|---|---|---|
| **A. Server-owned ElevenLabs multi-context WS + application PCM relay** | `voice_id` is in the WS path, so each active voice needs its own voice-bound socket; contexts do not select voices [P1][P2]. Room-wide generation is serialized even if multiple sockets are warm. | Exact `close_context` exists. Provider docs recommend closing the old context on interruption, but do not promise withdrawal of chunks already delivered [P2]. | Current leader clears the AudioWorklet ring and stops tracked cached/SFX sources; every later frame is rejected by line/context/fence. | Lease loss cancels the live context. Reconnect restores projections only. Explicit audio retry creates a new context/playback attempt and no game command. | API key stays server-side [P9]. Server records request/context/model/voice/characters/latency/outcome and later reconciles workspace credits [P6]. Provider default retention still applies unless ZRM is actually entitled and enabled [P7]. | Caption/text-only immediately; local cache/SFX/music continue. No automatic replay of a partial line. | **SELECTED default.** Strongest ownership and observability fit; application/network latency unmeasured. |
| **B. Server-owned HTTP streaming for whole text** | Official guidance says HTTP streaming fits complete up-front text and standard WS can add buffering when full text is already available [P1][P3]. Voice is one request path. | Client can abort its HTTP receive, but the opened official sources do not document an utterance-scoped provider cancellation acknowledgement comparable to `close_context`. | Same application player as A. | Simple new request for explicit retry; completed partial receipt cannot be safely auto-replayed. | HTTP exposes `character-cost`, `request-id`, and `x-trace-id` headers [P5]. Same server secret/retention boundary. | Text-only on abort/error. | **KEEP as measured fallback**, especially if all line text is complete and authorized tests show better TTFA. Does not satisfy the chosen close-context oracle without new provider evidence. |
| **C. Browser-direct ElevenLabs WS with server-minted single-use token** | Provider supports `tts_websocket` single-use tokens that expire after 15 minutes and are consumed on use [P8]. Each browser socket is still voice-bound [P1]. | Browser can send `close_context`, but the server must trust/observe a client-owned provider session and coordinate its fence with every app client. | Direct current-leader buffer stop is possible. | A new leader needs a new token/socket; in-flight context cannot transfer. A stale browser may retain already delivered audio until the R7 buffer/lease bound expires. | Long-lived key is absent, but a provider credential and provider data path enter the browser. Per-attempt centralized cost/retention evidence is weaker. | Text-only, but provider lifecycle and app lifecycle can disagree. | **NOT SELECTED.** Feasible, but fragments the server-owned cancellation/telemetry boundary. Reopen only after an authorized room A/B test proves a material advantage. |
| **D. Standard WS, one connection per line** | Supports partial text/alignment and voice-bound path [P1]. | Closing the socket stops future use of that socket; no independent context close. | Same application player. | Every retry is a new connection. | Same server key/retention boundary. | Text-only; cold connection cost for each line. | **REJECT for primary**, retain as adapter fallback if multi-context becomes unavailable. |
| **E. Generate a complete file, then HTML media playback** | Simplest for an already complete line. No first-audio until enough/all data is returned; not a streaming dialogue path. | HTTP abort has the same provider-side evidence gap as B. | `pause`/source reset can stop playback, but exact queued identities and sample-level bounded buffering are less explicit than the selected PCM graph. | Easy explicit replay; easy accidental replay if tied to projection history. | HTTP metadata is observable [P5]; file storage adds a new retention/provenance surface. | Caption/text-only. | **REJECT for dynamic story**, valid only for the offline cleared asset pipeline. |
| **F. Text-only** | No voice routing or provider. | Not applicable. | No audible buffer. | Deterministic. | No TTS disclosure or TTS credits. | Preserves gameplay and subtitles. | **MANDATORY degradation mode**, not the desired presentation. |

## Provider and model capabilities

| Capability / limit | Official fact | R6 consequence |
|---|---|---|
| Voice binding | Both standard and multi-context TTS WS endpoints place `voice_id` in the URL path [P1][P2]. | `context_id` is never a voice selector. The registry resolves an explicit voice before opening/selecting a socket. |
| Interruption | Multi-context accepts `close_context`; the guide uses it for barge-in [P2]. | Close future generation, then independently clear browser buffers. Treat any post-cancel provider frame as normal late input and discard it. |
| Context count | A connection allows up to five contexts, and the guide says to close unused contexts [P2]. | The MVP uses one generating context room-wide. The limit is not a reason to generate five voices concurrently. |
| Open-socket concurrency | An open WS counts toward concurrency only while its model is generating audio; account/model limits and response headers are plan-specific [P10]. | Warm voice sockets may exist, but the dispatcher remains serial and records `current-concurrent-requests`/`maximum-concurrent-requests` if exposed. No plan purchase follows from this fact. |
| Latency | Flash’s cited ~75 ms is model inference only; network/application/voice complexity and load add latency [P4]. Streaming improves perceived latency, not model inference [P4]. | Measure the production-shaped end effect. Do not call 75 ms an MVP TTFA or SLA. PVC/complex voice measurements remain required. |
| Input shape | Multi-context guidance recommends chunking long responses but flushing complete sentences [P2]. Standard WS `auto_mode` is recommended only for complete sentences [P1]. | Queue complete sentences, preserve one line/context, and do not forward individual model tokens as if they were sentences. |
| Output | ElevenLabs documents PCM S16LE including 24 kHz [P11]. | Normalize the provider boundary to mono `pcm_24000`; the browser resamples through its AudioContext. Any format change is an adapter/manifest revision, not implicit negotiation. |
| Error signals | HTTP 4xx indicates request/auth problems, 5xx provider problems; 429 distinguishes rate/concurrency codes [P12]. | Normalize to stable internal error classes. Never show provider bodies/keys in browser/admin. Current line becomes text-only; reconnect is for future work only. |
| Cost evidence | HTTP generation can expose `character-cost`, `request-id`, and `x-trace-id` [P5]. Workspace analytics returns credits by product/time and supports grouping/filtering [P6]. | Store per-attempt local inputs/observations without line text, then reconcile aggregate provider credits. Unknown per-WS cost stays `unknown`, never guessed. |
| Retention | TTS input/output retention is enabled by default. ZRM is for select Enterprise customers, API-only, and must be enabled with `enable_logging=false`; voice-cloning samples are not ZRM-eligible [P7]. | The data/plan authority must accept default retention or prove ZRM entitlement/configuration before real calls. The application cannot promise zero retention. |
| Voice availability | Public Voice Library voices can be removed immediately or after a notice period and may carry credit multipliers [P13]. PVC can clone only the account holder’s own voice; another performer must create/verify and share their voice [P14]. | Severin and important NPC identities require commissioned/controlled provenance. A public library voice is not the only brand voice or an implicit fallback. |

## Playback/mixing capabilities

| Channel | Source | Concurrency / priority | Selected behavior | Offline/provider failure |
|---|---|---|---|---|
| Control | server R7/R6 operations | priority 100, preempts all | strict reducer barrier: close admission → clear affected/all old lanes → commit `applied_control_fence` → admit exact-fence waiting media | always available |
| Speech | cleared cache or TTS | priority 80, one line at a time | stable FIFO by presentation order; no automatic reconnect replay; captions appear independently | cached stays available; TTS becomes text-only |
| Critical SFX | cleared asset | priority 70, may overlap speech | leader-scoped lease/fence/media envelope; short result cue; gain ducked during speech; never delays/cancels speech; no reconnect replay | available only at the current leader if asset is locally served |
| Ordinary SFX | cleared asset | priority 50, bounded polyphony | leader-scoped lease/fence/media envelope; may be coalesced/dropped under load by event ID; never affects world state; no reconnect replay | available only at the current leader if asset is locally served |
| Music | cleared loop/stem | priority 10, exactly one state | leader-scoped lease/fence/media envelope; state-driven equal-power crossfade; no generative provider; a new leader receives a fresh rendering of current state from loop start | reconstructed only at the current leader if asset is locally served |

Selected initial mixer constants are configuration, not acoustic facts: speech ducks music gain to `0.25` over `80 ms`, SFX gain to `0.50`, then releases both to `1.0` over `250 ms`; `music_state` uses a `1,000 ms` equal-power crossfade. The fake player proved the state transitions only. I8 must tune/falsify audibility, clipping, and intelligibility on the target speakers without weakening identities, one-leader ownership, or cancel semantics.

## Sources opened 2026-08-16

- **[P1]** ElevenLabs, [standard TTS WebSocket API](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input).
- **[P2]** ElevenLabs, [multi-context WebSocket guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/multi-context-web-socket) and [API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-multi-stream-input/).
- **[P3]** ElevenLabs, [latency optimization](https://elevenlabs.io/docs/api-reference/reducing-latency).
- **[P4]** ElevenLabs, [latency concepts](https://elevenlabs.io/docs/eleven-api/concepts/latency), [models](https://elevenlabs.io/docs/overview/models), and [real-time TTS guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts).
- **[P5]** ElevenLabs, [API introduction: tracking generation costs](https://elevenlabs.io/docs/api-reference/introduction).
- **[P6]** ElevenLabs, [workspace usage analytics](https://elevenlabs.io/docs/api-reference/analytics/workspace/usage).
- **[P7]** ElevenLabs, [Zero Retention Mode](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode).
- **[P8]** ElevenLabs, [single-use token API](https://elevenlabs.io/docs/api-reference/tokens/create).
- **[P9]** ElevenLabs, [API authentication](https://elevenlabs.io/docs/api-reference/authentication).
- **[P10]** ElevenLabs, [models: concurrency and priority](https://elevenlabs.io/docs/overview/models).
- **[P11]** ElevenLabs, [TTS output formats](https://elevenlabs.io/docs/overview/capabilities/text-to-speech).
- **[P12]** ElevenLabs, [API errors](https://elevenlabs.io/docs/eleven-api/resources/errors).
- **[P13]** ElevenLabs, [Voice Library](https://elevenlabs.io/docs/eleven-creative/voices/voice-library).
- **[P14]** ElevenLabs, [voice-cloning overview](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning).
