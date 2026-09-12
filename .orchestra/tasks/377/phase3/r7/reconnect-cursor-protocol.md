# R7 reconnect and cursor protocol

## Transport boundary

WebSocket is an ordered byte/message transport only within one live connection. RFC 6455 requires fragments of one message to arrive in sender order, but that does not supply application replay, cross-connection ordering, durable acknowledgement or effects-once rendering [4]. R7 therefore assumes at-least-once projection delivery and treats reconnect, replay/live overlap, gaps and duplicates as normal.

Upgrade follows R8: TLS; exact production Origin allowlist; valid `Secure`, `HttpOnly`, `SameSite=Strict` session cookie; and a CSRF-minted, single-use, ≤30-second socket ticket bound to session/room/role/origin/purpose. A browser can offer the ticket as a non-URL `Sec-WebSocket-Protocol` value alongside `room.v1`; the server consumes it at upgrade, negotiates only `room.v1`, and redacts the raw header. If the deployment stack cannot prevent the raw subprotocol ticket from access/error logs, it must choose another non-URL upgrade mechanism and prove the same properties before exposure. Room IDs and reusable bearers are absent from the socket URL.

Every inbound message rechecks the session record. Expiry, revocation, role/room change, bad schema or unauthorized message closes or rejects before state mutation. A reconnect obtains a new socket ticket. It resumes projection delivery only; browsers never auto-resend approval, draft, overlay, admin operation or audio control messages.

## Durable identity

| Field | Authority and meaning |
|---|---|
| `consumer_id` | stable opaque device/surface consumer assigned by the server session, not chosen in `client.hello` |
| `connection_id` | one socket attempt; changes on every reconnect |
| `projection_batch_id` | stable safe projection boundary shared by table/scene/admin successful envelopes |
| `event_id` | stable delivery identity, e.g. `projection:{batch}:{surface}`; never payload/content hash |
| `stream_seq` | contiguous integer in one `(room,surface,projection_schema)` stream; used to detect gaps, not to authorize |
| durable cursor | highest successfully reduced/rendered sequence per `(room,surface,consumer_id,projection_schema,reducer_version)` |
| `aggregate_version` / `world_revision` | authoritative R4 versions at the safe projection boundary |

A schema/reducer upgrade uses a new cursor key and requires a snapshot. The server never interprets a higher client cursor as truth. Client cursor hints may only make the server choose a more conservative replay; the durable server ack and a new snapshot are authoritative.

## New document and reconnect handshake

1. The document obtains a one-time socket ticket by CSRF-protected POST, opens the socket, and sends `client.hello` containing only protocol version, supported reducer versions and `rehydrate`.
2. Server loads session-owned room/role/capabilities/consumer ID and returns `server.welcome`. Unsupported protocol/reducer fails closed before any projection bytes.
3. A new document always uses `rehydrate=true`. No projection payload or cursor is required in Local Storage/IndexedDB. HTTP projection responses and socket bootstrap endpoints use `Cache-Control: no-store`.
4. Server reads one already validated safe projection batch and each stream high-water under a consistent read, marks `through_seq`, then buffers later outbox events for that connection.
5. Server sends full `projection.snapshot` envelope(s). Normal clients receive one; composite receives table and scene for the same batch.
6. Client validates the exact JSON schema and supported reducer version, builds a detached render tree/state, and swaps it atomically. Composite swaps only when both envelopes name the same batch/version.
7. Only after reducer plus render succeeds does the client send `projection.ack` for the exact event/batch/surface/seq/schema/reducer. Server transaction monotonically advances that consumer cursor. A lower/duplicate ack returns the stored result; a higher/gapped/mismatched ack is rejected and audited.
8. Server releases buffered events with `seq > through_seq` in order, then joins live delivery. Replay and live may still duplicate an ID; the reducer's applied-ID check makes the second delivery a no-op.

If the same live document reconnects and still has an intact rendered state, it may request bounded replay after its in-memory cursor. The server still uses its durable cursor, and it may force a snapshot for cursor age, retention, schema, integrity or any ambiguity.

## Reducer transaction

For each envelope, the browser performs this indivisible logical sequence:

```text
1. authorize stream from server.welcome; reject any other surface
2. validate closed envelope + payload schema and reducer version
3. if event_id already applied or seq <= cursor: ACK stored result / render nothing
4. if seq != cursor + 1: keep current safe view; request resync
5. reduce into a detached immutable view model
6. build/render into a detached DOM/canvas scene
7. atomically swap visible view
8. record event_id + seq in current document memory
9. send projection.ack
```

