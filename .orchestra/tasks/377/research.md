# #377 — AI tabletop MVP: architecture and reuse audit

**Phase:** 1 — research only
**Checked:** 2026-08-16 (Europe/Berlin)
**Repositories:** current DnD project (this worktree) and read-only `/home/kesha/orchestra`
**Excluded:** new repository creation, production changes, paid Deepgram/ElevenLabs calls, pricing, monetization, product naming, and a numeric latency SLA.

## Question

### Context

The product is a physical-room RPG table for 4–6 players with no human DM. A shared microphone feeds Deepgram; the AI drafts one party micro-action for review/redraft; only an approved action may change the world. The AI then runs enemies, exposes their dice, narrates, and sends narrator/enemy lines to ElevenLabs. The shared screen must include a square-grid map and digital tokens. Physical miniatures, camera, and CV are explicitly post-MVP. Players have no private secrets; world secrets remain server/AI-only until disclosure. These decisions are the source of truth [L2].

### Change under test

Build the MVP in a new private repository while reusing only mechanisms that are actually proven in the current DnD repository, its dashboard, and Orchestra.

### Baselines

1. Fork/copy the present DnD dashboard and game core.
2. Extract narrow tested primitives into a clean application.
3. Use Orchestra's lifecycle/event/recovery machinery as the application core and adapt the DnD domain.
4. Reimplement the required behavior from contracts, using existing repositories only as prior art.

### Outcome that decides the later choice

A viable option must complete and recover one approved party micro-action with these observable invariants:

1. one microphone stream produces reviewable speaker-attributed text;
2. no world mutation occurs before approval;
3. a repeated approve/send command is idempotent;
4. AI state mutation, enemy dice, narration, board update, and replay have one durable turn identity;
5. refresh/reconnect reconstructs the same committed state without duplication or omission;
6. the player surface never receives world-secret fields;
7. narrator/enemy audio can be interrupted without rolling back committed game state;
8. the room remains operable by an admin after browser, server, or provider interruption.

The owner intentionally supplied no numeric latency SLA. This research therefore identifies the serial interaction chain and latency-critical boundaries, but does not invent a threshold.

## Hypotheses considered and falsifiers

| hypothesis | why it could be true | what would prove it wrong | observed result |
|---|---|---|---|
| **H1. Forking the current DnD dashboard is the smallest route.** | It already runs an AI DM, has WorldGraph, tested combat, provider streaming, campaign views, replay, and a web dashboard. | Required voice/review/grid/recovery behavior is absent, or hidden coupling makes the fork carry more code and licensing surface than it saves. | **PARTLY REFUTED.** Strong domain primitives exist, but the required approval FSM, STT/TTS, grid/tokens, inbound idempotency, and durable interrupted-turn recovery do not. The current map is a location topology graph, not a tactical board. |
| **H2. A clean application around extracted game primitives is smaller.** | WorldRepository, projections, event schemas, provider protocols, and pure combat rules can be narrower than their current CLI/dashboard hosts. | The primitives cannot be separated without importing repository layout, global campaign state, shell rules, or module loaders. | **LIKELY, not yet selected.** Several seams are narrow and tested, but WorldGraph/dice/session/scene code contains material coupling; extraction must be selective, not a package-level copy. |
| **H3. Orchestra is the right runtime base.** | It has transport-independent sessions, persistent SQLite logs, provider capability declarations, hibernation, reconnect, restart recovery, and deterministic routing. | The domain needs only a small turn coordinator, while literal Orchestra reuse imports agent/worktree/systemd/SQLite complexity or incompatible licensing. | **PARTLY REFUTED.** Its invariants are valuable prior art; its full runtime is much broader than a room game and is AGPL-3.0 under the repository's license. |
| **H4. Browser-direct speech provider streams minimize the critical path.** | Deepgram and ElevenLabs both support short-lived client credentials, avoiding a server audio relay. | Shared-room audio needs server-side arbitration/recording, token refresh is unreliable, or real room measurements show no material advantage. | **UNCERTAIN.** Official protocols allow it, but no room microphone/network experiment was authorized or available. |

## Load-bearing findings

| finding | confidence and evidence tier |
|---|---|
| The current dashboard is **vanilla JS + FastAPI**, not the earlier React design described in historical planning documents. | **CONFIRMED — tier 1/2.** Current `frontend/index.html`, `frontend/js/app.js`, `backend/server.py`; the live loopback service served the current login HTML. |
| The DnD project has reusable game-domain behavior, not an MVP application: it lacks browser audio capture, Deepgram, an approval/redraft FSM, ElevenLabs playback routing, a square grid, and digital tokens. | **CONFIRMED — tier 2.** Full code search plus matrices A/B. |
| WorldGraph writes are atomic per `world.json`, but a whole AI turn is not atomic across WorldGraph, the event log, runtime-session metadata, campaign overview, save/module files, and narration. | **CONFIRMED — tier 2.** `WorldRepository.transaction()` is single-file; `GameSession._run_turn()`, `SessionManager`, and `SceneManager` perform separate commits. |
| Current reconnect recovers durable final events but not a durable in-progress turn. A process restart loses the in-memory `GameSession` task and broker; it can resume provider conversation state, not automatically finish the interrupted action. | **CONFIRMED — tier 2.** `backend/game_session.py`, `.runtime-session.json`, and `backend/live_broker.py`. |
| Current replay/live handoff can duplicate a persisted event: subscription occurs before history read and the client has no live-event ID dedupe. | **CONFIRMED — tier 1.** Deterministic probe produced `REPLAY_ID 1`, `LIVE_ID 1`, `PAYLOADS_EQUAL True`; code at `backend/server.py:802-834`. |
| Current inbound messages have no `turn_id`, idempotency key, or acknowledgement. A disconnect after send leaves the players unable to distinguish “lost” from “accepted”; retry can create another turn. | **CONFIRMED — tier 2.** `frontend/js/app.js:1386-1394`, `backend/server.py:821-829`, `GameSession.send()`. |
| Existing secret projection is useful but convention-based: denylisted field names and visibility flags are removed; a new secret field with an unrecognized name is not fail-closed by schema. | **CONFIRMED — tier 2.** `backend/campaign_views.py:86-156`; projection tests cover known names, not schema allowlisting. |
| Deepgram supplies word-level speaker labels and segment/finality signals, but its official docs do not promise stable real-person identity or accuracy for 4–6 people around one shared microphone. Party-turn assembly remains application logic. | **CONFIRMED limitation — tier 2.** Official Deepgram streaming, diarization, and utterance-end docs [E1–E5]. |
| ElevenLabs can stream partial text to audio and stop future generation for a multi-context utterance by closing its context. Already delivered browser audio is outside that provider guarantee, so audible interruption also requires client-side stop/discard keyed by line/context. `voice_id` is part of the endpoint path, so multiple narrator/enemy voices require separate voice-specific connections or another explicit multi-voice API; contexts alone do not select different voices. | **CONFIRMED + inference — tier 2.** Endpoint and multi-context docs [E7][E10]; the client-playback and connection-per-voice consequences are inferences from the documented provider boundary and endpoint shape. |
| A clean Git history does not clean the IP boundary. The DnD repository currently declares CC BY-NC-SA 4.0 and contains upstream-origin files; Orchestra declares AGPL-3.0. Git authorship is not proof of ownership assignment or relicensing authority. | **CONFIRMED repository facts / legal conclusion UNCERTAIN — tier 2.** Licenses and git history [L12]. |

## Minimum architecture invariants (not an option selection)

Every viable option reduces to six responsibility boundaries:

1. **Room input/output:** browser microphone capture, live transcript/review UI, shared grid/token board, audio playback.
2. **Authoritative turn coordinator:** a durable state machine (`listening → drafting → awaiting_approval → executing → presenting → committed/error`) keyed by immutable `turn_id` and idempotent commands.
3. **Game kernel:** explicit commands against an authoritative world store; dice and state mutations return structured domain events rather than terminal text.
4. **Provider adapters:** Deepgram STT, model runtime, and ElevenLabs TTS behind protocol-specific adapters; provider events never directly authorize world mutation.
5. **Durable state and replayable projection:** command deduplication, causal turn identity, crash-safe committed state, and player-safe/admin projections. An append-only event log plus checkpoints and a transactional current-state store plus outbox are both compatible; Phase 1 does not choose between them.
6. **Recovery surface:** inspect the current state, interrupt external work/audio, retry only an uncommitted stage, and reproject the room screen from durable state.

