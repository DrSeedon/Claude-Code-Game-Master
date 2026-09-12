# R7 — synchronized browser surface contract

- Status: research decision contract for I1/I3/I8
- Date: 2026-08-16
- Scope: synthetic schemas, reducer/authority probe and browser interaction contract only
- Decision owner: frontend/UX lead + backend projection owner
- No frontend was copied; no private repository, provider, remote service, real room, production state or deployment was created

## Question

**Context.** The canonical MVP has one remote authoritative room, table/scene/admin browsers, a composite one-screen fallback, R4 transactional coordinator/outbox semantics, R8 server-owned room/surface/actor authority, player-safe output, temporary planning marks and one playback owner.

**Change under test.** Use exact per-surface allowlisted full projections in a shared versioned batch, at-least-once delivery with stable event IDs, reducer-and-render-success cursor acknowledgement, server-owned capabilities, a separate TTL overlay stream, and a fenced server audio lease.

**Baseline.** The unsafe baseline is socket-order rendering with an in-memory cursor, content/text dedupe, one full world/admin payload filtered in browser code, client-selected role/actor and client-local audio election.

**Measurable outcome.** Under duplicate, drop, reorder, reconnect, render failure, canary injection, capability attacks, overlay expiry and leader loss: all safe surfaces reach one projection batch; duplicate renders once; failed render cannot move its cursor; no browser bytes contain the canary; denials change no protected state; overlays reconnect/expire without canonical mutation; and the lease store has one current playback owner.

## Hypotheses and falsifiers

| Hypothesis | Falsifier | Result |
|---|---|---|
| **H1 — reducer-gated full projections plus stable IDs converge under ordinary replay faults.** | Any client ends on another safe aggregate version; a duplicate renders twice; or a render exception advances the cursor. | **CONFIRMED in the synthetic harness.** Four presentation clients ended at version 3; duplicate render count was 1; injected failure left cursor 0, then replay advanced it to 1 [4]. |
| **H2 — WebSocket order, content dedupe and an in-memory cursor are sufficient.** | A dropped/reordered message creates a gap; reconnect loses cursor/view; equal content represents distinct events. | **REFUTED by contract and probe.** The probe observed and repaired a sequence gap/snapshot; RFC 6455's within-message/connection ordering does not provide application replay across reconnect [4][6]. R4 already measured replay/live duplication [2]. |
| **H3 — one canonical/full payload can be sent to every browser and filtered by role in the client.** | An unrevealed field reaches network/cache/DOM/error bytes or an unknown field passes a denylist. | **REFUTED by the R4/R8 boundary.** R4's unknown-field canary required publication failure; R8 forbids full/private state in every browser including admin [2][3]. R7 uses three closed server projections and rejects unknown fields. |
| **H4 — composite requires a fourth authority role/state.** | Exact table+scene envelopes cannot be paired without mixed versions or broader capabilities. | **REFUTED in the synthetic reducer.** A table session subscribed to exact table+scene streams and atomically staged one batch without admin authority; both panes ended at version 3 [4]. |
| **H5 — client-local “first player wins” audio election is adequate.** | Reconnect/partition lets two clients believe they lead or a stale generation plays after re-election. | **REFUTED as an authority model.** The selected single server lease/generation fenced the old synthetic leader and elected generation 2; physical audible non-overlap still requires I8 buffer/clock measurements [4]. |

## Decision

Adopt protocol version 1 defined by:

- `projection-schemas.json`: exact `table.v1`, `scene.v1`, and operational `admin.v1` envelopes with `additionalProperties`/`unevaluatedProperties` closure and explicit field allowlists;
- `transport-schemas.json`: closed WebSocket messages for handshake, ack, overlay, admin operation and audio lease/play/stop;
- `capability-matrix.md`: server-owned room/surface/actor/capability intersection and negative zero-mutation boundary;
- `wireflows.md`: table/scene/admin/composite, overlay and audio sequences;
- `reconnect-cursor-protocol.md`: snapshot/replay/live barrier, cursor transaction, gap and reducer failure behavior;
- `pointer-events-device-matrix.md`: one Pointer Events reducer for touch/mouse/pen plus display/fullscreen fallbacks;
- `surface_protocol_probe.py`, `test_surface_protocol_probe.py`, and `probe-results.json`: reproducible synthetic evidence.

### Non-negotiable invariants