An exception in steps 1–7 changes none of visible view, applied IDs or cursor and sends no ack. Replay retries the same stable event. If a DOM/canvas API cannot support a detached swap, the implementation must use a rollbackable render boundary or treat the current renderer as incompatible; “cursor then render” is forbidden.

Applied IDs may be bounded to the retained sequence window because `stream_seq <= cursor` is also a duplicate. Content/text equality is never a dedupe signal: two legitimate events may have identical narration.

## Drop, reorder and render-failure decisions

| Observation | Client behavior | Server behavior |
|---|---|---|
| exact duplicate event ID/sequence | no second render; repeat/stored ack allowed | return stored ack result; no cursor/world change |
| `seq == cursor+1` | stage/render/ack | advance only after exact ack |
| `seq > cursor+1` | retain safe view; stop applying that stream; request resync | snapshot or bounded replay from durable cursor |
| `seq <= cursor`, unknown ID | no render; report protocol inconsistency | audit/integrity check; normally force snapshot |
| unknown field/type/schema | render nothing; keep cursor; show local degraded status | fail projection publication when caught server-side; safe admin error only |
| render exception | keep prior view, ID unseen and cursor unchanged | replay same stable event; repeated failure becomes safe `projection_schema_mismatch`/client health alert |
| socket closes | show explicit disconnected veil; disable authoritative actions and audio at deadline | do not mutate locally; expire/revoke lease; accept no old-socket message |
| internet returns | obtain new ticket and rehydrate/resume | reconcile from authoritative safe snapshot/cursor only |

There is no offline authority. While disconnected, pointer previews may remain visual but move/attack/approval/admin actions are disabled; overlays are local drafts until accepted by the server and may be discarded.

## Composite atomicity

Composite holds staging slots keyed by `projection_batch_id`. It exposes a new batch only after one valid `table.v1` and one valid `scene.v1` envelope with equal aggregate/world versions are present. It then swaps both panes and acknowledges both events. Any mismatch, missing half, render error or schema mismatch retains the previous two-pane batch and requests resync. One stream never advances visibly by itself.

## Projection failure and convergence definition

The convergence target is the latest **validated safe projection batch**, not necessarily the latest committed world revision during a projection incident. On the success trace, every connected surface eventually displays the same batch/aggregate/world boundary. On projection failure, table/scene/composite retain their last safe batch; admin explicitly reports current committed versions versus last-safe projected versions and `repair_projection_schema`. Claiming convergence to the rejected version is forbidden.

An audited `reproject_last_safe` creates new delivery event IDs referencing the same safe batch/version. This intentionally renders again and is distinct from an accidental duplicate. It cannot enqueue audio or call the kernel.

## Heartbeat and resource bounds

- `server.welcome.heartbeat_ms` is 1–30 seconds; two missed intervals mark the connection unhealthy. Exact deployment values are an I8 measurement, not fixed here.
- Replay is bounded by retention and message/byte limits. Exceeding either forces a full snapshot.
- Unknown or oversized JSON closes with an application protocol error before deserialization into domain commands.
- Backpressure never drops a new full projection while advancing its cursor. A slow consumer is disconnected and rehydrates; the last safe visible view remains.
- Overlay sequence is separate and ephemeral. A gap replaces overlays from `overlay.snapshot`; it cannot affect projection cursor or aggregate/world version.
- Audio lease generation is separate. Projection ack cannot grant audio authority.

## Synthetic evidence

`test_surface_protocol_probe.py` injects replay/live duplication, a reordered gap, a dropped range repaired by snapshot, and a render exception. The recorded run shows four presentation clients (three core surfaces plus composite) at aggregate version 3; duplicate event render count 1; failed-render cursor 0 before retry and 1 after successful retry. These are tier-1 measurements of the synthetic reducer, not evidence about an actual browser, network, reverse proxy or database.

## Sources

1. Canonical local product source: `docs/tasks/377/mvp-product-spec.ru.md`, §§5–6, 14, 16 and 25 — tier 2 primary local specification.
2. R4: `docs/tasks/377/phase3/r4/state-machine.md`, `coordinator-adr.md`, `fault-matrix.md`, `command-event-schemas.json` — tier 1 synthetic measurement plus accepted local decision contract.
3. R8: `docs/tasks/377/phase3/r8/remote-authority-threat-model.md` — tier 2 primary local security contract.
4. [RFC 6455 §5.4, Fragmentation](https://www.rfc-editor.org/rfc/rfc6455#section-5.4) — tier 2 IETF primary protocol specification; message fragments are delivered in sender order.
5. [WHATWG WebSockets Standard](https://websockets.spec.whatwg.org/) — tier 2 living primary web-platform specification; browser WebSocket interface and handshake integration.