This is a set of observable guarantees, not a recommendation about local versus VPS placement, browser-direct versus server-proxied audio, persistence architecture, or repository history.

## A. REUSE MATRIX

`MVP fit` concerns behavioral fit, not line count. `Extract` means move a small contract/algorithm with its tests after license clearance; it does not mean copy the containing package.

| capability | source repo | exact file:line/function | current behavior proven by | dependencies | hidden coupling | MVP fit | reuse mode (copy/extract/rewrite/avoid) | reason |
|---|---|---|---|---|---|---|---|---|
| WorldGraph | DnD | `lib/world_repository.py:19-127 WorldRepository`; `lib/world_graph.py:149 WorldGraph`, `:175 transaction`, `:572 apply_damage` | `tests/test_world_repository.py:22-130`; `tests/test_world_graph.py:81-544`; full suite 544/544 | POSIX `fcntl`, JSON file, campaign directory, `json_ops`, module data | `WorldGraph` is a 2,885-line service/CLI hybrid; active campaign discovery, stdout error reporting, broad schema, random tick engine | **High** for world entities and atomic single-world writes; insufficient for turn/event atomicity | **extract** repository transaction + typed subset; do not copy monolith | The lock/revision/atomic-replace pattern is proven; the broad API and CLI context are not a clean application boundary. |
| dice/combat | DnD | `lib/dice.py:55 DiceRoller`, `:344 _combat_profile`, `:579 _persist_auto_damage`, `:651 main` | `tests/test_dice_combat.py:238-421` proves enemy/player/spell damage persistence; `:456-473` basic rolls | WorldGraph schema, `ModuleRuntime`, CLI parsing, ANSI output, global RNG | Resolution and persistence are combined; events are unstructured terminal output; D&D-specific field aliases | **High** mechanics, **low** event contract | **extract** pure resolver; **rewrite** persistence/event wrapper | Enemy dice must be openly renderable as structured events and commit once with damage. |
| campaign/session state | DnD | `backend/game_session.py:44 get_or_create_session`, `:104 GameSession`, `:314 send`, `:343 _run_turn`; `lib/session_manager.py:23 SessionManager`, `:162 create_save`, `:199 restore_save` | `tests/test_game_session.py:32-442`; `tests/test_session_manager.py:233-329` | provider registry, JSONL log, broker, overview/world/module files | in-memory session registry; save/restore spans multiple files without one commit; “session” means both provider lifecycle and campaign snapshot | **Partial** | **rewrite** one durable turn/session aggregate, borrowing tested behaviors | The required approval state and crash recovery are absent; copying both meanings of session would preserve ambiguity. |
| campaign creation / bootstrap | DnD | `lib/campaign_manager.py:42 CampaignManager`, `:134 create`, `:332 init_campaign_files`, `:360 _init_empty_files`; `backend/campaign_api.py:199 create_campaign` | `tests/test_campaign_api.py:87-168`; `tests/test_campaign_mode.py:52-97`; `tests/test_wizard.py:96-216` prove normalized/atomic creation, path rejection, defaults, and duplicate handling | filesystem layout, active-campaign file, `campaign_context`, `overview_schema`, WorldGraph, rules/session-log files | creates the legacy campaign bundle and solo `player:active`; global active campaign remains a fallback; no three-candidate/selection transaction | **Medium** bootstrap safety, **low** product setup fit | **extract** name/path and atomic-claim tests; **rewrite** the setup aggregate/schema | Proven path/race handling is worth retaining, but the MVP setup must persist map candidates, selection, party roster, grid, and voice configuration as one recoverable flow. |
| scene manager | DnD | `lib/scene_manager.py:26 SceneManager`, `:84 transition` | `tests/test_scene_manager.py:68 complete beat`, `:118 prevalidation`, `:134 travel delegation` | WorldGraph, overview JSON, `time_manager`, optional world-travel import | transition validates first but then performs separate graph/time/overview operations; imports module through path/name | **Medium** domain command semantics | **extract** validation/command shape; **rewrite** commit boundary | Useful scene semantics, but approval-to-commit needs a single durable turn outcome. |
| entity enhancement / RAG | DnD | `lib/entity_enhancer.py:65 EntityEnhancer`, `:91 _ensure_rag`, `:163 search_raw`, `:335 apply_enhancements`, `:479 get_scene_context`; `tools/dm-session.sh:70,133` | Source establishes the call path; `rg` found no direct `tests/` reference to `EntityEnhancer`/`get_scene_context`, so runtime behavior is **not directly test-proven** | active `CampaignManager`, WorldGraph, optional ChromaDB + sentence-transformers, campaign vector directory, CLI/stdout | active-campaign lookup; scene read can auto-write retrieved passages into world state; query templates and thresholds are embedded; retrieved source may contain unrevealed world material | **Low for MVP critical path; possible later AI-only lore retrieval** | **avoid** in MVP; if required later, **rewrite** behind an explicit read-only AI-secret retrieval boundary | Heavy optional dependencies and untested read/write coupling do not help the approval/grid/voice tracer; raw passages must never reach player/TTS projections. |
| event log/replay | DnD | `backend/event_log.py:26 read_events`, `:46 read_current_session_events`, `:101 append_event` | `tests/test_event_log.py:22-164` including concurrent monotonic IDs and corrupt tails; `tests/test_ws_game_protocol.py:129-181` | JSONL, POSIX file lock/fsync, campaign directory | malformed rows are skipped; IDs are campaign-file local; no turn correlation, idempotency, event version, or checkpoint transaction with world | **High foundation** | **extract then extend** | Append/fsync/replay is proven, but the MVP needs command IDs, turn stages, domain events, and recovery checkpoints. |
| broker / WebSocket | DnD | `backend/live_broker.py:14 LiveBroker`; `backend/server.py:740 game_websocket` | `tests/test_live_broker.py:12-81`; `tests/test_ws_game_protocol.py:77-310`; focused 57/57 | one asyncio process, FastAPI WS, JSONL replay | raw inbound strings; no ack/idempotency; 256 queue drops any oldest event, not only partials; replay/live overlap; single-worker only | **Low-to-medium** | **rewrite** protocol, retain only campaign channel idea | A typed command/event protocol and durable cursor are mandatory; current broker assumptions can lose or duplicate UI events. |
| provider layer | DnD | `backend/runtime/protocol.py:12 AgentProvider`; `backend/runtime/registry.py:80 RuntimeRegistry`, `:197 create_default_registry`; `backend/providers/claude_sdk.py:221 process_message`; `backend/providers/codex_cli.py:536 process_message` | `tests/test_runtime_registry.py:56-188`; `tests/test_claude_dm.py:94-248`; `tests/test_codex_cli_provider.py:262-688` | Claude Agent SDK / Codex app-server CLI, repo cwd, MCP, model catalog | providers expose agent/tool behavior, not a constrained game-command interface; Claude uses `bypassPermissions`; model IDs/runtimes drift | **High adapter shape**, **medium implementation fit** | **extract** event/protocol normalization; **rewrite** factories and permissions | The structural provider seam and event normalization are proven; the new app needs least-privilege tools and a smaller model contract. |
| system prompt assembly | DnD | `backend/claude_dm.py:9 load_system_prompt`, `:137 _campaign_context`, `:179 _cinematic_context` | `tests/test_claude_dm.py:7-90`; game-system-prompt research/report [L7] | shell compiler, `.claude/additional`, narrator files, campaign markdown, repo cwd | repository layout and Bash compilation; fallback prompt; tool rules intermixed with product/runtime context | **High content value**, **low package fit** | **rewrite assembler; extract reviewed rules** | Preserve campaign/rules/narrator contracts, not filesystem and shell coupling. |
| auth | DnD | `backend/auth.py:19-82`; `backend/server.py:89 AuthMiddleware`; `backend/config.py:103-114` | `tests/test_ws_game_protocol.py:84 auth gates`; `tests/test_config_security.py:19-33` | one environment password, static salt, cookie | shared 30-day cookie, no identities/roles/revocation/CSRF; unauthorized API GET returns login HTML with HTTP 200 in the live measurement | **Only a closed-room prototype gate** | **avoid/rewrite** | Admin and table surfaces need explicit roles/sessions and API-consistent failures; provider-token endpoints require protection. |
| frontend streaming / reconnect | DnD | `frontend/js/app.js:412-488` stream buffer; `:1196-1275` WS lifecycle; `:1278-1383` event/history; `:1386 sendGame` | server-side replay tests; current frontend has **no JS behavioral test** | global mutable JS state, DOMPurify/marked/Cytoscape CDNs, raw WS | cursor only in memory; cursor advances before rendering; content-key local echo hides legitimate repeated text; no command ack/id | **Medium algorithms, low UI fit** | **rewrite UI; port measured buffering algorithm only** | The common screen must add audio/FSM/grid and deterministic reconnect; copying 2,847-line global script carries obsolete UI state. |
| map projection / world-travel | DnD | `backend/map_view.py:86 _location_visible`, `:265 get_map_snapshot`; `modules/world-travel/lib/world_travel_store.py`; `frontend/js/app.js:2084 renderMap` | `tests/test_map_view.py:51-242`; world-travel store/projection tests; current renderer code | world-travel module, WorldGraph location nodes, Cytoscape | topology/coordinates and hidden-location rules; no square cells, token occupancy, movement range, initiative, drag authority | **High lore/navigation projection; no tactical board** | **extract** visibility/navigation projection; **rewrite** grid/token model and renderer | It solves “which locations may players see,” not the mandatory shared tactical surface. |
| player-safe world projection | DnD | `backend/campaign_views.py:86 _private_field`, `:95 _player_safe_copy`, `:128 _explicitly_hidden`, `:312 CampaignViewProjector`, `:672 get_campaign_views` | `tests/test_campaign_views.py:242-383` covers canonical views, hidden NPC/quest/wiki/consequence data, nested GM fields, and economy | WorldGraph schema and naming conventions | denylist/visibility conventions are not a schema allowlist; a future unknown secret key can pass through | **High starting behavior; insufficient safety invariant** | **extract projection tests; rewrite as allowlisted schema** | The AI/table trust boundary is mandatory and deserves a fail-closed contract independent of frontend rendering. |
| cinematic MCP | DnD | `backend/cinematic_mcp.py:71 render_cinematic_scene`, `:130 build_cinematic_mcp`; `backend/claude_dm.py:179 _cinematic_context` | `tests/test_claude_dm.py:64-219`; game-dashboard report [L6] | Claude MCP, Codex/image provider, generated media filesystem | provider-specific subprocess/tool chain; prompt-only instruction to use player-visible facts; no programmatic secret sanitizer | **Optional, not critical-path MVP** | **avoid initially; extract later if retained** | Grid maps and tokens are mandatory; cinematic frames are not a substitute and can leak secrets or add failure latency. |
| wizard | DnD | `backend/server.py:582 wizard_websocket`; `backend/wizard_mcp.py:19 WizardEvents`, `:68 run_wizard_tool`; wizard prompt/report [L8] | `tests/test_wizard.py:12-351`; wizard-streaming report [L8] | provider, Bash campaign creator, UI event buffer, repo templates | LLM-driven eight-phase creation; non-transactional shell work; not the required “three maps → select → adventure” flow | **Low behavioral fit; reusable UI-event idea** | **rewrite** fixed setup FSM; optionally extract event envelope | Map selection must be deterministic, recoverable, and visible on the table, not hidden in a long agent wizard turn. |
| Orchestra transport-independent lifecycle | Orchestra | `/home/kesha/orchestra/app/backend_protocol.py:10 BackendLike`; `app/runtime_registry.py:20 RuntimeCapabilities`, `:80 register_runtime`; `app/session.py:956 send`, `:1501 _persistent_event_loop`, `:1589 _handle_event` | `tests/test_runtime_registry.py:22-137`; `tests/test_session.py`; current production runtime | SQLite, agent backends, prompts, MCP, worktrees, manager | designed for long-running coding agents, steering, subagents, context, cost, worktrees; session file is 3,142 lines | **High prior-art value, low wholesale fit** | **rewrite a small turn coordinator from invariants; do not copy runtime wholesale** | Capability-declared adapters and transport-independent events are valuable; agent-team machinery is not game behavior. |
| Orchestra persistent event log / replay | Orchestra | `/home/kesha/orchestra/app/db.py:99 logs schema`, `:1480 add_log`, `:1606 get_logs`; `app/routes/sessions.py:401 stream_session_logs`; `app/live_broker.py:22 subscribe`, `:46 publish` | `tests/test_logs_sync.py:47-320`; `tests/test_live_broker.py`; immutable-row invariant in source | SQLite WAL, SSE polling, single-process partial broker | dashboard/session schema, log types, global DB; partial accumulator and secret masking tied to coding-agent output | **High pattern fit** | **reimplement schema/projection; literal copy only with license clearance** | Durable rows + ephemeral partials + cursor are the right separation; the new event schema must be game-turn-specific. |
| Orchestra recovery / routing | Orchestra | `/home/kesha/orchestra/app/session_hibernate.py:70 hibernate_now`, `:118 heartbeat_loop`; `app/manager.py:2065 auto_resume_all`; `app/runtime_router.py:403 RuntimeRouter`, `:641 evaluate_routing` | `tests/test_manager.py:2039+`; `tests/test_seamless_restart.py`; `tests/test_fd_adopt.py`; `tests/test_runtime_router.py`, `test_runtime_router_db.py` | systemd FD store/adoption, SQLite session state, CLI processes, quota observation and policy | recovery includes inherited file descriptors, CLI PIDs, restart notices, hibernation, multi-model quotas; far beyond one game process | **High recovery/routing lessons, low literal fit** | **rewrite minimal checkpoints and explicit provider policy** | Adopt “persist before work, reconnect listener, distinguish interrupted from idle”; avoid systemd/FD adoption and quota router unless later evidence requires them. |

