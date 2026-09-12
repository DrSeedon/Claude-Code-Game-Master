# R8 — Remote-authority threat model

Status: fail-closed design and future negative-test oracle. No remote service, token, provider, room, repository, or production state was created or exercised. The model implements the canonical requirement that the VPS is authoritative, browsers receive only projections, and model text cannot mutate world state.

## Security objective and invariant

An attacker controlling a browser, WebSocket payload, model response, replayed request, or another room must be unable to cause a mutation outside the authenticated session's server-side room and capability. The only mutation path is:

```text
authenticated table session
  -> server-owned room/role/allowed-actor lookup
  -> persisted immutable draft and typed plan
  -> current single-use approval for the same draft/version
  -> internal capability kernel validates server envelope
  -> atomic audit + outbox + world revision commit
  -> allowlisted projections
```

For every rejected, expired, replayed, cross-room, stale, spoofed, or unauthorized request:

```text
HTTP/WS result is 401, 403, or 409 as specified
AND world_revision_after == world_revision_before
AND mutation_count_after == mutation_count_before
AND no unauthorized projection, command payload, token, or secret is emitted
AND a redacted denial audit record exists when an authenticated request reached authorization
```

An audit-write failure before mutation is a hard failure and leaves the world unchanged. This route chooses one authoritative relational database and two explicit transactions: an approval transaction that consumes consent and durably queues an immutable command without changing the world, followed by an execution transaction that atomically records command consumption, execution audit, mutation ledger, world mutation/revision, immutable result, and outgoing presentation event. The kernel performs no external side effect inside or before that execution commit. If R4 selects storage that cannot provide this transaction boundary, the zero-or-duplicate-mutation guarantee is **blocked** and remote mutation must not be exposed.

## Assets, actors, and trust boundaries

Protected assets are canonical world state and revision, private GM/story state, draft and typed-command plans, room membership, logical actor selection, audio-leader lease, provider credentials, sessions/tickets/nonces, audit records, and player/admin projections.

Threat actors include an unauthenticated internet client, a malicious or compromised table browser, a browser from another room, a compromised scene display, an operational admin exceeding scope, injected model/provider output, an XSS/CSWSH adversary, a network observer below TLS, and an operator or CI credential with excessive privilege.

Trust boundaries are browser↔VPS HTTP/WebSocket, room A↔room B, table/scene/admin projections, coordinator↔model/provider adapters, coordinator↔capability kernel, kernel↔state transaction, and application↔audit/secret stores. TLS authenticates transport endpoints but does not authorize a room, role, actor, turn, or mutation.

### Server-owned roles

| Session role | Allowed | Explicitly denied |
|---|---|---|
| `scene` | Read one room's allowlisted scene projection; reconnect from a bounded cursor | Draft, select actor, approve, invoke commands, read GM/admin/private state, or become audio leader unless separately leased |
| `table` | Read one room's table projection; submit transcript/text as a draft; select one logical hero from the room's server allowlist; approve or reject the current immutable draft; receive presentation | Operational administration, story/GM override, arbitrary command submission, another room, secret/private projection, direct database/provider/kernel access |
| `admin` | Operational start/pause/end, microphone/connections/volume, cancel, reproject, and retry only an unfinished technical stage for assigned rooms | Acting as GM, changing story/world facts, selecting a hero, approving or executing a turn, revealing private plan/state, submitting typed commands, overriding AI decisions |
| internal coordinator/kernel | Execute only a typed, allowlisted command from a valid server envelope with expected world revision and idempotency key | Browser reachability, free-form commands, model-originated authority, or bypass of approval/state/version checks |

`surface`, `role`, `room_id`, `actor_id`, and capabilities in client payloads are untrusted hints or rejected fields. The authoritative values come from a server-side session record on every HTTP request and every WebSocket message. A shared table intentionally identifies a **logical selected hero**, not the physical speaker. Diarization or voice likeness cannot become authentication. A person at the table may select any hero the room policy permits; the enforceable property is that this cannot cross the table role, room, or allowed-hero set.

## Authentication and session protocol

### Commissioning

1. An already authorized operator asks the server to mint a cryptographically random opaque enrollment ticket for exactly one `room_id`, `surface_role`, device label, issuer, and purpose. Lifetime is at most 60 seconds. The database stores a hash, `jti`, issue/expiry time, and unused state.
2. The ticket is delivered out of band and never put in a query string, referrer-bearing page, analytics event, application log, or persistent browser storage. Its exchange endpoint requires TLS and an exact expected method/content type.
3. The server atomically verifies hash, purpose, role, room, expiry, and unused `jti`, then consumes it before issuing the session. Concurrent exchanges yield at most one success. Expired, unknown, or consumed tickets are indistinguishable to the client.
4. The session is an opaque high-entropy identifier stored only as a `Secure`, `HttpOnly`, `SameSite=Strict` cookie. The server record owns role, room, device, expiry, revocation epoch, and capabilities. Session rotation occurs after commissioning, privilege change, recovery, or suspected compromise. Logout/revocation closes associated sockets.

