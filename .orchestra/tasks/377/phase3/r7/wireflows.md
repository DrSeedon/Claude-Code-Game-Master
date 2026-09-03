# R7 table, scene, admin, and composite wireflows

All arrows below are application messages after the R8-authenticated WebSocket upgrade. HTTP commissioning, CSRF, one-time socket ticket, Origin validation, session lookup and per-message authorization precede these flows. Every message uses a closed schema; `room`, role, actor allowlist, consumer identity and capabilities come from socket context.

## Shared safe projection batch

```text
coordinator           projection worker       table             scene             admin
    | world commit + projection task (one R4 transaction)          |                 |
    |------------------------>|                                     |                 |
    |                         | build table.v1 from revealed state  |                 |
    |                         | build scene.v1 from revealed state  |                 |
    |                         | build admin.v1 from operational rows|                 |
    |                         | validate all closed schemas + canary scan             |
    |                         | persist batch:N + three stable events                |
    |                         |-------------------->| event seq T    |                 |
    |                         |------------------------------------>| event seq S      |
    |                         |------------------------------------------------------>|
    |                         |       each reducer stages, renders, then ACKs          |
    |<------------------------| designated table/composite ACK gates presentation     |
    | coordinator=committed; enqueue audio intent; scene/admin delivery may catch up  |
```

The three envelopes share `projection_batch_id`, `aggregate_version`, and `world_revision`, but have distinct stable `event_id`, `surface`, sequence and payload schema. Full replacement snapshots/events are the MVP contract; JSON Patch and content-based dedupe are excluded.

Only the room's server-designated presentation consumer can make its table ack satisfy the R4 presentation gate. Other acks advance their own delivery cursors and health. A disconnected scene/admin never makes world execution repeat and does not block the next committed turn; it catches up from the latest safe batch.

If table or scene projection validation fails, the worker publishes neither player envelope and retains the entire prior safe player batch. A separately constructed operational admin update reports `projection_schema_mismatch` / `repair_projection_schema`, current committed versions, and last-safe per-surface versions without including the rejected field or value. The UI must show degraded/lagging rather than claim convergence.

## Table flow

```text
table                         server session/coordinator                    kernel
  | client.hello(rehydrate, reducer versions) |                               |
  |------------------------------------------>|                               |
  |<-- server.welcome + table snapshot -------|                               |
  | stage detached view; atomic DOM swap      |                               |
  |-- projection.ack(event/seq/schema) ------>| durable table cursor           |
  |                                           |                               |
  |-- select allowed logical actor ---------->| validate session actor set     |
  |-- final text/transcript ----------------->| persist draft/typed plan        |
  |<-- table projection: exact draft summary + single-use approval nonce ------|
  |-- approve(turn,draft_version,nonce) ----->| consume approval; no world edit|
  |                                           |-- internal typed envelope ---->|
  |                                           |<-- structured result ----------|
  |                                           | atomic world/result/outbox commit
  |<-- table projection event ----------------|                               |
  | render succeeds                           |                               |
  |-- projection.ack ------------------------>| commit presentation/audio task |
```

The approval body never contains room, actor, role, plan, command type, command arguments or target. Unknown fields reject the whole request. Pointer input produces only an intent (selection, destination, overlay); the server validates grid/range/LOS/resources and constructs any canonical typed command only through the approved coordinator route.

## Scene flow

```text
scene                         server projection stream
  |-- client.hello ---------->|
  |<-- welcome + scene snapshot (public asset refs/subtitle/activity/result)
  | render to detached scene  |
  |-- projection.ack -------->|
  |<-- later scene event -----|
  | gap or unknown schema? keep last safe scene; request resync; no partial render
```

The scene socket has no message schema for draft, actor selection, approval, overlay, admin control, command or reveal. Scene audio is possible only if that exact session was separately commissioned with `audio.candidate` and later receives the current room lease.

## Operational admin controls

Every operation has a stable `operation_id`, `expected_control_revision`, closed operation enum and operation-specific parameters. Exact duplicates return the stored operational result. A conflict or denial cannot change world, control, command, outbox, cursor, overlay or lease state except the redacted audit row.