## B. GAP MATRIX

| missing capability | exact MVP behavior | external API/hardware | latency-critical? | failure behavior | secret/data handling | deterministic test oracle | existing partial primitive |
|---|---|---|---|---|---|---|---|
| browser audio capture | Obtain explicit mic permission; publish capture state; stream one declared codec/sample rate; stop/restart without duplicating audio; keep typed-text admin fallback separate from player approval | browser `getUserMedia`, AudioWorklet/MediaRecorder; room mic | **Yes**, first link | remain in `listening/error`; do not draft or mutate; show actionable mic/device error | raw room speech leaves browser only through the selected STT boundary; never log provider credentials | fake `MediaStream` emits known PCM frames; assert sequence, stop cleanup, reconnect, and no frames after stop | none in current frontend |
| Deepgram streaming STT | Warm WS consumes audio; interim text is provisional; concatenate `is_final` segments; only a completed utterance becomes a draft input; support `Finalize`, `CloseStream`, and keepalive | Deepgram `/v1/listen` WS | **Yes** | freeze last provisional transcript as unapproved/error; reconnect with a fresh short token; never auto-submit ambiguous audio | API key server-only; browser receives temporary token; raw audio/transcript are third-party data | fake WS trace with interim rewrite, multiple final segments, `speech_final`, `UtteranceEnd`, reconnect, and late events | provider streaming/event normalization patterns, not audio |
| multi-speaker / turn segmentation | Preserve word timestamps and speaker label; build one review card showing attributed utterances; allow correction/redraft; never treat a pause or diarizer label as approval | Deepgram diarization; shared mic; optional future multichannel hardware | **Yes** | mark speaker/segment uncertain and require review; overlapping/unstable labels cannot advance | speaker labels are player-visible; no private-player-secret partition needed | recorded synthetic event fixture with overlaps, label changes, long pauses, and multiple `is_final` chunks; expected canonical utterance list | none; product review step is only prose [L2] |
| player-declared physical dice | Capture a physical player roll only through an explicit reviewed declaration/control; store `{turn_id, actor, declared_total, optional_notation, version}` with the approved party action; permit correction before approval; honesty is intentionally not verified | physical dice; room mic or review UI | **Yes** when a roll is part of the action | an ambiguous number or unconfirmed declaration remains ordinary transcript and cannot affect resolution; stale correction/duplicate approve is rejected or returns the same result | declared player rolls are public; retain no unnecessary raw audio | fixtures distinguish “I have 17 arrows” from an explicit “roll total 17”; correction replaces the draft version; duplicate approval records one declared roll and one mutation | `DiceRoller` resolves electronic rolls, but there is no structured spoken physical-roll input [L2] |
| review / approve / redraft state machine | Durable `turn_id`; draft is immutable/versioned; approve command names draft version and is idempotent; redraft creates a new version; world mutation allowed only in `executing` after accepted version | no hardware; model provider for draft/redraft | **Yes** | timeout/disconnect leaves `awaiting_approval`; duplicate approve returns the same committed result; rejected/stale version is explicit | draft contains only player speech/player-visible context; world secrets stay server-side | table-driven state-transition test + crash/reload at every transition + duplicate command oracle | `GameSession.running` boolean and Orchestra status persistence are insufficient partials |
| ElevenLabs streaming TTS | Send approved narration/enemy line chunks; deliver playable chunks with line/voice/turn/context identity; interruption closes provider generation **and** immediately stops/discards already buffered client playback for that identity; text remains visible | ElevenLabs TTS WS; browser audio graph/room speakers | **Yes**, perception | keep committed text/board visible; on cancel close context, stop playback, ignore late chunks; retry audio only, never replay game mutation | long-lived key server-only; browser may use single-use token; send only disclosed text, never hidden prompt/world fields | fake WS + fake audio queue: cancel closes context, stops current buffer, discards queued/late chunks for `line_id/context_id`; retry does not call game kernel | optional ElevenLabs dependency only; no current integration |
| narrator / enemy voice routing | Server emits `speech_line{turn_id,line_id,speaker_role,entity_id,voice_id,text}`; narrator and each configured enemy resolve deterministically; player speech is not synthesized | ElevenLabs voice IDs, one/more voice-specific WS connections | **Yes** | missing voice falls back to an explicitly configured narrator voice or text-only; never guess a credential/voice | voice IDs are configuration; disclosed line text only | fixture voice registry; same event always maps to same voice; unknown entity takes declared fallback | narrator style controls prose, not audio routing |
| grid / token board | Square-cell map with stable coordinates; player/enemy tokens; server-authoritative positions/HP/visibility; snapshot + idempotent deltas; common display renders current committed turn | browser canvas/SVG/DOM; display/TV/projector | **Yes** for feedback | keep last committed snapshot; reject stale movement version; no optimistic position becomes canonical | hidden tokens/cells absent from player projection, not merely CSS-hidden | reducer/property tests: replay event list yields byte-equivalent board; stale/duplicate delta no-op | WorldGraph entities + map visibility + Cytoscape topology only |
| AI-visible dice events | AI enemy roll emits notation, individual dice, modifier, target/DC/AC, total, outcome, and linked mutation under one turn; common screen renders before/with consequence | model tool call; local RNG/CSPRNG policy to decide later | **Yes** for trust | invalid roll/result aborts dependent damage before commit; duplicate event cannot damage twice | rolls are public; hidden enemy stats not required in the event beyond disclosed modifiers/policy | seeded/fake roller asserts exact structured event and one damage commit; replay never rerolls | `DiceRoller` + combat persistence tests, but output is CLI text |
| three-map selection / generation | Produce exactly three typed, player-safe candidates and persist the selected candidate/version before adventure creation. **Unresolved product type:** tactical grid boards require grid metadata, traversability, and spawn cells; illustrative/adventure maps require an explicit deterministic conversion step before they can seed the mandatory board | map/image generator not yet selected; room display | setup-critical, not per-turn | cache candidates; provider failure leaves retryable setup without half-created campaign; duplicate selection is idempotent; a candidate lacking the metadata required by its declared type cannot be selected | candidates exclude world secrets and provider prompts; generated asset provenance recorded | fake generator returns three typed fixtures; reject missing grid/conversion metadata; crash/reload; selected ID + converter version yields the same initial board | wizard choices envelope; cinematic image tool; neither implements typed candidates or grid conversion |
| world-secret projection | AI context may read complete world; table/audio/event payloads use an allowlisted player schema; disclosure is a domain event that changes projection | none | **Yes** for safety | unknown field/type is omitted and logged for admin; projection failure blocks publication, not world commit | server-only canonical secret store; no secret in browser cache, TTS text, logs exposed to table, or image prompt | adversarial schema fixture adds unknown nested secret keys; assert absent from every player output | `CampaignViewProjector`, `_location_visible`; current denylist is not fail-closed |
| admin recovery | Separate authenticated admin surface shows turn stage, provider connections, last committed event, and pending draft; can interrupt external work/audio, retry an uncommitted stage, or restore projection | browser; local/VPS server | recovery-critical | every action is idempotent/audited; never “retry whole turn” after committed mutation; degraded text/board mode survives TTS failure | admin can see world secrets; table token cannot; provider keys never displayed | crash matrix at each FSM stage, refresh both surfaces, repeat recovery command | DnD interrupt/reset/compact endpoints; Orchestra interrupted/idle/restart logic |
| durable command/state/output contract | Every client command has `command_id`, expected aggregate version, actor/surface, and `turn_id`; every durable state transition and outbound record preserves schema version and causal identity without requiring events to be the canonical store | none | **Yes** | duplicate command returns the stored result; conflict is explicit; corrupt canonical state or output record halts/requires admin instead of silent skip | redact provider secrets before persistence; table queries player projection | common oracle: crash/reload yields identical committed state and player projection. Event-log variant: replay yields that snapshot. Transactional-state/outbox variant: dedupe/result row survives and each pending output is delivered once | DnD monotonic JSONL; Orchestra immutable SQLite rows; neither supplies the whole persistence-neutral contract |

