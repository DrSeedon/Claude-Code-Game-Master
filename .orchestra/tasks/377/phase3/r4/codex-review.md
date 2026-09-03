The named test passed (`19 passed in 4.74s`), but its synthetic envelopes do not implement the declared schemas, room isolation, authorization boundary, or audio/secret contract, and checkpoint corruption can evade detection. The artifact itself states: "The event-log candidate is viable and passed every correctness case." That conclusion is not supported for the full predeclared protocol oracle until these gaps are tested.

Full review comments:

- [P1] Validate the harness against the declared protocol schemas — /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/command-event-schemas.json:36-45
  blocking: The harness commands omit required `request_digest`, while returned results omit required `schema_version`, `command_id`, and `request_digest`; therefore all 19 tests can pass even though none of the measured command/results satisfy the externally consumed contract. Add schema validation to the common oracle and make both candidates persist and return schema-conforming envelopes.

- [P1] Scope command deduplication by room — /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/durability_probe.py:487-490
  blocking: Both stores query and key results solely by `command_id`, although the contract and ADR define uniqueness within `(room_id, command_id)`. In a multi-room database, two rooms using the same command ID will either receive the other room's stored result or raise an idempotency conflict, so the harness's fixed single room cannot establish the declared isolation guarantee.

- [P1] Enforce actor capabilities in the command contract — /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/command-event-schemas.json:28-30
  blocking: `Actor` and command `type` are independently valid, so the schema accepts a player or provider issuing internal authority commands such as `commit_world`, `prepare_projection`, or `enqueue_audio`; the harness also ignores `actor` entirely. This contradicts the state machine's mandatory authentication/capability step and leaves the authoritative-mutation security claim unasserted.

- [P1] Exercise the declared audio job and secret boundary — /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/command-event-schemas.json:300-310
  blocking: The tested audio record contains only `line_id` and `turn_id`, while the declared `AudioJob` requires `context_id`, `text_event_id`, `status`, and schema version; no audio text or image prompt is ever constructed. Consequently the passing canary case only proves projection filtering and cannot support the contract claim that secrets cannot enter audio text or image prompts, nor that contract-shaped audio enqueue is deduplicated.

- [P2] Bind checkpoint position into its integrity check — /home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/durability_probe.py:463-467
  blocking: The checkpoint checksum covers only `state_json`, not `event_seq`. If `event_seq` is corrupted upward while the state and canonical event rows remain unchanged, recovery accepts the checkpoint, skips required suffix events, and silently returns stale state despite the claimed fail-loud canonical-corruption behavior. Include the checkpoint position in the checksum or otherwise verify that checkpoint state corresponds to that exact event prefix.

> ⚠ Codex usage unaccounted: ValueError: Codex completed turn reported zero tokens

## Round 1 disposition

- Outcome: reviewer output was substantive and therefore consumed round 1, but no completed verdict was returned because the response omitted `## Verdict`.
- Evidence check: the quoted line beginning “The event-log candidate is viable” exists verbatim in `coordinator-adr.md`.
- P1 schema mismatch — **ACK/FIXED:** every admitted command, result, durable event, player projection, and audio job is now validated against `command-event-schemas.json`; stored results carry schema/command/request/room identity.
- P1 room scope — **ACK/FIXED:** both `command_results` tables now use `(room_id, command_id)` primary keys; a same-ID second-room trace receives its own stored `wrong_aggregate`, never the first room result.
- P1 capabilities — **ACK/FIXED:** JSON Schema constrains internal commands to coordinator/server and provider events to provider/server; the harness forges player `commit_world` and verifies schema/runtime rejection with zero mutation.
- P1 audio/secret boundary — **ACK/FIXED:** audio jobs now contain and validate schema version, line/context/turn/text-event IDs, disclosed text, and status; the player projection includes a disclosed image prompt; canary absence is asserted for both, while unknown projection shape publishes/enqueues neither.
- P2 checkpoint position — **ACK/FIXED:** checkpoint checksum binds `event_seq|state_json`; a dedicated fault corrupts only the position and recovery fails loud. The transactional analogue corrupts an outbox payload and also fails loud.
- Updated evidence: `uv run --frozen pytest -q docs/tasks/377/phase3/r4/test_durability_probe.py` → `19 passed in 8.78s`; regenerated `probe-results.json` records 19/19 cases per candidate, 38 rows total.

## Round (2026-08-16T13:10:24Z)

## Round 2

Re-review status: all five prior blocking findings are **FIXED**. Named test:

`uv run --frozen pytest -q docs/tasks/377/phase3/r4/test_durability_probe.py` → `19 passed in 5.31s`

`probe-results.json` contains 38 passing rows: 19 per candidate.

## Findings

- **FIXED — Protocol schemas:** admitted commands and persisted/returned envelopes are schema-validated with command, digest, room, and schema identity.
- **FIXED — Room-scoped deduplication:** both stores use `(room_id, command_id)` and the cross-room scenario proves no stored-result leak.
- **FIXED — Actor capabilities:** schema admission and store processing reject forged player `commit_world` with zero mutation.
- **FIXED — Audio/secret boundary:** schema-valid audio jobs and image prompts are exercised; the canary is excluded, and projection failure creates neither output.
- **FIXED — Checkpoint integrity:** `event_seq` and state are jointly checksummed; corrupted checkpoint position and outbox payload are detected.
- **Suggestion:** [coordinator-adr.md:184](/home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-durable-coordinator/docs/tasks/377/phase3/r4/coordinator-adr.md:184) says the event candidate “passed all 16 cases,” while the current result is 19/19. Change this to 19 cases; the 16 figure applies only to the combined crash traces.

The schema, harness, state machine, fault matrix, and persistence selection are otherwise consistent. No new blocking bug was found.

## Verdict

**APPROVED**

Artifact evidence: “Correct transaction and ID boundaries dominate the label.”