| Operation | Guard and state change | Observable result; world effect |
|---|---|---|
| `start` | admin capability; stopped/paused → running; increment `control_revision` | input/coordinator may accept new turns; `world_revision` unchanged |
| `pause` | running → paused; stop accepting new input/provider starts; do not roll back committed work | explicit paused projection/audio stop; world unchanged |
| `end` | current room → ending/ended; cancel uncommitted provider/audio work and close admission | recoverable ended state; world unchanged |
| `diagnostics` | read-only | enum/bucket microphone, WS, provider and projection health; no raw errors/content; no revision change |
| `set_volume` | `0..1`; increment control revision | current leader receives config; no world/aggregate change |
| `cancel_generation` | exact current attempt/context; idempotent cancellation | late provider events dropped/audited; no kernel call |
| `cancel_audio` | exact `line_id/context_id`, or current line selected server-side | revoke context, increment audio fence, `audio.stop` to every socket, discard buffers; no kernel call |
| `reproject_last_safe` | server resolves last validated safe batch | new delivery event IDs for the same batch/version; explicit re-render, no world mutation/audio replay |
| `retry_unfinished_stage` | target must equal current R4 `recovery_action` and be uncommitted | retry draft/execution preparation/projection/audio stage only; never rerun committed kernel work |

Admin may never supply replacement text, plan, command, world patch, reveal, actor or story decision. `reproject_last_safe` does not retry audio. Audio retry is a distinct server-side technical operation and never dispatches the kernel.

## Composite fallback

```text
composite table socket              projection service
  |-- hello (table.v1 + scene.v1 reducer support) -->|
  |<-- welcome(role=table, streams=[table,scene]) ----|
  |<-- table snapshot batch:N ------------------------|
  | stage map pane; do not expose yet                  |
  |<-- scene snapshot batch:N ------------------------|
  | stage cinematic pane; atomic two-pane swap         |
  |-- ack table event + ack scene event -------------->|
```

If only one half of batch N arrives, composite keeps both panes at batch N−1 and requests resync for the missing stream. It never combines table N with scene N−1. The table pane remains primary; the scene pane is sidebar/overlay. Fullscreen is a local presentation request and cannot change capabilities, subscription or audio ownership.

## Planning overlay flow

```text
table             ephemeral overlay service            all table/composite clients
  | overlay.create(command_id, id, arrow/marker, points, ttl 1..30s) |
  |----------------------->| authorize table; validate visible grid  |
  |                        | dedupe command; store outside canonical DB aggregate
  |                        |-- overlay.upsert(seq, absolute expires_at) ---------->|
  | reconnect              |                                                      |
  |<-- overlay.snapshot(active as of server_now, overlay_seq) --------------------|
  |                        | injected clock reaches expires_at                    |
  |                        |-- overlay.expired(seq,id) --------------------------->|
```

Overlay messages contain public board coordinates, a public creator reference and no arbitrary text in v1. Reconnect replaces the entire local overlay set. A sequence gap triggers another overlay snapshot. Client expiry is a safety hide based on server time; server expiry/tombstone is authoritative. An overlay command ID remains a tombstone through the replay window so replay after expiry cannot resurrect it. Overlay create/remove/expiry never changes `aggregate_version`, `world_revision`, a typed command, approval state or audio.

## Audio leader flow

```text
eligible client A             lease service                 eligible client B
  | audio.candidate(unlocked, buffer<=250ms) |                       |
  |-------------------------->|<--- candidate -----------------------|
  |<-- lease generation G ----|                       no lease -------|
  |<-- audio.play(G, ids) -----|                                      |
  | renew G; bounded buffer    |                                      |
  X disconnect/renewal loss    |                                      |
  |                            | expire/revoke G; fence stale ACKs     |
  |                            |-- lease generation G+1, not_before -->|
  | stale G cannot play/renew  |                                      |
```

The lease store has at most one current row per room. Generation is monotonically increasing. Playback requires exact current `(lease_id,generation,consumer_id)` and a server-issued `audio.play` bound to stable `presentation_id/line_id/context_id/text_event_id`. Nonleaders receive no playable media command. A leader hard-stops before its conservative local lease deadline and buffers at most 250 ms. Without a bounded clock/RTT estimate, the client stops and the server fails silent. After ungraceful loss, the successor's `not_before` is no earlier than the old server expiry plus the maximum permitted old buffer and measured clock-uncertainty guard; silence is preferred to overlap. A cooperative release with confirmed buffer drain may elect immediately.

`cancel_audio` increments the fence, sends `audio.stop` to all sockets, closes provider generation and discards queued/late chunks for the context. Replaying audio creates a new playback attempt/generation binding, never a game command or world mutation.