## C. CURRENT FLOW

### One current text turn

| transition | current entrypoint / behavior | file:line | corresponding proof |
|---|---|---|---|
| 1. browser input → WS | `sendGame()` echoes locally and sends the raw trimmed string; there is no audio, command envelope, ID, or ack | `frontend/js/app.js:1386-1394` | server contract: `tests/test_ws_game_protocol.py:266 test_receive_text_is_always_a_player_turn_never_control_message`; no JS unit oracle |
| 2. WS auth/address/replay | WS authenticates one shared cookie, selects campaign/model/runtime, subscribes, reads JSONL after `after_id`, then sends status | `backend/server.py:740-812 game_websocket` | `tests/test_ws_game_protocol.py:77-181`, `:221-284` |
| 3. accepted input → background turn | `GameSession.send()` rejects only while running/locked, appends `user_message`, publishes running, then starts `_run_turn` | `backend/server.py:814-834`; `backend/game_session.py:314-331` | `tests/test_game_session.py:183-256` |
| 4. provider construction/resume | registry validates model/runtime/effort and builds provider; `.runtime-session.json` resumes only the exact runtime/model | `backend/game_session.py:104-164`; `backend/runtime/registry.py:80-194`; `backend/runtime/session_store.py:59-118` | `tests/test_runtime_registry.py:56-188`; `tests/test_game_session.py:115-169`; runtime-store tests |
| 5. provider call/event normalization | `_run_turn()` calls `provider.process_message`; Claude connects/queries SDK and normalizes partial/text/tool/result/usage; Codex has equivalent app-server adapter | `backend/game_session.py:343-417`; `backend/providers/claude_sdk.py:188-351`; `backend/providers/codex_cli.py:536-760` | `tests/test_claude_dm.py:94-248`; `tests/test_codex_cli_provider.py:262-688` |
| 6. tool → state mutation | Claude runs with repo cwd and `bypassPermissions`; compiled prompt directs Bash tools; wrappers call Python managers/WorldGraph; WorldRepository atomically replaces `world.json` | `backend/providers/claude_sdk.py:188-212`; `backend/claude_dm.py:42-134`; `tools/dm-world.sh:1-5`; `lib/world_repository.py:49-127` | WorldGraph/repository/dice/scene tests; there is **no end-to-end oracle** that makes tool mutation and turn event commit one transaction |
| 7. persist/provider replay | partials are broker-only; final text/error/activity/image is appended to `events.jsonl` and published; provider session ID is separately atomically stored | `backend/game_session.py:367-448`; `backend/event_log.py:101-126`; `backend/runtime/session_store.py:79-118` | `tests/test_game_session.py:146-299`; `tests/test_event_log.py:22-164` |
| 8. broker → WS | per-campaign in-memory queue forwards payload; oldest payload is dropped after 256 entries | `backend/live_broker.py:14-40`; `backend/server.py:831-834` | `tests/test_live_broker.py:12-81`; focused transport suite 57/57 |
| 9. frontend render/reconnect | client advances in-memory cursor, renders stream/final/activity, refreshes `/views` and `/map`, and reconnects exponentially | `frontend/js/app.js:1196-1383`, `:1494-1516`, `:2084-2130` | WS replay and Python view/map tests; no JS reconnect/render behavioral suite |

