# R7 capability matrix

Status: closed research contract for I1/I3/I8. The matrix refines the R8 server-owned roles; it does not create a browser-trusted role system.

## Admission rule

Effective authority is the intersection of the server-side session record, the socket's commissioned purpose, the current room policy, and current session validity. `room_id`, `role`, `surface`, `actor_id`, `consumer_id`, audio priority, and capability names in a client body are never authority. An action schema that does not need one of those fields rejects it as unknown. A selector such as `surface` in `projection.ack` is accepted only to name one of the socket's already authorized streams.

Authorization runs on every message before any command, outbox, overlay, control, audio-lease, or cursor mutation. Authenticated denial adds a redacted audit row; protected state stays byte-identical.

## Role and presentation matrix

| Server session / mode | Projection streams | May send | Explicitly denied |
|---|---|---|---|
| `table` | `table.v1` | submit final text/transcript; select one actor from the session's server allowlist; approve/reject exact current draft; table projection ack; create/remove own planning overlays | admin operations; scene/admin projection; arbitrary typed command; another room/actor; kernel/provider/DB access |
| `scene` | `scene.v1` | scene projection ack | draft, actor selection, approval, overlay write, admin operation, typed command, table/admin projection |
| `admin` | `admin.v1` | operational start/pause/end; diagnostics; volume; cancel generation/audio; reproject last safe; retry the exact unfinished technical stage; admin ack | draft/approval; actor selection; story/world edit or reveal; typed command; table/scene/private projection; creative override |
| `table` + `presentation_mode=composite` | exact `table.v1` + `scene.v1` | same game actions as `table`; ack both streams after one atomic composite swap | admin projection/capabilities; a fourth composite schema; independently advancing one pane |
| internal coordinator/kernel | no browser projection | R4 internal typed execution/projection/audio commands under a server envelope | browser reachability; free-form/model authority; bypass of approval/version/idempotency checks |

`composite` is not a role. It is a commissioned table session with the two player-safe projection-read capabilities. It never receives admin metadata and cannot broaden the table action set.

## Closed capability list

| Capability | Table | Scene | Admin | Composite table | State it may change |
|---|:---:|:---:|:---:|:---:|---|
| `projection.read.table` / `projection.ack.table` | yes | no | no | yes | delivery cursor only, after reducer success |
| `projection.read.scene` / `projection.ack.scene` | no | yes | no | yes | delivery cursor only, after reducer success |
| `projection.read.admin` / `projection.ack.admin` | no | no | yes | no | delivery cursor only, after reducer success |
| `draft.submit` | yes | no | no | yes | R4 coordinator draft state, never world state |
| `actor.select` | yes, allowed set only | no | no | yes, allowed set only | current logical selection, never physical identity |
| `draft.approve` / `draft.reject` | yes, exact current immutable draft | no | no | yes | approval state; world remains unchanged until internal execution |
| `overlay.write` | yes | no | no | yes | separate TTL overlay store only |
| `room.start` / `room.pause` / `room.end` | no | no | yes | no | operational `control_revision`, not world revision |
| `diagnostics.read` | no | no | yes | no | none; returns enum/bucket health only |
| `volume.set` | no | no | yes | no | room audio configuration/control revision only |
| `generation.cancel` / `audio.cancel` | no | no | yes | no | provider/audio attempt state only; never kernel/world |
| `projection.reproject` | no | no | yes | no | delivery outbox for the last safe batch only |
| `stage.retry_unfinished` | no | no | yes | no | the server-named uncommitted R4 stage only |
| `audio.candidate` | separately commissioned | separately commissioned | never | separately commissioned | room audio lease only |
| `kernel.execute`, story/world edit/reveal, arbitrary tool | never | never | never | never | no public path exists |

Audio eligibility is orthogonal to surface role and omitted by default. A server-side room policy normally gives the physical table/composite first priority and may commission the scene display as failover. The client may report that playback is user-unlocked; it cannot claim priority or grant itself the capability.

## Negative cases and zero-mutation boundary

| Attack | Decision | Must remain byte-identical; denial audit may append |
|---|---|---|
| payload claims another `surface` or `role` | schema reject or 403 | world/aggregate/control revisions; command/result/outbox/overlay/audio/cursor records |
| table claims an actor outside server allowed set | 403 | same protected state |
| room-A session names room B | uniform 403/close before existence disclosure | both rooms' state and projection bytes |
| table requests admin projection or operation | 403 | protected state; no admin bytes |
| admin submits/approves a draft, reveals a secret, or sends a command | 403/422 | world, draft, command and projection records |
| scene drafts, approves, overlays, or claims audio without a lease capability | 403 | protected state |
| expired/revoked session or consumed one-time ticket/nonce | 401/409 and socket close where applicable | protected state; a legitimate first consumption remains unchanged |
| typed command in HTTP/WS/model/admin/approval input | 404/403/422; data cannot dispatch | no command/result/outbox/mutation row |
| nonleader or stale audio generation reports playback | reject and issue `audio.stop` | lease row and world state |

The synthetic negative suite exercises seven authorization cases plus enrollment replay. Its protected fingerprint includes world/aggregate/control revisions, command-facing stream lengths, overlays, audio lease, volume and canonical bytes; every denial left it unchanged while denial audit rows increased.

## Admin metadata allowlist

The admin browser receives only the fields defined by `AdminPayload` in `projection-schemas.json`: operational run state; coordinator stage/recovery action and numeric versions; per-surface status/version/ack-age bucket; audio/input/provider enum health; a safe error code/stage/correlation hash/retryable flag; currently allowed recovery enum values; and the last operation ID/kind/outcome/operator hash.

There is no schema path for narration, map cells/tokens, actor/NPC names, world facts, typed plans/arguments, provider prompts/results, raw transcript, raw errors/stack traces, filesystem paths, service URLs, credentials/tokens/nonces, private audit identity, or secret values. Admin projection is built from operational records rather than by filtering the canonical world object.