If a signed token is ever used instead of an opaque lookup, the validator pins algorithm and token type and validates signature, issuer, audience, subject, expiry, not-before, `jti`, and token kind. RFC 8725 specifically requires algorithm verification and audience/issuer validation and recommends mutually exclusive validation rules for different token kinds [1]. Enrollment, session, WebSocket, approval, audio lease, and provider tokens therefore never share a validator or audience.

### HTTP and WebSocket

State-changing HTTP uses the session cookie plus a per-session CSRF token bound to the request. WebSocket upgrade accepts an explicit production Origin allowlist, an authenticated session, and a single-use WebSocket ticket minted by a CSRF-protected POST. The WS ticket lifetime is at most 30 seconds, is bound to the session/room/role/origin/purpose, and is atomically consumed at upgrade. No bearer appears in the WebSocket URL. OWASP recommends explicit Origin validation, authentication, authorization for every message, and avoiding token/message content in logs [3].

Authentication is revalidated at least on every message through the session lookup, and socket closure is immediate on expiry/revocation/room-role change. Reconnect establishes a new socket ticket and resumes only an allowlisted projection cursor; it never replays an approval or client command. RFC 9700 recommends audience restriction, least privilege, and sender-constrained or rotated credentials to reduce replay [2]. Server-side session binding and single-use purpose tickets implement those properties without treating a reusable bearer as proof of device identity.

## Approval and mutation protocol

1. Final transcript or text creates a draft. The coordinator stores `turn_id`, room, selected logical actor, normalized input, typed plan, plan hash, `draft_version`, expected world revision, state `awaiting_approval`, and a random single-use approval nonce. Provider/model output has no database or kernel capability.
2. The table projection displays the exact human-readable draft/plan for confirmation. The approval request accepts only `turn_id`, `draft_version`, and `approval_nonce`; it has no command, arguments, actor, room, role, plan, or target fields. Unknown fields are rejected rather than ignored.
3. The **approval transaction** loads and locks the server session and stored turn; verifies `table`, same room, allowed actor, `awaiting_approval`, unexpired/unconsumed nonce, exact version/hash, and expected world revision; consumes the nonce; writes the approval audit; creates a unique immutable command in `approved_pending`; and marks the turn approved. It performs no world mutation and emits no presentation. A crash before commit leaves the nonce usable and no command; a crash after commit leaves one recoverable pending command and a consumed nonce.
4. A worker selects the durable `approved_pending` command. In a single database **execution transaction**, it locks the command and affected world aggregate, revalidates command schema/capability, room/actor eligibility, expected revision, and absence of a mutation-ledger row for `command_id`. The in-process kernel is a deterministic/pure state transition with no network, filesystem, provider, audio, or other external side effect. Unknown command or argument fails before mutation.
5. The same execution transaction writes the unique mutation-ledger row, applies the world change and next revision, records the immutable result and execution audit, creates the outgoing presentation event, and marks the command/turn committed. A crash before commit rolls all of these back; recovery retries the same pending command. After commit, recovery finds the ledger/result and never invokes the kernel again.
6. Publishing the committed outgoing event and recording its delivery acknowledgement happen after the execution commit. Publication can be at least once; the projection/presentation consumer deduplicates the immutable event ID. A crash before acknowledgement may republish the same event but cannot repeat world mutation. The acknowledgement transaction cannot edit the world, command result, or mutation ledger.
7. A stale expected revision becomes a visible conflict recorded without world mutation and returns to a new draft/approval cycle; it is never auto-rebased under old consent. Browser replay of a consumed approval is denied. Internal redelivery of an already committed `command_id` reads the stored result without dispatching the kernel.
8. Projection is an allowlist generated from committed state. Admin, table, and scene clients never receive provider prompts, secrets, internal plan fields, GM-only state, another room's state, or kernel command envelopes. Exactly one server-issued room audio-leader lease may render audio; lease expiry/revocation is server-authoritative.

There is no public `/command`, `/kernel`, `/execute`, database, Bash, SQL, arbitrary tool, or provider callback mutation endpoint. A typed command found in request text, model output, URL, WebSocket message, admin request, or approval payload is data and cannot dispatch. Provider callbacks and late model/audio events must match stored purpose, turn/attempt ID, room, and current stage; late or canceled attempts are audited and dropped with zero mutation.

## Threat-to-control and test matrix