### Refresh, disconnect, and duplicate-message damage points

1. **Ambiguous send:** the browser sends a raw string and immediately renders it (`app.js:1386-1394`). If the socket drops before the player sees a durable event, the client cannot tell whether the server persisted it. Manual retry is not idempotent.
2. **Legitimate repeat hidden:** `localEcho` is keyed by `role:content`, not event ID (`app.js:1368-1380`). Two intentional identical utterances can be suppressed during replay in the same page lifetime.
3. **Cursor before render:** `afterId` advances before `handleEvent()` (`app.js:1236-1242`). A rendering exception can make a same-page reconnect skip the event whose UI side effect failed.
4. **Replay/live duplicate:** broker subscription precedes history read (`server.py:802-809`). An event appended/published in that interval is both history and queued live payload. The deterministic probe reproduced equality for event ID 1; `handleEvent()` has no ID dedupe.
5. **Queue drop can become permanent in the UI:** `LiveBroker.publish()` drops the oldest payload regardless of whether it is ephemeral or a persisted final (`live_broker.py:30-40`). If a later persisted ID is received, the client cursor moves beyond the missing row, so reconnect will not request it.
6. **Disconnect does not stop a turn:** this is intentional and tested (`server.py:748-751,836-839`). Final durable text is recoverable, but in-flight partials and current playback are not.
7. **Server restart is not turn recovery:** the session registry/task/broker are process memory. Provider session ID survives, but there is no persisted stage or automatic resubmission of the accepted `user_message`.
8. **Mutation/output split:** a tool can mutate `world.json` before its subsequent activity/final narration reaches JSONL. A process/provider crash can leave a changed world and an apparently unfinished turn.
9. **Multi-file scene/save split:** `SessionManager.restore_save()` and `SceneManager.transition()` touch overview/world/module/time state in separate operations; a mid-operation failure has no aggregate rollback.
10. **Auth response shape:** on the measured live service, unauthenticated `GET /api/status` returned the login page with HTTP 200, while the unauthenticated WS upgrade returned 403. A frontend expecting JSON can fail as a parse error instead of an auth state.

## D. OPTIONS — no recommendation in Phase 1

### Comparable critical-path units

With warm provider connections, the product imposes four serial decision gates independent of deployment topology:

1. **G1 — utterance boundary:** audio has produced a reviewable final transcript; STT interim rewrites are not a gate result.
2. **G2 — draft ready:** the first model draft/version is durably available to the room.
3. **G3 — decision accepted:** an approve/redraft command and its durable acknowledgement agree on the draft version.
4. **G4 — execution committed:** approved model execution has produced committed domain/dice events and a replayable player projection.

For a baseline approval with no redraft, a coordinator implemented with separate provider requests therefore expects **two model request/response cycles** (draft, execution) and **one room-to-authority command/acknowledgement cycle** (approval). Each redraft adds one model request/response cycle and one redraft command/acknowledgement cycle. Deepgram and ElevenLabs are long-lived streams, not per-turn request/response cycles: measure STT utterance-final delay, TTS time-to-first-audio, and TTS completion separately. TTS can overlap G4 once a disclosed line exists; its completion is not a prerequisite for committed game state. Token issuance is connection setup and is amortized, not counted per micro-action. No numeric time is claimed.

The reuse column below is an enumerated inventory, not a percentage or LOC proxy. A listed item remains a candidate until its behavioral contract and license boundary survive a vertical prototype.

| option | local in room / VPS | browser / server / provider boundary | display surfaces | repository boundary | enumerated tested capability inventory | expected request/response cycles and stream topology | single points of failure | migration cost | what would falsify |
|---|---|---|---|---|---|---|---|---|---|
| **O1. Evolve the DnD dashboard into a local room monolith** | Local FastAPI owns world/coordinator/store/provider clients; VPS absent or optional remote admin. Deepgram/model/ElevenLabs remain external. | Browser sends mic frames to local server; server proxies STT/TTS and owns all credentials/commands. | One common screen with a protected admin mode/route in the same app. | Carry DnD history or fork it, then add new code in place. | Candidate retention, if licensed: WorldRepository/WorldGraph subset, dice resolver, campaign path/bootstrap checks, JSONL durability tests, provider event normalization, prompt rules, player/map projections. Rewrite: inbound protocol, auth, frontend, approval coordinator, audio, grid/tokens. | **2 model + 1 approval command/ack**; STT and TTS each traverse browser↔local-server and local-server↔provider streams; STT final, TTS first audio, and completion remain unmeasured. | room server, room LAN/browser, each external provider; current single process | **M** | A tracer cannot isolate the enumerated retained contracts from global campaign/CLI/dashboard coupling, or the DnD license boundary is not cleared for the private repo. |
| **O2. Clean private repo: extracted game kernel + new voice/turn/UI shell** | Local authoritative server and durable state; optional VPS only issues remote access/tokens/backups. | Browser may connect directly to Deepgram/ElevenLabs using short tokens; server receives the canonical utterance/approval, calls the model, owns world and events. | Separate read-only table surface and admin surface, both projections of one durable state/event contract. | Clean history; bring only license-cleared narrow code/tests or reimplement contracts. | Candidate extraction: WorldRepository transaction contract, pure dice resolution, campaign name/path checks, projection/visibility oracles, provider event schema. Rewrite: session/scene commit boundary, coordinator, transport, audio, UI/grid, auth. | **2 model + 1 approval command/ack**; audio streams browser↔provider; canonical utterance, review, approval, and projection cross browser↔local authority; short-token issuance is amortized per connection. | room browser for audio, local server/store, provider streams; token issuer if placed on VPS | **M** | Browser-direct capture/diarization/playback is unreliable in the actual room, or the named kernel contracts still import repository shell/module/global-state dependencies. |
| **O3. Orchestra-derived durable session core + DnD domain adapter** | VPS or room service runs a SQLite lifecycle/event/recovery core; room browser is thin. Providers external. Local cache may retain only the last table projection. | Browser sends commands to the authority; server proxies or tokenizes speech providers and treats the model as one runtime adapter. | Separate table and admin surfaces, matching distinct consumer projections. | New repo with selected Orchestra/DnD packages or subtree history; literal code requires both license boundaries to be resolved. | Candidate Orchestra inventory: immutable log/cursor semantics, capability-declared runtime adapter, interrupted/idle distinction, persisted-before-work and routing tests. Candidate DnD inventory: typed world subset, dice resolver, player projection. Exclude Orchestra worktrees/subagents/FD adoption/quota machinery. | **2 model + 1 approval command/ack**; if authority is VPS, review/approval/projection are WAN cycles; speech is either an additional WAN relay through authority or browser-direct with token setup. | VPS/network becomes critical when authoritative; SQLite/service; providers; room loses command authority if WAN fails | **L** | A small coordinator passes the same crash/idempotency/replay oracles without Orchestra dependencies, either license boundary is not cleared, or room WAN tests make remote authority unacceptable. |
| **O4. Clean-history behavioral reimplementation** | All authoritative application behavior local; VPS optional backup/admin gateway. | Browser-direct or server-proxied speech remains an adapter choice; domain service accepts only typed transcript/draft/approve commands. | Separate table/admin projections by default; one physical browser may host both tabs. | New clean history; reimplement from written behavioral contracts, importing no source until rights are cleared. | No literal code assumed. Reusable evidence/oracles only: DnD combat/world/projection/reconnect tests and Orchestra lifecycle/recovery failure cases inform independently written contracts. | **2 model + 1 approval command/ack**; STT/TTS stream topology is intentionally undecided, so this option has no latency advantage until both paths are measured. | room server/store and providers; fewer inherited runtime components but all recovery correctness must be rebuilt | **L** | A license-cleared narrow extraction delivers the same vertical tracer and recovery oracles with lower coupling/migration cost; independent implementation repeats defects already excluded by existing tests. |