1. The VPS/session store owns room, role, actor allowlist, consumer ID, capabilities and audio priority. Client authority claims are absent or rejected.
2. Canonical world, coordinator result and projection intent retain the R4 single-authority transaction boundary. Browser state is never authoritative.
3. Table and scene are built only from revealed/player-safe data. Admin is constructed independently from operational records, not filtered from world state.
4. One successful projection transaction fixes a safe `projection_batch_id`, `aggregate_version`, and `world_revision`; table/scene/admin receive distinct stable events for that boundary.
5. Delivery is at least once. Stable ID + stream sequence + full snapshot create effects-once rendering. Payload text/content is not identity.
6. Cursor acknowledgement is durable only after exact schema validation, reducer success, detached render construction and visible atomic swap.
7. Composite is table authority with exact table+scene subscriptions. It displays/acks neither half until both halves of one batch render successfully.
8. Unknown projection fields/types publish no player envelope, preserve the last safe batch, and produce only a safe operational error. World commit is neither undone nor repeated.
9. Overlay state has its own sequence/TTL store and idempotency tombstones. It never changes aggregate/world version or enters an approved command.
10. Playback requires the sole current server lease `(room, lease_id, generation, consumer_id)`. A projection ack or client claim cannot grant it.

## Projection boundary

### Table allowlist

`board` contains public cells/tokens/legal cells/public rolls; `phase` contains public mode/round/side/acted actor IDs; `draft_card` contains the exact human-readable summary and current single-use approval nonce; `public_events` contains disclosed narration/roll/result/phase/notice; `activity` contains an enum. Hidden cells/tokens and internal plan/command fields have no schema path.

### Scene allowlist

`scene` contains only public scene/asset/transition references; `speaker` only a public actor/display/portrait reference; `subtitle`, `public_result`, and activity are disclosed text/enums. Image prompts, raw provider output and private actor state have no path.

### Admin allowlist

Admin receives eight top-level fields only: run state, coordinator stage/recovery/versions, projection-health enums and age buckets, audio/input health enums, safe error code/stage/correlation hash/retryability, allowed recovery enums and last operation metadata. It receives no map, narration, NPC/world facts, draft plan, command, prompt, transcript, raw error/stack, token, URL, filesystem path or private audit identity.

All browser bootstrap/projection responses use `Cache-Control: no-store`. Authority credentials remain an HttpOnly cookie and one-time upgrade ticket; no projection/session bytes go to Local Storage. An approval nonce is short-lived, table-only and bound to the immutable stored draft; it is not an authority bearer outside that exact approval transaction.

## Aggregate, delivery and acknowledgement semantics

- Full replacement projection is selected for MVP. It keeps replay and schema upcast behavior deterministic; deltas/patches may be reconsidered only with a new gap/upcast oracle.
- Sequence is per `(room,surface,projection_schema)`. Cursor is per `(room,surface,consumer_id,projection_schema,reducer_version)`.
- A new document rehydrates from a full safe snapshot. A reconnecting intact document may ask for bounded replay, but the server can force snapshot on any ambiguity.
- The server-designated table/composite presentation consumer's table ack satisfies the R4 presentation gate and permits the audio enqueue task. Other acks report delivery health and cannot repeat/block world mutation indefinitely.
- A gap, unknown schema or render exception leaves the last safe view and cursor untouched. Composite also leaves both panes untouched on a missing/mismatched half.
- `reproject_last_safe` creates new delivery event IDs pointing to the same safe batch/version. It intentionally renders again, but never invokes the kernel or audio.

On a healthy trace, connected clients converge to the latest safe aggregate version. During a projection failure, the safe projection can lag committed world. Admin must show current committed versions and last-safe surface versions as degraded; claiming that the rejected batch converged is forbidden.

## Capabilities and admin operations

The closed matrix is in `capability-matrix.md`. Table owns draft/actor/approval and non-canonical overlay actions. Scene is read-only. Admin owns only start/pause/end, diagnostics, volume, provider/audio cancel, safe reproject and retry of the server-named unfinished technical stage. Composite has the table action set, not a union with scene/admin.

Start/pause/end/volume/cancel/reproject increment or inspect `control_revision`/technical state as specified but do not mutate world revision. Admin cannot supply story text, plan, command, patch, reveal or actor. Audio retry/cancel and projection retry never call the game kernel.

Every state-changing message has a stable request/operation ID and expected version. Exact duplicates return the stored result. Authorization and schema denial occurs before protected state; authenticated denials append a redacted audit decision.

## Overlay contract