| Threat / attacker action | Fail-closed authentication and authorization | Audit evidence | Required negative oracle |
|---|---|---|---|
| Surface spoofing: scene/table payload claims `admin`; actor spoofing: payload claims another hero or actor outside the room allowlist | Ignore no authority-bearing client claim: reject unknown authority fields; load immutable session role/room and allowed actors; physical voice identity is never trusted | hashed session ID, server role/room, requested field names (not values containing speech), selected actor decision, deny reason | `test_surface_actor_payload_cannot_override_session_claims`: 403/validation failure; no admin projection; revision/mutation count unchanged |
| Cross-room REST read/write using room A session for room B ID | Object lookup is scoped by server session room before existence disclosure; unauthorized room responds uniformly; projection cache keys include authorized room and role | hashed session, authorized room, requested-room hash, route, decision | `test_cross_room_rest_access_has_no_read_or_write`: no room-B bytes or existence signal; zero mutation |
| Cross-room WebSocket subscription/event injection | WS ticket and socket context are bound to one session/room/role/origin; every subscription and message reauthorizes; server supplies room to downstream calls | connection ID, hashed session, bound room/role, message type, denial/close code | `test_cross_room_websocket_access_has_no_projection_or_mutation`: no B event, socket closes, zero mutation |
| Expired enrollment/session/WS/approval token | Server clock validates expiry and revocation from stored record on each use/message; no grace for mutation; expired socket closes | token kind and hashed `jti`, issuer, expiry bucket, route, decision; never raw token | `test_expired_ticket_session_and_nonce_are_rejected`: 401/409 and zero mutation |
| Replayed ticket, nonce, or captured approval | Random one-time `jti`/nonce is atomically consumed before issue/approval; approval bound to session, room, turn, version, plan hash and expected revision; mutation ledger deduplicates only internal command recovery | original consumption and every replay denial linked by hashed `jti` or command ID | `test_replayed_ticket_and_approval_are_denied_after_success`: first complete and record the legitimate issue/approval/execution, then snapshot revision and session/command/outbox/mutation/result state; every later sequential and concurrent replay is 409/denied, every protected-state snapshot stays byte-identical while only denial-audit rows increase, and each replay has its denial row. A separate simultaneous-race test permits exactly one original winner and requires every loser denied |
| Table→admin escalation | Closed capability matrix is stored server-side; table session cannot call operational admin endpoints or request admin projections; role changes require new commissioning by an authorized operator | server role, capability, route, decision and reason | `test_table_cannot_call_admin_or_read_admin_projection`: 403, no private bytes, zero mutation |
| Admin→GM/story escalation | Admin API contains operational enum only; admin cannot draft/select/approve/execute/reveal or modify world/story; retry references a stored unfinished technical stage and cannot alter its plan | admin identity, assigned room, operation enum, target stage ID, before/after revision | `test_admin_cannot_approve_execute_or_change_story`: every attempt 403/schema rejection and zero mutation |
| Direct typed-command bypass of approval through HTTP, WS, model output, or approval body | No public command endpoint; strict schemas reject command fields; only stored `awaiting_approval` draft can create internal envelope; LLM/provider adapter lacks kernel/DB capability | rejected route/message type, turn/version, schema/authz reason; never command secret/content beyond safe type | `test_direct_typed_command_and_approval_injection_are_rejected`: 404/403/422; no command/outbox row; zero mutation |
| Approval after plan/draft change or world revision conflict | Approval binds nonce to immutable plan hash, `draft_version`, actor, room and expected revision; edit invalidates nonce; transaction compares current state | turn, offered/current version/hash fingerprints, revision, decision | `test_stale_or_changed_draft_cannot_execute`: 409, nonce invalidated, zero mutation |
| Cross-site WebSocket hijacking and CSRF | Exact Origin allowlist, SameSite cookie, CSRF-protected ticket-mint POST, single-use WS ticket; reject `Origin: null` and absent/unexpected Origin | origin category, connection ID, route, decision; do not log token | `test_bad_origin_and_missing_csrf_cannot_open_authority_socket`: upgrade rejected and zero mutation |
| Session theft, XSS, or browser storage leakage | HttpOnly cookie, no authority token in URL/local storage, short idle/absolute expiry, CSP and output encoding, session rotation/revocation, least privilege | session creation/rotation/revocation and security events; no token or player speech | `test_revoked_session_closes_socket_and_cannot_mutate`: socket closed, subsequent HTTP/WS denied, zero mutation |
| Duplicate network delivery, reconnect, crash, or late provider result | immutable turn/attempt/command IDs, persisted-before-work outbox, unique constraints, expected revision, terminal result replay, late-attempt rejection | state transitions and IDs, recovery reason, before/after revision | `test_duplicate_and_recovered_command_is_exactly_once` plus crash-point parametrization: one commit/result, never two mutations |
| Projection confusion or secret leakage | Typed allowlists per surface/role; cache key includes room/role/revision; serialization denies unknown fields; no shared full-state payload filtered in browser | projection schema version, room/role/revision, field-set hash | `test_projection_allowlists_do_not_cross_room_role_or_secret_fields`: forbidden canaries absent from bytes, logs, caches and errors |
| Audio-leader spoof or duplicate playback | Server grants one expiring room/role-bound lease; presentation event has unique ID; nonleader ACK cannot acquire authority; cancel invalidates pending playback and late chunks | leader session hash, lease generation/expiry, presentation ID, ACK/cancel/result | `test_only_current_audio_leader_renders_each_presentation_once`: one render; stale leader and late chunks rejected |