No option can remove the approval exchange without violating the product decision. No local/VPS winner is supported without measuring the actual room microphone, browser, LAN/WAN, model provider, and audio playback path.

## E. EXTERNAL API FACTS

Only official Deepgram and ElevenLabs primary documentation was used. Pages were opened and checked on **2026-08-16**. No credential was read or copied and no paid API was called.

### Deepgram

| fact | MVP consequence | source |
|---|---|---|
| Live STT is `wss://api.deepgram.com/v1/listen`; it accepts binary audio plus JSON `Finalize`, `CloseStream`, and `KeepAlive`, and returns `Results`, metadata, `UtteranceEnd`, and `SpeechStarted`. | A long-lived adapter can separate provisional transcript, final segment, utterance boundary, and connection lifecycle. | [E1] |
| Server auth uses `Authorization: Token <API_KEY>`; temporary JWT uses Bearer/Sec-WebSocket-Protocol. Default temporary-token TTL is 30 seconds, max 3,600 seconds; token only needs to be valid at WS handshake. | Long-lived API key stays server-side. Browser-direct connection uses a newly issued short token on every connect/reconnect. | [E1][E2][E3] |
| `interim_results=true` yields mutable `is_final:false` hypotheses. `is_final:true` finalizes a segment; complete utterance text may require concatenating multiple final segments until `speech_final:true`. | Never send interim text directly to the world/model as an approved command; the assembler needs segment IDs/timestamps and a buffer. | [E4] |
| `UtteranceEnd` detects a configured gap after the last finalized word, but official docs warn it can fire while a speaker continues and recommend additional client logic for voice agents needing precise boundaries. | A pause can propose an end, not approve a party turn. Semantic/review logic remains necessary. | [E5] |
| Streaming diarization returns a `speaker` value on each word. The official page does not define stable human identity or a 4–6-person accuracy guarantee. | Store labels as uncertain observation, show them for correction, and measure the actual room. Do not bind `speaker:2` permanently to a player without application calibration. | [E6] |
| Multichannel can process up to 20 channels, but it transcribes separate submitted audio channels. | A normal shared browser mic is one channel; multichannel helps only if the hardware/audio pipeline supplies genuinely separate channels. | [E12] |
| `KeepAlive` is a text frame recommended every 3–5 seconds when no audio is sent; 10 seconds without audio/keepalive closes with `NET-0001`. `Finalize` flushes buffered audio without necessarily closing; `CloseStream` flushes and terminates. | Connection manager and fake-clock tests must cover room silence, flush, reconnect, and late final events. | [E13][E14][E15] |

### ElevenLabs

| fact | MVP consequence | source |
|---|---|---|
| TTS input streaming is `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`. The client sends initialization/text/EOS; responses contain base64 audio, optional alignment, and `is_final`. | Text tokens/sentences can be forwarded while approved model narration is generated, reducing perceived wait without waiting for the whole paragraph. | [E7][E8] |
| API keys are documented secrets that must not be exposed in browser code. `POST /v1/single-use-token/{token_type}` supports `tts_websocket`; token expires after 15 minutes and is consumed on use. The TTS WS accepts `single_use_token`. | Browser-direct TTS is technically supported through a protected token endpoint; server proxy remains another option. Never put `xi-api-key` in shipped JS. | [E7][E9][E11] |
| `voice_id` is a path parameter and `model_id` a query parameter. | **Inference:** narrator/enemy voice routing across distinct voice IDs needs distinct voice-specific sockets/requests or another explicit multi-voice endpoint; a context ID alone is not a voice selector. | [E7] |
| Standard WS is intended for partial text input. It defaults to a 20-second inactivity timeout (max 180). `auto_mode` removes buffering but is recommended only for full sentences because partial sentences reduce quality. | Sentence-aware chunking/flush is part of the adapter; “send every model token” is not automatically correct. | [E7][E8] |
| Multi-context WS supports independent contexts, `flush`, `close_context`, and `close_socket`; official guidance handles interruption by closing the old context and creating a new one. One connection allows at most five concurrent contexts and is tied to one `voice_id`. The guide does not state that `close_context` stops audio already delivered to a client. | Barge-in requires two coordinated operations: close future provider generation for the context, then stop/discard browser playback and late chunks keyed by line/context. Neither operation rolls back committed game state. Five contexts are enough for sequential room generation but not evidence for five different voices. | [E10] |
| Concurrency is plan/model-specific. The current official table starts at 2 concurrent Multilingual-v2 or 4 Flash TTS generations; an open WS counts only while generating audio. | Player count is not TTS concurrency: the shared room normally plays one line at a time. Voice-line concurrency still needs an explicit queue and selected account-limit check, with no price decision here. | [E16] |
| Zero-retention mode via `enable_logging=false` is documented as enterprise-only for this endpoint. | Data-retention policy is an unresolved deployment decision; do not promise zero retention from the base API. | [E7] |

## F. IP / REPO BOUNDARY

This is a repository evidence audit, **not legal advice**. Where the files/history cannot establish a legal conclusion, it is marked unresolved.

### Facts established from the repositories

| boundary fact | concrete evidence | consequence that can be stated |
|---|---|---|
| Current DnD root declares CC BY-NC-SA 4.0 and copyright `2024-2026 Sean Stobo`; `pyproject.toml` declares the same SPDX-style identifier. | `LICENSE:1-22`, `pyproject.toml:9`, README license section | Literal copying must be treated as licensed source, not “our private code,” until an owner/legal review documents another right. |
| Initial public commit `87f6eaa` used MIT; commit `e2145d3` by Sstobo changed the root license to CC BY-NC-SA. | `git show 87f6eaa:LICENSE`; `git show e2145d3 -- LICENSE`; `git log --follow LICENSE` | The history contains code received under an earlier license and a later repository-wide declaration. The repository alone does not resolve which terms may be elected for every later revision. |
| `lib/dice.py` and `lib/session_manager.py` entered in the upstream initial commit by Sstobo; `lib/world_graph.py`, backend, current vanilla frontend, and world-travel entered in later Maxim-authored commits. | `git log --diff-filter=A -- <file>`: `87f6eaa`, `d239c9c`, `d9973ff`, `bfedd5a`, `486afa5`, `da8dfb9` | Provenance differs by file. “Authored in this fork” is useful evidence but is not proof that the committer owns all rights or can relicense dependencies/contributions. |
| DnD history has 218 Maxim, 14 Sstobo, and 9 DrSeedon commits in `git shortlog -sne --all`; `CONTRIBUTING.md` contains no CLA/assignment terms. | git shortlog; `CONTRIBUTING.md` full read | Ownership/assignment cannot be concluded from this repo. |
| Orchestra declares AGPL-3.0, names Seedon (ООО «Сидон») as copyright holder, and offers a separate commercial license contact; it has multiple commit authors and no CLA in `CONTRIBUTING.md`. The license notice summarizes an obligation to make modified program source available to users interacting with it remotely over a network. | `/home/kesha/orchestra/LICENSE:1-21`, git shortlog, `CONTRIBUTING.md` | Literal Orchestra code requires license review. Whether and how that condition applies to a specific combined/private room or VPS deployment cannot be concluded from repository metadata; git also does not prove contributor assignments. |
| DnD runtime campaign data and source material are ignored. Only `.gitkeep` and one campaign template are tracked; `.env.example` is tracked, not `.env`. | `.gitignore:26-43`; `git ls-files world-state/**`; tracked secret/data scan | Runtime world state is not a reusable code asset and must not enter the new repository/history. |