V1 supports `arrow` and `marker`, public grid points only, TTL 1–30 seconds, server absolute `expires_at`, separate monotonic overlay sequence, full reconnect snapshot, and dedupe tombstone through the replay window. The server clock expires items; clients may hide conservatively if the expiry event is lost. Sequence gap replaces the local overlay set. No arbitrary overlay text is accepted.

The synthetic item was visible in a reconnect snapshot before 2,000 ms, absent exactly at expiry, and left `(world_revision, world_mutation_count)` unchanged [4]. A server process restart may discard this explicitly ephemeral store unless I3 chooses a TTL-capable external store; the next overlay snapshot makes loss explicit and still cannot affect canonical state.

## Exactly one audio leader

Audio eligibility is separately commissioned. Default room policy prioritizes the physical table/composite; scene can be failover; admin is never eligible. The client must first satisfy browser user-activation/audio-unlock and report a maximum buffered duration of 250 ms. The server stores at most one room lease, increments generation on every grant/revoke, and sends playable media only with the exact current lease/generation/consumer.

Lease duration in the synthetic model is 5 seconds; production duration/renewal cadence is an I8 measurement. The browser stops before a conservative local deadline and never buffers more than 250 ms. After ungraceful loss, successor `not_before` is old expiry + buffer cap + measured clock-uncertainty guard. If clock/RTT uncertainty is unbounded, fail silent. Cooperative release with confirmed drain can fail over immediately. This closes logical ownership; physical no-echo remains an explicit real-browser/room gate.

Cancel independently closes provider generation, increments the audio fence, sends stop to all clients, and drops buffered/queued/late chunks by `line_id/context_id`. Audio repeat is a playback attempt, not a game command.

## Pointer Events and fullscreen

Pointer Events supplies one hardware-agnostic flow for mouse/touch/pen [5]. The first eligible primary activation takes a controller interaction lock, pointer capture keeps the gesture coherent, move events update local preview, up emits one high-level intent, and cancel/lost capture/disconnect emits none. Because `isPrimary` is per pointer type, the controller lock—not `isPrimary` alone—prevents simultaneous mouse+touch commits [5].

The interactive board declares `touch-action: none` before contact; controls outside it preserve native scroll/activation. Coalesced events may smooth previews but final intent uses the ordinary captured terminal coordinate. The server snaps/validates cells and every rule/resource.

Fullscreen is a user-gesture, promise-based local request and may fail [7]. Failure keeps the same synchronized in-window layout. Fullscreen and composite layout never change authority, cursor or audio leader.

## Measurement

Commands:

```bash
uv run --active --frozen --no-sync pytest -q docs/tasks/377/phase3/r7/test_surface_protocol_probe.py
uv run --active --frozen --no-sync python docs/tasks/377/phase3/r7/surface_protocol_probe.py
```

Observed synthetic oracle:

| Check | Result |
|---|---|
| pytest | `10 passed in 0.54s` in the final verification run |
| core + composite convergence | table/scene/admin/composite each `[3]` |
| composite atomic pair | visible batch `batch:3`; first half alone leaves state/cursors empty in the focused test |
| duplicate replay/live | stable event rendered `1` time |
| reducer/render exception | cursor `0` before replay; `1` after successful replay |
| browser canary | absent from serialized client states |
| authorization | 8 expired/replayed/spoof/escalation/cross-room/direct-command denial paths; protected fingerprint unchanged; 8 denial audits |
| admin controls | 8 start/pause/end/diagnostics/volume/cancel/reproject operations; `control_revision=7`; world/aggregate/mutation unchanged |
| overlays | reconnect-visible inside TTL; empty at expiry; canonical versions/count unchanged |
| audio | generations `[1,2]`; final current leader count `1`; stale generation fenced |
| input | synthetic mouse and touch drags normalized identically; tests also cover pen/cancel/non-primary |

The harness validates every produced projection with JSON Schema Draft 2020-12. Its canonical object contains `GM_ONLY_CANARY_377_R7`; the string is absent from browser serialization. Three committed safe batches intentionally produce `world_revision=3`, `aggregate_version=3`, and `world_mutation_count=3`; overlay/admin/denial operations add none.

## Findings and confidence

