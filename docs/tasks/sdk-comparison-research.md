# SDK Implementation Comparison: Orchestra vs DnD Game Master

**Question:** What does Orchestra (`/mnt/data/Projects/Python/orchestra/`) do in its Claude SDK client, streaming backend, frontend, MCP tools, session persistence, and resilience layers that the DnD web client (`backend/` + `frontend/`) is missing or doing worse — and what concretely should DnD adopt?

**Method:** Full read of DnD `backend/` (server.py, providers/*, tools_registry.py, wizard_mcp.py, chat_history.py, config.py, claude_dm.py) and frontend (useWebSocket.ts, Chat.tsx). Full read of Orchestra `app/backend_claude.py`, `session.py`, `session_turns.py`, `session_hibernate.py`, `session_state.py`, `live_broker.py`, `events.py`, `backend_protocol.py`; targeted reads of `manager.py` (auto_resume_all), `routes/sessions.py` (SSE), `mcp_stdio.py`, `static/js/app.js` (SSE client). All line references verified against source this session.

**One correction to the task framing (CONFIRMED):** Orchestra's frontend is NOT React. It is vanilla JS + HTMX + **SSE** (`EventSource`), a 6,480-line `app/static/js/` bundle. DnD is React + raw **WebSocket**. So frontend comparison is about *patterns* (reconnect, replay, dedup), not framework code reuse.

---

## 1. Architecture comparison table

| Area | Orchestra | DnD | Verdict |
|---|---|---|---|
| **SDK wrapper** | `ClaudeBackend` (`app/backend_claude.py`, 431 L) → unified `AgentEvent` stream; one of 3 backends behind a `Protocol` (`backend_protocol.py`) | `ClaudeSDKProvider` (`providers/claude_sdk.py`, 243 L) behind `BaseProvider` ABC — clean abstraction, similar idea | DnD's provider abstraction is fine; the *options and lifecycle* inside it are weak (below) |
| **Streaming granularity** | `include_partial_messages=True` + `StreamEvent` deltas → token-level typewriter (`backend_claude.py:139`, `268-286`) | `include_partial_messages=False` (`claude_sdk.py:99`) → whole `TextBlock`s only; "streaming" arrives in multi-paragraph chunks | Orchestra ✅ |
| **Turn ↔ connection coupling** | Turn runs in a server-side `asyncio.Task` (`session.py:421` `_claude_event_loop`), independent of any UI client; SSE is a read-only viewer | Turn generation lives inside the WebSocket handler coroutine; WS disconnect → `provider.interrupt()` + close (`server.py:634-639`) — a page refresh **kills the DM's turn mid-generation** | Orchestra ✅ (biggest architectural gap) |
| **Concurrent clients** | N SSE viewers per session, all fed by `LiveBroker` pub/sub + DB replay | Each `/ws/game` connection builds its **own** `ClaudeSDKClient` bound to the **same** session UUID (`server.py:586-592`) — two tabs fork the CLI session | Orchestra ✅ (DnD correctness bug) |
| **Event persistence** | Every event (`text`/`tool`/`tool_result`/`status`/`error`) → SQLite `add_log`, fire-and-forget on a dedicated thread pool (`session.py:983-985`, `30-40`) | Only final user/assistant text → `chat-history.json`, rewritten wholesale each turn (`server.py:618-625`); tool activity is lost on reload | Orchestra ✅ |
| **Live reconnect replay** | `LiveBroker` accumulates in-flight partials, replays them to a reconnecting subscriber (`live_broker.py:20-29`); SSE resumes from `after_id` | No replay of an in-flight turn; no `after_id`; reload loses whatever streamed since last save | Orchestra ✅ |
| **Client reconnect** | `EventSource.onerror` → close + retry in 2 s, resume from `lastId` (`app.js:210-215`) | `useWebSocket.ts` has **no reconnect at all** — on close the UI is dead (input disabled) until manual page reload | Orchestra ✅ |
| **Resilience** | connect timeout 60 s; reconnect loop capped at 5 consecutive failures; heartbeat/zombie detection; turn timeout 600 s with auto-continue; rate-limit retry 30/60/90 s; session-limit detection; auto-continue on `max_turns` (cap 5) | `try/except` around the message loop; on exception drop client and hope next message reconnects (`claude_sdk.py:207-214`). No timeouts, no retry, no heartbeat | Orchestra ✅ |
| **Restart survival** | Sessions in SQLite; `auto_resume_all` resets `running→idle`, reloads sessions, injects staggered "server restarted, continue" notices (`manager.py:1144-1214`) | Session UUID in `storage/sessions/<key>` file; resume works passively on next connect. Acceptable for a game, but a mid-turn server restart silently loses the turn | Orchestra ✅ (DnD partial credit — resume-by-UUID is the same core mechanism) |
| **MCP tools** | External stdio FastMCP process calling back over HTTP + `INTERNAL_TOKEN` (`mcp_stdio.py:1-57`) — avoids in-process SDK control_request deadlock (claude-agent-sdk #425/#701) | Wizard: in-process `create_sdk_mcp_server` + `asyncio.Queue` bridge (`wizard_mcp.py`) — good pattern for its scope. Game: **no MCP**; SDK provider silently ignores the `tools` arg | Split decision (see §2.6) |
| **Tool schema duplication** | One tool source (MCP server) | `tools_registry.py` (611 L of Anthropic schemas + subprocess exec): schemas fetched by `server.py` and passed to *both* providers, but **executed only** via the API provider; SDK provider ignores them and uses CLI built-in Bash → same game logic exposed two different ways, guaranteed drift | Orchestra ✅ |
| **Permissions** | `permission_mode="default"` + `can_use_tool` callback with explicit deny-list and per-input rules (`backend_claude.py:44-55`, 137) | `permission_mode="bypassPermissions"` (`claude_sdk.py:98`) — blanket approval of everything incl. arbitrary Bash | Orchestra ✅ |
| **System prompt** | Preset-append: `{"type":"preset","preset":"claude_code","append":...}`, and **only when not resuming** (`backend_claude.py:144-147`) | Full-replace string, passed on every connect incl. resume (`claude_sdk.py:101-102`) | Orchestra ✅ (see §2.5) |
| **Cost/usage tracking** | Full extraction from `ResultMessage.usage` — cache hit %, input/output tokens, recomputed cost (`backend_claude.py:356-418`), 4-level cost model | `ResultMessage` used only for session-id capture and error text; usage discarded. `get_context_usage()` exists in the provider but **no caller** in server.py (dead code) | Orchestra ✅ |
| **Interrupt** | HTTP endpoint + MCP tool + UI button; also implicit on stop/kill | `provider.interrupt()` exists but is only invoked on WS **disconnect**; no user-facing stop | Orchestra ✅ |
| **Config** | `.env` via systemd EnvironmentFile, single source, read once at startup | `get_config()` re-reads env + `mkdir` on **every call** (each endpoint hit, each WS connect) (`config.py:60-112`) — harmless but sloppy | Orchestra ✅ (minor) |
| **Frontend state** | Global log store keyed by agent, id-based dedup, load-more pagination, local-echo dedup (`app.js:159-216`) | `messages: string[]` grows unboundedly (`useWebSocket.ts:31`); every chunk triggers a full-history effect scan; only last element processed (bug, §4.1) | Orchestra ✅ |

**Where DnD is actually fine / better than it looks:**
- `BaseProvider` ABC + factory (`providers/base.py`, `factory.py`) is a *cleaner provider abstraction than Orchestra's* — Orchestra grew `backend_for_model` dispatch inside `AgentSession._make_backend` (`session.py:207-257`). DnD should keep this layer.
- The wizard's `WizardEvents` queue bridge (`wizard_mcp.py:20-27`) is a legitimate, tidy pattern for UI-side-channel tools.
- Storing only the CLI session UUID and letting `~/.claude/projects/*.jsonl` own the transcript is the same design Orchestra uses (SQLite `session_id` column). Correct call.

---

## 2. Best practices from Orchestra that DnD is missing

### 2.1 Decouple the turn from the transport (the big one)
Orchestra: `AgentSession.send()` submits to the backend and a **persistent listener task** (`session.py:421-498`) consumes events, logging each to DB and publishing partials to `LiveBroker`. UI clients subscribe/unsubscribe freely; nobody's browser owns the turn.
DnD: `game_websocket` (`server.py:546-639`) does `receive_text → async for chunk → send_text` inline. Consequences, all real:
- refresh/navigate during a long DM narration → `WebSocketDisconnect` → `provider.interrupt()` → turn dies, tool side effects (HP already deducted via `dm-inventory.sh`) are half-applied but the narration is lost and not saved to history;
- phone locks the screen → same;
- nothing can observe or stop the turn except that one socket.

**Adopt:** a per-campaign `GameSession` object (module-level registry keyed by campaign name) owning the provider + a listener task + a small in-memory broker; WS handlers become thin subscribe/publish shims. This is ~150 lines and unlocks §2.2-2.4 almost for free. Orchestra's `LiveBroker` (`live_broker.py`, 58 lines, zero deps) can be copied nearly verbatim.

### 2.2 One provider per session key, enforced
Orchestra's manager keeps `sessions: dict[id → AgentSession]` and always routes through it. DnD creates a fresh `ClaudeSDKClient` per WS connection against the same resume UUID (`server.py:586-592` + `claude_sdk.py:105-107`). Two browser tabs → two `claude` subprocesses resuming one session → whichever finishes a turn last wins `_save_session_id()`, and the CLI transcript forks. With the registry from §2.1 this bug disappears.

### 2.3 Token-level streaming
`include_partial_messages=True`, handle `StreamEvent` → `content_block_delta`/`text_delta` (`backend_claude.py:268-286`). DnD's UI already appends text chunks (`Chat.tsx:71-84`), so flipping this on plus one new event branch in the provider gives a real typewriter — but **only after the §3.1 frame-loss bug is fixed** (higher chunk rate makes that bug constant, per Codex review). Keep the final `TextBlock` as the authoritative full text (Orchestra rule: partials are ephemeral, the final `text` event is the DB truth — `session.py:530-534`).

### 2.4 Persist an event log, not a chat mirror
Orchestra logs every event with a monotonically increasing id and streams with `after_id` resume (`routes/sessions.py:273-315`). DnD rewrites `chat-history.json` wholesale each turn (`server.py:618-625`) and saves **only if the turn produced text** — a turn that errors after tools ran leaves no trace, and the user message itself is dropped from history. Also `%%ACTIVITY%%` tool events are never saved, so reload shows narration without the dice rolls the narration references.
**Adopt:** append-mode JSONL (or SQLite) per campaign: `{id, type, content, ts}` for `user_message | text | activity | error`. History replay endpoint reads it; the WS `history` message goes away or pages.

### 2.5 SDK options hygiene (`_build_options`, `claude_sdk.py:88-107` vs `backend_claude.py:117-167`)
Concrete deltas to copy:
- `system_prompt={"type": "preset", "preset": "claude_code", "append": dm_rules}` instead of full replace. DnD's SDK path depends on the CLI's built-in Bash tool to run `tools/dm-*.sh`; replacing the whole Claude Code preset removes the CLI's own tool-usage scaffolding. Confidence: **LIKELY** improves tool reliability (SDK semantics of string-replace are documented; magnitude untested).
- Don't re-send `system_prompt` when `resume` is set (Orchestra sends it only on fresh sessions, `backend_claude.py:144-147`).
- `max_turns=25` is low for a combat round (attack roll + damage + HP update + condition + loot ≈ 2 turns each). Orchestra uses 200 **plus** auto-continue on `max_turns` stop reason (`session_turns.py:82-91`). At minimum raise it and surface the stop reason.
- `max_buffer_size=50MB` (`backend_claude.py:140`) — protects against SDK buffer overflow on huge tool outputs (e.g. `dm-overview.sh` on a big world.json).
- `env={"DISABLE_NON_ESSENTIAL_MODEL_CALLS": "1", "DISABLE_TELEMETRY": "1"}` + explicit HTTPS_PROXY/HTTP_PROXY/NO_PROXY passthrough (`backend_claude.py:121-127`) — the proxy passthrough is MANDATORY in this household (all Anthropic traffic goes through `.env` proxy).
- `asyncio.wait_for(client.connect(), timeout=60)` (`backend_claude.py:180`) — DnD's `connect()` can hang forever if the CLI stalls; the WS then hangs silently.
- Replace `bypassPermissions` with `can_use_tool` allow-callback (`backend_claude.py:44-55`): auto-allow the game tool surface, deny `run_in_background`, and you get a natural interception point for logging tool calls. **UNCERTAIN** how much this matters for a local single-player game, but it costs ~15 lines.

### 2.6 MCP as the single tool surface (kill the duplication)
Current DnD state (CONFIRMED by reading): `tools_registry.py` defines 12 Anthropic-format schemas + subprocess executors, consumed **only** by `AnthropicAPIProvider` (`anthropic_api.py:135`). `ClaudeSDKProvider.process_message` accepts `tools` and never touches it — the SDK DM plays through CLI Bash + `/tmp/dm-rules.md`. Two parallel tool systems, different behavior per provider (API DM can't use `dm-wiki.sh`, `dm-search.sh`, custom-stats middleware, module hooks — none are in the registry).
**Adopt the wizard's own pattern for the game:** build an in-process SDK MCP server (`create_sdk_mcp_server`, exactly like `wizard_mcp.py`) whose tools shell out to `tools/dm-*.sh`, pass it via `mcp_servers` for **both** providers... except the API provider can't consume SDK MCP. Realistic options:
  1. Keep bash-via-CLI for SDK (works today), generate `tools_registry` schemas from a single declarative table, or
  2. Declare the API provider legacy and delete `tools_registry.py` (639 + 611 lines gone).
Given "ТОЛЬКО ПОДПИСКА. НИКАКИХ API-КЛЮЧЕЙ" is the house rule, option 2 is the honest one — flagging as a **decision for the orchestrator**, not doing it.
Caveat if game tools ever become MCP tools that call back into the FastAPI server: that's the in-process deadlock Orchestra dodged by going external-stdio (`mcp_stdio.py:1-6`, claude-agent-sdk issues #425/#701). Wizard tools are safe because they only `put_nowait` on a queue.

### 2.7 Resilience ladder (in Orchestra, absent in DnD)
Each is independent and copyable:
- **Reconnect-and-continue**: on stream death, `backend.reconnect()` then inject `"[system] Connection was restored after interruption. Continue your work."` (`session.py:485-490`). For a game: "continue narrating where you left off".
- **Consecutive-failure cap** (5) before giving up (`session.py:419, 466-474`) — prevents infinite reconnect storms.
- **Turn timeout** (600 s) with a nudge message rather than a kill (`session.py:431-437`).
- **Heartbeat/zombie detection**: RUNNING with 30 min of silence, or listener task dead while RUNNING → recover (`session_hibernate.py:55-97`).
- **Rate-limit retry** with linear backoff 30/60/90 and session-limit (5 h subscription quota) detection via text sniffing `"You've hit your session limit"` (`session.py:556-558`, `581-592`) — directly relevant to DnD since it runs on the same Max subscription.
- **Idle hibernate**: disconnect the `claude` subprocess after 5 min idle, transparently reconnect-with-resume on next message (`session_hibernate.py:29-53`). DnD keeps a subprocess alive per open tab for hours of idle play. Cheap win: RAM and one fewer stale process.

### 2.8 Frontend patterns worth porting into React
- Reconnect with backoff + resume cursor (`app.js:158-216`). In hook form: on `close`/`error`, retry after 2 s with attempt counter; re-request history after `lastId` (needs §2.4's ids).
- Local-echo dedup (`app.js:171-184`) — DnD currently appends the user message locally *and* would duplicate it if history replay includes it after reconnect.
- Bounded buffers — Orchestra pages logs at 100/500; DnD keeps every raw WS frame in React state forever.

---

## 3. Anti-patterns in DnD (that Orchestra avoids)

### 3.1 `Chat.tsx` processes only the **last** WS frame — chunk loss (bug, CONFIRMED by code reading)
`useWebSocket` appends every frame to `messages`; `Chat.tsx:41-99` runs an effect on `rawMessages` change but reads **only** `rawMessages[rawMessages.length - 1]`. React 18 batches state updates: two `onmessage` callbacks in one microtask window → one effect run → the earlier frame is silently dropped. At block-level streaming this is occasional (lost `activity` lines, missing text chunk); with token-level streaming (§2.3) it becomes constant corruption. **This must be fixed before adopting partial streaming.** Fix: track a consumed-index ref and process `rawMessages.slice(consumed)`; or better, deliver parsed events via callback/reducer from the hook instead of accumulating raw strings.

### 3.2 `error` events are invisible in the UI; stuck spinner on escaped errors (bug, scope refined after Codex review)
Two distinct failure classes:
- **Provider-internal errors** (SDK exceptions inside `process_message`, `claude_sdk.py:207-214`): caught, yielded as `{"type":"error"}`, generator ends normally → server *does* send `done`. Spinner stops — but the error itself is **invisible**, because the frontend has no `error` branch (`Chat.tsx:47-84` handles `activity|history|done|text` only): the JSON parses, matches nothing, is silently dropped. Player sees the DM just... not answer.
- **Escaped errors** (raised outside the provider's try: `load_session` guard at `claude_sdk.py:149-152`, or a failed `websocket.send_text`): hit the server's `except` (`server.py:627-632`), which sends `error` **without** `done` → stuck "DM печатает..." spinner *and* invisible error.

Orchestra: errors are first-class log rows rendered in chat, and turn-end status is computed server-side. Fix: `finally: send done` server-side; render `error` type client-side (fixes both classes).

### 3.3 Turn state lives in the socket handler (§2.1) — refresh kills the DM mid-sentence, half-applied tool effects.

### 3.4 Session fork via per-connection providers (§2.2).

### 3.5 Dual tool systems with drift (§2.6) — the API-provider DM and SDK-provider DM are *different games* (registry lacks wiki/search/craft/modules).

### 3.6 History as rewrite-the-world JSON (§2.4) — O(n) rewrite per turn, no tool activity, drops turns that errored, and `load_chat_history → append → save` inside the WS handler races if two campaigns/connections ever share a dir.

### 3.7 `bypassPermissions` + `allow_origins=["*"]` + zero auth. For localhost play it's tolerable; the moment this binds to `0.0.0.0` (which it does — `config.py:30` `backend_host: "0.0.0.0"`) anyone on the LAN has an unauthenticated Claude with arbitrary Bash in your repo. Orchestra: cookie auth + `INTERNAL_TOKEN` for MCP callbacks. Minimum fix: bind 127.0.0.1 by default.

### 3.8 Dead code / unwired capabilities: `provider.get_context_usage()` never called; `tools` arg on the SDK path ignored; `_expected_results` counter emulates what SDK's `receive_response()` already does.

---

## 4. Migration plan (prioritized, each step independently shippable)

**P0 — correctness bugs (do first, small):**
1. `Chat.tsx`: consume **all** unprocessed frames, not just the last (consumed-index ref). ~10 lines.
2. `server.py`: wrap turn in `try/finally` → always send `done`; `Chat.tsx`: render `type:"error"` as a visible message and stop the spinner. ~15 lines.
3. `useWebSocket.ts`: auto-reconnect with 2 s backoff + attempt cap (pattern from `app.js:210-215`). ~20 lines.
4. `claude_sdk.py:_build_options`: add `asyncio.wait_for(connect, 60)`; don't pass `system_prompt` when resuming.
5. `config.py`: default `backend_host` → `127.0.0.1` (one line; closes the LAN-exposed `bypassPermissions` hole, §3.7). *(Promoted to P0 per Codex review.)*
6. Interim single-connection guard on `/ws/game`: reject a second concurrent connection for the same campaign (~5 lines; stops the session fork §2.2 until the P1 registry lands). *(Promoted per Codex review.)*

**P1 — the session registry (medium, the structural fix):**
5. `GameSession` registry: one provider + listener task + mini-broker per campaign, module-level dict; WS handlers subscribe/unsubscribe (Orchestra blueprint: `session.py` send/listen split + `live_broker.py` copied as-is). Fixes §3.3/§3.4, enables everything below.
6. Interrupt endpoint (`POST /api/game/interrupt`) + stop button — trivial once #5 exists (`provider.interrupt()` is already implemented).

**P2 — streaming + history quality:**
7. `include_partial_messages=True` + `StreamEvent` handling in provider (blueprint `backend_claude.py:268-286`). Requires P0-1 first.
8. Append-only event log (JSONL per campaign) with ids; replay `after_id` on reconnect; persist `activity` events. Replaces `chat_history.py` rewrite model.

**P3 — resilience ladder:**
9. Reconnect-and-continue + consecutive-failure cap (blueprint `session.py:459-498`).
10. Rate-limit/session-limit detection with backoff (blueprint `session.py:556-592`) — same Max subscription, same 5 h window problem.
11. `max_turns` raise + auto-continue nudge (blueprint `session_turns.py:82-91`); turn timeout.
12. Idle hibernate: disconnect CLI subprocess after N min idle, resume on next message (blueprint `session_hibernate.py:29-53`).

**P4 — architecture decisions (need orchestrator/user sign-off):**
13. Tool surface unification (§2.6): recommend dropping `AnthropicAPIProvider` + `tools_registry.py` (house rule: subscription only) → single SDK path, `-1,200` lines; else generate both schemas from one table.
14. `can_use_tool` allow-list instead of `bypassPermissions`; bind `127.0.0.1` by default.
15. Usage/cost surfacing: read `ResultMessage.usage` (blueprint `backend_claude.py:376-397`), wire the already-existing `get_context_usage()` into a status endpoint → "context 73%" indicator, auto-warn before CLI auto-compact eats the campaign context.

---

## 5. Confidence & counter-evidence

| Finding | Confidence | Basis |
|---|---|---|
| Last-frame-only processing loses chunks (§3.1) | CONFIRMED (mechanism) / LIKELY (frequency) | Code reading; React 18 batching is documented behavior. Not reproduced live this session |
| Error invisible in UI (§3.2, all errors) | CONFIRMED | No `error` branch in Chat.tsx |
| Stuck spinner (§3.2, escaped errors only) | CONFIRMED (narrowed by Codex) | Provider-caught errors still get `done`; only errors escaping the provider skip it |
| Two tabs fork the CLI session (§2.2) | CONFIRMED (code) | Per-connection `create_provider` + shared resume UUID; not reproduced live |
| SDK provider ignores `tools` / dual tool system (§2.6) | CONFIRMED | `tools` param unreferenced in `claude_sdk.py`; `execute_tool` imported only by `anthropic_api.py` |
| Preset-replace degrades CLI tool use (§2.5) | LIKELY | SDK semantics documented; magnitude not measured |
| `bypassPermissions` on 0.0.0.0 is a LAN exposure (§3.7) | CONFIRMED (config) | `config.py:30`; actual exploitability depends on user's network |
| Orchestra patterns are portable at quoted effort | LIKELY | LiveBroker/hibernate/retry are dependency-free; estimates are engineering judgment |

**Counter-evidence / what argues against wholesale adoption:** Orchestra is a multi-agent fleet manager — much of its machinery (status persistence in SQLite, WAITING state, auto-report, TG bridge, worktrees) exists because *many* long-lived agents outlive any viewer. DnD is one player, one campaign, one session at a time; a full `AgentSession`-grade port would be over-engineering. The plan above deliberately takes only the transport-decoupling, streaming, and resilience slices, not the orchestration machinery. Also, DnD's WS-per-client with server push is not inherently worse than SSE+poll — the defect is turn ownership, not the transport choice.

**Second opinion (Codex, GPT-5.6, source-evidence review — `docs/tasks/codex-review-sdk-comparison.md`):** all load-bearing claims confirmed against source. Four refinements accepted and folded in: (1) stuck-spinner narrowed to escaped-provider errors (provider-caught errors do get `done`); (2) `tools_registry` schemas are *passed* to both providers, *executed* only by API provider; (3) partial streaming requires the §3.1 fix first — "no frontend changes" retracted; (4) `127.0.0.1` bind + single-connection guard promoted into P0.

**Sources:** direct code reading of both repos this session (file:line refs throughout). No external sources required; SDK behavior claims (preset semantics, `receive_response`, partial messages) come from claude-agent-sdk usage evidenced in Orchestra's working production code. Cross-verified by Codex adversarial review (above).