### Practical transfer modes

| mode | provenance/operational effect | legal/IP status from available evidence |
|---|---|---|
| full DnD history/fork | Best preserves blame, tests, and attribution; also carries all upstream-derived material and historical paths. | Does not remove CC/noncommercial/share-alike questions. Private visibility does not itself establish permission. |
| subtree/package extraction with history | Preserves provenance for a selected component and its tests; still imports its license and dependency graph. | Viable only after file-level license/right clearance. |
| copy into clean history | Smaller history, but loses useful attribution/blame unless deliberately recorded. | **Does not erase provenance or license obligations.** |
| contract/behavior reimplementation | New code can be scoped exactly to the MVP and avoid literal coupling. | Whether a specific implementation is sufficiently independent is a legal question; repository facts alone cannot certify “clean room.” |
| separate commercial/owner permission | Could permit code reuse under terms different from the public license. | No such grant exists in the inspected repositories; it must be documented outside git before relying on it. |

### Mandatory exclusions from a new repository

- `.env`, `.env.local`, API keys, cookies/password material, Orchestra internal tokens, provider profiles;
- `world-state/campaigns/*`, `active-campaign.txt`, `world.json`, `events.jsonl`, `.runtime-session.json`, campaign saves/backups;
- source PDFs/imported books and RAG/vector stores;
- generated media/audio and any prompt/event logs containing player speech or world secrets;
- live SQLite databases, WAL/SHM files, systemd/nginx/DNS configuration copied from production;
- git remotes/deploy secrets and local settings.

### Unresolved legal decisions

1. Who owns or can separately license the later Maxim/DrSeedon DnD contributions?
2. Did all Orchestra contributors assign rights to Seedon, or is AGPL the only documented grant for their contributions?
3. Does the intended private room/demo distribution trigger particular CC ShareAlike obligations? The repo cannot answer this.
4. Which assets, rules text, templates, and third-party game-system content have independent licenses?

These require owner/legal confirmation; Phase 1 cannot infer them from git.

## G. MEASUREMENTS

### Measurement protocol

All commands were run on 2026-08-16 in this worktree without paid APIs. Pass criteria were declared before the runs: collection/full/focused tests exit 0; transport probe reproduces or rejects the predicted overlap; `uv.lock` must end byte-identical to HEAD; no production mutation. `/tmp` held only small logs/probes.

Environment:

```text
date --iso-8601=seconds
2026-08-16T11:18:54+02:00

uname -srmo
Linux 6.8.0-136-generic x86_64 GNU/Linux

uv --version
uv 0.11.28 (x86_64-unknown-linux-gnu)

project interpreter used by tests
CPython 3.11.15
```

### Tests and lock reproducibility

```text
/usr/bin/time -f 'WALL_SEC=%e USER_SEC=%U SYS_SEC=%S MAX_RSS_KB=%M EXIT=%x' \
  uv run --no-sync pytest --collect-only -q

544 tests collected in 5.08s
WALL_SEC=8.10 USER_SEC=4.93 SYS_SEC=0.57 MAX_RSS_KB=89684 EXIT=0
```

```text
/usr/bin/time -f 'WALL_SEC=%e USER_SEC=%U SYS_SEC=%S MAX_RSS_KB=%M EXIT=%x' \
  uv run --no-sync pytest -q

544 passed in 28.23s
WALL_SEC=31.75 USER_SEC=8.79 SYS_SEC=3.40 MAX_RSS_KB=145904 EXIT=0
```

```text
/usr/bin/time -f 'WALL_SEC=%e USER_SEC=%U SYS_SEC=%S MAX_RSS_KB=%M EXIT=%x' \
  uv run --no-sync pytest -q tests/test_event_log.py tests/test_live_broker.py \
  tests/test_game_session.py tests/test_ws_game_protocol.py

57 passed in 3.71s
WALL_SEC=6.94 USER_SEC=2.83 SYS_SEC=0.65 MAX_RSS_KB=78580 EXIT=0
```

Counter-measurement: the first `uv run` and the full run tried to rewrite `uv.lock` because the global `exclude-newer` barrier was removed. Generated changes were restored and not accepted. A read-only locked check proves the current lock is stale relative to current resolution metadata:

```text
uv sync --locked --dry-run
Resolving despite existing lockfile due to removal of global exclude newer
Resolved 167 packages in 1.30s
Checked 97 packages in 5ms
Would make no changes
error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.
UV_LOCKED_DRY_RUN_RC=1
```

Final tracked lock hash after restoration:

```text
sha256sum uv.lock
9a2777069070e432d0322f62ce9fc0258670da20c709a1616ae8809af1c67d6a  uv.lock
```

Therefore the 544-pass result validates current code against the environment resolved on 2026-08-16, but the repository does **not** currently provide a locked reproducibility proof. This matches the known issue in `TODO.md` [L9].

### Code/component footprint (scope, not reuse proof)

```text
component  files  bytes
backend       26  234053
lib           33  452010
frontend       4  199369
modules       52  508500
tools         25   81194
tests         35  223818
```

Selected DnD runtime files total 8,089 lines (`server`, `game_session`, event/broker/registry, two providers, WorldGraph/repository, dice/session/scene). Selected Orchestra lifecycle/event/routing files total 12,495 lines. These numbers describe extraction surface only; they are explicitly **not** evidence of reusability.

Module manifests and footprint:

```text
firearms-combat  files=12 py=5  bytes=133688 text_lines=3639  dependencies=[]
mass-combat      files=9  py=4  bytes=104436 text_lines=2852  dependencies=[]
world-travel     files=30 py=19 bytes=259712 text_lines=7236  dependencies=[]
```

Direct declared Python dependencies:

```text
core=9
  claude-agent-sdk, fastapi, matplotlib, pdfplumber, pypdf2,
  python-docx, python-dotenv, requests, uvicorn
optional: voice=1, rag=2, full-meta=2, dev=4
uv.lock package records=167
```

### Static import graph

Counting rule: parse every `.py` under `backend/`, `lib/`, and `modules/` with `ast`; resolve unique internal module/basename imports; count unique file-to-file edges. Dynamic shell/module imports are excluded, so this is a lower bound.

```text
PY_FILES=87 PARSED=87 INTERNAL_UNIQUE_EDGES=175 PARSE_ERRORS=0

top fan-in:
13 lib.world_graph
13 modules/world-travel/lib/world_travel_store
12 lib.json_ops
12 lib.campaign_context
 9 lib.campaign_manager

top fan-out:
17 backend.server
 7 lib.world_graph
 6 lib.agent_extractor
 6 lib.rag.__init__
 6 modules/world-travel/lib/navigation_manager
 5 lib.dice
 5 lib.session_manager
 4 backend.game_session

component edges:
backend->backend 43
backend->lib      7
lib->lib         68
modules->lib     17
modules->modules 40
```

Interpretation: WorldGraph is a proven central primitive and a high-coupling extraction point; `backend.server` is the largest orchestrating fan-out. The AST graph understates shell wrappers, prompt-driven Bash tools, and dynamic world-travel loading.

### Frontend footprint and dependencies

```text
frontend/index.html     lines=162  bytes=9859   gzip_bytes=2844
frontend/js/app.js      lines=2847 bytes=128317 gzip_bytes=34572
frontend/css/style.css  lines=1075 bytes=60974  gzip_bytes=12901
frontend/favicon.svg               bytes=219
frontend total: files=4 bytes=199369
```