| Finding | Confidence |
|---|---|
| Stable-ID full projection + post-render ack converges under the injected duplicate/drop/reorder/reconnect/render faults. | **CONFIRMED for the synthetic reducer — tier 1 direct measurement.** Not yet a real browser/socket/DB result. |
| Unknown fields and the canary cannot enter any schema-valid projection generated by the probe. | **CONFIRMED for declared schemas/probe — tier 1 measurement plus closed-schema inspection.** Future projector code remains unimplemented. |
| Server-owned capability denial can preserve protected state while auditing denials. | **CONFIRMED for eight synthetic denial paths — tier 1.** Production-shaped HTTP/WS/session/transaction tests remain R8/I8 work. |
| Separate TTL overlays meet reconnect/expiry/zero-canonical-mutation semantics. | **CONFIRMED in injected-clock model — tier 1.** Server restart persistence is intentionally not promised. |
| One fenced server lease is the correct logical ownership boundary. | **CONFIRMED in synthetic election — tier 1; LIKELY for physical no-echo.** Buffer, clock, browser crash and room acoustics are unmeasured. |
| One Pointer Events reducer can express touch/mouse/pen equivalently. | **CONFIRMED for normalized synthetic traces; LIKELY in target hardware.** Real UA capture/DPI/palm/fullscreen behavior requires I3/I8. |

## Counter-evidence, limits and rejected alternatives

- WebSocket/TCP order is useful within a connection and full snapshots cost more bytes than deltas. Neither fact supplies reconnect state or makes cursor-before-render safe. MVP chooses correctness and bounded projection sizes; profile before reopening deltas.
- A fully transactional DOM is an abstraction: canvas/audio/DOM APIs can have irreversible side effects. Implementation must stage offscreen/detached and swap, or introduce an explicit rollbackable boundary. The Python reducer proves the required ordering, not browser atomicity.
- Logical lease uniqueness cannot physically silence a crashed/partitioned browser that already buffered unbounded media. Hence the 250 ms cap, conservative not-before fence and fail-silent rule; I8 must falsify the assumed clock/buffer bound.
- `Sec-WebSocket-Protocol` can carry a short upgrade ticket without placing it in a URL, but proxies may log headers. R8's no-token-log oracle decides whether that concrete mechanism is admissible; R7 does not mandate it if logs cannot be controlled.
- Admin health necessarily reveals that a stage/version/error exists. The closed enum/bucket/hash schema is the selected minimum; no content/world details are justified by operational recovery.
- A table browser is a shared-room authority within its allowed actor set. It does not authenticate the physical speaker; this preserves the canonical one-mic decision and R8 limitation.
- Full projection batches may be too large for a dense 256×256 board. I3 should measure actual serialized size/render time and may introduce independently reviewed chunk/asset references, but cannot weaken version, allowlist, ack or secret invariants.

## Future affected files and gates

Expected consumers in the future private repository (no files created here): server projection schemas/projector/outbox/WS/session/capability/audio-lease/overlay modules; table/scene/admin reducers; composite layout; and I1/I3/I8 integration/e2e/security tests.

Stop implementation and return to R7/R4/R8 if it needs browser filtering of full state, a fourth composite authority, content-hash dedupe, cursor advance before visible success, locally authoritative offline actions, admin world/story access, overlay-to-world mutation, more than one lease row, unbounded audio buffer/clock uncertainty, or an authority field taken from a client payload.

## Sources

1. **[1] Tier 2 primary local specification:** `docs/tasks/377/mvp-product-spec.ru.md`, especially §§5–6, 11, 14, 16, 20, 22, 25.
2. **[2] Tier 1/2 accepted local coordinator evidence:** `docs/tasks/377/phase3/r4/coordinator-adr.md`, `state-machine.md`, `fault-matrix.md`, `command-event-schemas.json`, and `probe-results.json`.
3. **[3] Tier 2 primary local security contract:** `docs/tasks/377/phase3/r8/remote-authority-threat-model.md`, including session, per-message authorization, projection and audio-leader controls.
4. **[4] Tier 1 direct synthetic measurement:** `surface_protocol_probe.py`, `test_surface_protocol_probe.py`, `probe-results.json`; final commands/results above.
5. **[5] Tier 2 primary web standard:** [W3C Pointer Events Level 3](https://www.w3.org/TR/pointerevents3/), §§4, 8–10, fetched 2026-08-16.
6. **[6] Tier 2 primary protocol standard:** [RFC 6455 §5.4](https://www.rfc-editor.org/rfc/rfc6455#section-5.4) and [WHATWG WebSockets Standard](https://websockets.spec.whatwg.org/), fetched 2026-08-16.
7. **[7] Tier 2 primary web standard:** [WHATWG Fullscreen Standard](https://fullscreen.spec.whatwg.org/), `requestFullscreen()` algorithm and transient-activation requirement, fetched 2026-08-16.