## Audit contract

Every security-relevant decision records timestamp, correlation ID, event type, authenticated principal/device and session as salted hashes, server-side role/room/capability, route or WS message type, turn/draft/command/attempt IDs where applicable, current and expected revision, decision, reason code, and outcome. Mutations add before/after revision and affected aggregate IDs. Enrollment, privilege change, login failure, expiry, replay, cross-room denial, schema rejection, approval, execution, projection, audio lease, provider callback, and break-glass events are covered.

Logs never contain raw tokens/cookies/nonces, authorization headers, provider secrets, raw player speech, unrestricted model prompts/results, enrollment audio, or full private state. Security operations can correlate hashes without turning logs into a replay or content database. Audit access is independent of application writers; integrity/retention failure alerts the security owner. Denied anonymous scanning may be sampled/rate-limited, but any authenticated authorization denial is retained.

## Future test command and fixture requirements

The destination security suite has one named command:

```bash
uv run pytest -q tests/security/test_remote_authority.py
```

Each test uses two rooms and all three roles, snapshots `world_revision`, mutation/outbox/command/result counts and bytes, projection bytes, and relevant audit rows before the attack, and asserts the invariant after it. Replay tests first prove and snapshot a legitimate completed consumption, then attack that consumed value; a separate barrier-synchronized race asserts exactly one original winner and denial of every loser. Token-expiry tests use an injected monotonic/application clock, not wall-clock sleeps. Crash tests inject failure immediately before and after approval nonce consumption/commit, pending-command recovery, execution-transaction lock, kernel calculation, mutation-ledger insertion, world/result/event/audit writes, execution commit, event publish, and delivery acknowledgement. At every boundary they assert the exact world revision plus command, result, mutation-ledger, outbox/event, and acknowledgement state described in steps 3–7. Test secrets and canaries are synthetic and never accepted by a real provider.

The integration harness must exercise production-shaped HTTP, WebSocket, database uniqueness/transactions, session store, and coordinator/kernel separation. Unit tests of token decoding or an intermediate authorization helper alone do not prove the observable zero-mutation end effect.

## Limits, counter-evidence, and blockers

- **CONFIRMED:** RFC 8725 requires the listed JWT algorithm/issuer/audience validation, RFC 9700 documents audience/least-privilege/replay mitigations, and OWASP documents per-message WebSocket authorization and Origin controls [1]–[3]. These are primary standards or project guidance, not measurements of this future implementation.
- **LIKELY:** the opaque-session, one-time-ticket, closed-capability, immutable-approval, and atomic-commit design satisfies the named threats if the full negative suite passes. No implementation exists, so this remains a design claim.
- **Physical-speaker attribution is intentionally out of scope:** a shared table cannot securely prove which person spoke. Voice matching would add biometric/privacy risk without establishing authorization. The product exposes a logical actor selection within the room's allowed set and records that limitation.
- A stolen active table session can exercise table capabilities until detected/revoked; browser security and short session lifetime reduce but do not eliminate this risk. It still cannot cross room/role or bypass current approval.
- TLS termination, reverse proxy, clock source, session database, audit store, CSP, rate limiting, and secret manager are unspecified. Their concrete configuration and the named production-shaped tests are blockers before remote exposure.
- Internet loss intentionally stops new authoritative actions. Clients display an explicit disconnected state, cannot mutate locally, and reconcile only from the server's committed cursor after reauthentication.
- An operational admin is not a narrative superuser. Any future requirement to let admin approve or alter story state is an architecture/security change requiring a new role, threat model, and owner decision; it is not implemented by broadening `admin`.

## Sources

1. [RFC 8725, JSON Web Token Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725.html) — IETF primary standard.
2. [RFC 9700, Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html) — IETF primary standard.
3. [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html) — OWASP project guidance.

Canonical local primary source: `docs/tasks/377/mvp-product-spec.ru.md`, especially the surface/room, VPS, confirmation, bounded-command, FSM, invariants, reuse, and private-repository sections; exact R8 delivery criteria in `docs/tasks/377/plan.md`.