There is no build/bundle step. `index.html:9-11` loads marked, DOMPurify, and Cytoscape from jsDelivr; `app.js` is one global-state file. This confirms the current dashboard is vanilla, while also making whole-file reuse a coupling risk.

### Current transport behavior

Focused transport/session tests: **57 passed** as above.

Deterministic replay/live overlap probe:

```text
subscribe campaign queue
append_event(text, "same-final")
publish the stored event
read_current_session_events(after_id=0)

REPLAY_COUNT 1 LIVE_QUEUE_COUNT 1
REPLAY_ID 1 LIVE_ID 1 PAYLOADS_EQUAL True
```

Read-only observation of the already-running service (no login, no mutation):

```text
127.0.0.1:18083 LISTEN, uvicorn, cwd=/home/kesha/projects/dnd-game-master
GET /                         -> HTTP/1.1 200, login HTML, 1709 bytes
GET /api/status unauthenticated -> HTTP/1.1 200, same login HTML, 1709 bytes
WS upgrade /ws/game unauthenticated -> HTTP/1.1 403 Forbidden, empty body
```

This proves the deployed/current transport is loopback FastAPI/Uvicorn with cookie auth gating; it does not measure internet/proxy latency and no production configuration was read or changed.

## Adversarial second opinion

`docs/tasks/377/codex-review-research.md` records the two-round `codex-debate` review. Round 1 returned **0 blocking findings**, seven material suggestions, and one architecture-affecting map question. Round 2 verified that all eight were fixed and independently checked the replay/live evidence against `backend/server.py:802-809`; it returned **0 blocking findings** and two consistency/scope suggestions. Those final suggestions are applied here: Matrix B now has persistence-neutral recovery plus explicit event-log and transactional-state/outbox oracles, and the Phase 1 conclusion no longer prescribes an implementation tracer. The review's dissent is preserved in full rather than collapsed into this summary.

## Counter-evidence and limitations

1. **Against a clean rewrite:** 544 green tests, atomic WorldRepository writes, provider adapters, projections, and campaign isolation mean a fork may produce a demo sooner if the license and coupling are accepted.
2. **Against dismissing Orchestra:** it already solved immutable logs, partial/final separation, runtime capability declarations, hibernation, interrupted-vs-idle recovery, and deterministic routing under real failures. Reimplementing these carelessly would repeat known bugs.
3. **Against choosing Orchestra wholesale:** the measured relevant surface is 12,495 lines before auth/UI/manager dependencies and targets coding agents, not approved game actions.
4. **Against browser-direct speech as a conclusion:** official short-token support establishes feasibility, not microphone quality, diarization stability, echo cancellation, or reconnection behavior in the actual room.
5. **Against server-proxy speech as a conclusion:** central arbitration and key custody are simpler, but an extra audio relay can add work and failure surface; no authorized empirical comparison was run.
6. **Against a latency claim:** no model/STT/TTS paid requests and no room hardware measurement were performed; the owner supplied no numeric SLA.
7. **Against treating diarization as identity:** Deepgram documents speaker labels, not stable named-player recognition for 4–6 people at one table.
8. **Against treating current secret filters as complete:** existing tests prove known fields are removed; they do not prove unknown future fields fail closed.
9. **Against a legal conclusion:** license files and git history establish notice/provenance, not contributor assignments, private-use interpretation, or a separate grant.

## Unresolved decisions for the Phase 2 gate

1. Authoritative server placement: room-local, VPS, or local with VPS backup/gateway.
2. Speech path: browser-direct with short tokens versus server-proxied audio, to be decided by a real room experiment.
3. One common/admin surface versus separate table and admin projections (one physical device may still open both).
4. IP route: DnD fork/history, license-cleared package extraction, separate permission, or behavioral reimplementation.
5. Room audio topology: one shared mic, microphone array, or separate channels/devices; this determines whether diarization or multichannel is appropriate.
6. Tactical-board scope: token movement authority, initiative/turn order, fog/visibility, grid scale, and whether players interact or only view in MVP.
7. Crash semantics: how approved execution checkpoints couple domain mutations, dice events, narration, and retries.
8. Meaning of “three maps”: three tactical square-grid boards, three illustrations, or three adventure/location maps later converted into boards; then generator, required grid/traversability/spawn metadata or converter contract, and asset/provenance policy.
9. Voice roster, selected ElevenLabs models/voice IDs, playback queue, and data-retention policy.
10. Model provider/runtime and least-privilege game tool interface; current agent SDK comparison is informative but not a product decision [L4].

## Sources

### Local primary sources read in full

- **[L1]** `CLAUDE.md` — current architecture/session notes/known issues.
- **[L2]** `docs/product/ai-rpg-table-partner-model.ru.md` — product source of truth.
- **[L3]** `docs/architecture.ru.md`.
- **[L4]** `docs/tasks/sdk-comparison-research.md`.
- **[L5]** `docs/tasks/frontend-migration-blueprint.md` — historical blueprint; current implementation verified separately.
- **[L6]** `docs/tasks/game-dashboard/report.md`.
- **[L7]** `docs/tasks/game-system-prompt/research.md` and `report.md`.
- **[L8]** `docs/tasks/wizard-streaming/report.md` plus current wizard source/tests.
- **[L9]** `TODO.md`.
- **[L10]** DnD source/test files named in matrices A/C; current HEAD `03f94c...` at research start.
- **[L11]** Read-only Orchestra source/tests named in matrix A; `/home/kesha/orchestra` main worktree.
- **[L12]** Both repositories' `LICENSE`, `pyproject.toml`, `CONTRIBUTING.md`, `git log`, `git shortlog`, file-add history, `.gitignore`, and tracked-file scans.

### External official primary sources (opened 2026-08-16)

- **[E1]** Deepgram, [Live Audio WebSocket API](https://developers.deepgram.com/reference/speech-to-text/listen-streaming).
- **[E2]** Deepgram, [Token-Based Authentication](https://developers.deepgram.com/guides/fundamentals/token-based-authentication).
- **[E3]** Deepgram, [Browser authentication pattern](https://developers.deepgram.com/docs/browser-agent-overview).
- **[E4]** Deepgram, [Configure Endpointing and Interim Results](https://developers.deepgram.com/docs/understand-endpointing-interim-results).
- **[E5]** Deepgram, [Utterance End](https://developers.deepgram.com/docs/utterance-end).
- **[E6]** Deepgram, [Speaker Diarization](https://developers.deepgram.com/docs/diarization).
- **[E7]** ElevenLabs, [TTS WebSocket API](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input).
- **[E8]** ElevenLabs, [Understanding audio streaming](https://elevenlabs.io/docs/eleven-api/concepts/audio-streaming).
- **[E9]** ElevenLabs, [API Keys](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys).
- **[E10]** ElevenLabs, [Multi-Context WebSocket and interruption handling](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/multi-context-web-socket).
- **[E11]** ElevenLabs, [Create Single Use Token](https://elevenlabs.io/docs/api-reference/tokens/create).
- **[E12]** Deepgram, [Multichannel](https://developers.deepgram.com/docs/multichannel).
- **[E13]** Deepgram, [Audio Keep Alive](https://developers.deepgram.com/docs/audio-keep-alive).
- **[E14]** Deepgram, [Finalize](https://developers.deepgram.com/docs/finalize).
- **[E15]** Deepgram, [Close Stream](https://developers.deepgram.com/docs/close-stream).
- **[E16]** ElevenLabs, [Models — concurrency and priority](https://elevenlabs.io/docs/overview/models).

## Phase 1 conclusion

The verified minimum is not “copy the dashboard and add microphones.” It is a durable approval-gated turn coordinator between speech, game commands, replayable projections, the tactical board, and TTS. The current DnD repository offers strong, tested domain primitives and projection/provider patterns, while Orchestra offers strong lifecycle/recovery prior art; both full applications contain coupling and license boundaries that make wholesale copying an unproven shortcut. Phase 1 does not select among O1–O4 or prescribe an implementation sequence. It stops at the unresolved decision gate above and requires separate approval before Phase 2 planning.
