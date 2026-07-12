# Vanilla-frontend rewrite — report

## Follow-up: persistent wizard + Codex round 2 (2026-07-12)
Shipped persistent wizard drafts, activity-in-wizard, model list trim (sonnet-5 default,
opus-4-6 removed). Codex re-review (resumed session, reviewing the diff) found 5 issues;
4 fixed, 1 deferred as design scope:

- **[fixed] Path traversal** — `session_id` was a raw path component; `?session_id=../campaigns/x`
  could rmtree a real campaign. Added `is_valid_session_id` (`^[A-Za-z0-9_-]{1,64}$`), enforced at
  the WS handler and DELETE endpoint. Verified: `..`, `/etc/passwd`, spaces, overlong → rejected.
- **[fixed] set_model race on a just-started turn** — `send()` scheduled `_run_turn` which read the
  mutable `self.model_name` late; a `set_model()` in the scheduling window could change the turn's
  model / trigger a mid-turn provider reset. Now `send()` snapshots `model` + `model_dirty` and passes
  them into `_run_turn`. Verified: mid-turn switch leaves the running turn on the old model, applies next turn.
- **[fixed] Stale choices resurrected on replay** — submit cleared choices client-side but nothing was
  persisted, so replay restored the last `show_choices`. Handler now appends a `clear_choices` event when
  the user message is a `[Sidebar selection…]`/`[Sidebar skip…]`. Verified: replay ends with panel hidden.
- **[fixed] Draft delete leaked the provider + could recreate the log** — `delete_draft` is now async and
  `await provider.close()`s the SDK subprocess; the create_campaign path deletes AFTER the turn fully
  unwinds and `return`s from the handler, so nothing appends to a removed log. Verified: provider closed, idempotent.
- **[deferred] Disconnect mid-turn aborts wizard generation** — wizard turns run inline (not
  background-task+broker like game), so a socket drop mid-stream unwinds the turn. Fixing fully = replicating
  the game's broker/background model for wizard (big rewrite). Flagged to orchestrator as a scoped tradeoff.

185 backend tests pass; browser + WS verified after fixes.

## Follow-up: 3 UI features (2026-07-12)
1. **Context usage indicator** — `ClaudeSDKProvider.get_context_usage()` reads `ResultMessage.usage`
   (input + cache_read + cache_creation) / 200k window → `{percent,used_tokens,total_tokens}`, or None
   pre-turn. `game_session._run_turn` publishes a `usage` event before `done` (live-only, never logged).
   Header bar: green <50 / yellow 50-80 / red >80, label "N% ctx".
2. **Model select** — `/api/models` + `ALLOWED_MODELS` whitelist (sonnet-5 / opus-4-6 / opus-4-8).
   `/ws/game?model=` validated against whitelist → falls back to config default on unknown.
   `get_or_create_session` recreates the session on a *different* model **only when not running**
   (mid-turn safety — verified: switching mid-turn keeps the live session). Select `change` reconnects.
3. **Right panel** — wizard choices moved from a bottom bar into a 340px right column with a static
   "Настройки кампании" header. `#app` is now 3 columns; stacks on ≤900px.

### Self-review catch
Model switch on an existing campaign was a **silent no-op** — `get_or_create_session` returned the
cached session with the old model. Fixed: recreate on model change (guarded against mid-turn). Without
this the select would lie for existing campaigns.

### Verify (follow-up)
- `get_context_usage`: None → 50% → 85% unit-tested; colors map correctly in browser (30/65/92 → green/yellow/red).
- `/api/models` returns whitelist + default. Session recreation: 4 cases pass (create / switch-recreate /
  same-noop / running-kept).
- Browser (Playwright): model-select populated, right-panel + "Настройки кампании" + 10 cards, ctx bar
  updates+colors, wizard→campaign switch abandons wizard WS cleanly, history replay intact. No console errors.
- 185 backend tests pass. `usage` event confirmed NOT persisted to event log (history contract intact).

### Codex review round (3× P2, all fixed)
Codex flagged the model-switch design (my session-recreation was too clever):
1. **Orphaned sessions / concurrent turns** — recreating a session on model switch left old
   WS handlers holding the old GameSession → two turns could write one campaign's log.
2. **Mid-turn switch dropped** — "don't recreate while running" meant a switch during streaming
   was silently lost.
3. **Config default bypassed** — `/api/models` hardcoded `sonnet-5` as default, overriding
   `config.model_name` for every game socket.

Fix (simpler than the original): **never recreate the session.** `get_or_create_session` now
keeps one session per campaign forever and calls `session.set_model()` in place. `set_model`
updates the model + a `_model_dirty` flag (works even mid-turn — applies next turn). `_run_turn`
resets the CLI session (`provider.close()`) when dirty, so the new model starts fresh; the event
log is untouched. `_model_options()` makes the default = `config.model_name` (included in the list
even if not in the static whitelist). E2E-verified: switch → next turn closes provider once + uses
new model + clears dirty; one session throughout; config model is the default.

---

## What
Killed the entire React/Vite/TypeScript frontend, replaced with plain
HTML/CSS/JS served by FastAPI (Orchestra pattern). One process, zero npm,
zero build, zero frameworks. CDN-only deps: `marked` + `DOMPurify`.

## Files (+1037 / −8053)
| File | Change | Notes |
|------|--------|-------|
| `frontend/` React app | **deleted** | src/, package.json, vite.config, tsconfig — all gone (~8000 lines) |
| `frontend/index.html` | rewritten (66 lines) | single-page shell: sidebar + main chat, CDN scripts |
| `frontend/css/style.css` | new (249 lines) | Orchestra `:root` tokens, 2-panel flex, left-border bubbles, `.typing-cursor`/`.streaming`/`.waiting-dots` animations |
| `frontend/js/app.js` | new (714 lines) | flat, linear app logic |
| `backend/server.py` | 4 surgical edits | serve index.html at `/`, mount `/static`, drop CORS; API+WS unchanged |
| `webui.sh` | rewritten (3 lines) | single `uvicorn` on :18083, no vite |

## app.js — what it does (flat, no classes)
- **Campaign list**: polls `GET /api/campaigns` every 5s → sidebar. Click → `selectCampaign()`.
- **Game WS**: `/ws/game?campaign=<name>&after_id=<n>`. Bumps `afterId` on any id-bearing
  event + from history max-id. Reconnect: 2s base, ×2 backoff, cap 30s, max 5 attempts.
- **Streaming typewriter** (ported 1:1 from Orchestra): RAF loop, `BASE_CPS=12`,
  `PARSE_INTERVAL=50ms`, adaptive chunk `len/8`, ~20 DOM writes/s, blink cursor `▍`,
  auto-scroll gated at 80px from bottom.
- **Event dispatch**: stream→typewriter, text→finalize bubble, activity→collapsible tool
  line (finalizes stream first for correct order), error→red banner, history→replay+dedup,
  done→flush stream + hide waiting, show_choices/clear_choices/wizard_complete→wizard.
- **Wizard mode**: `/ws/wizard`, client-side preset choices on open, `[System: …presets…]`
  injection on first message, `[Sidebar selection for step "…"]` prefix on submit, strips
  inline ```tool:``` blocks from display, `wizard_complete`→auto-switch to new campaign game WS.
- **Send**: local echo → `ws.send` → clear input; `localEcho` Set dedups on history replay.

## Protocol preserved 1:1
`stream · text · activity · error · done · history · show_choices · clear_choices · wizard_complete`
Backend `game_session`/`event_log`/`live_broker` untouched.

## Verification
- **185 backend tests pass** (`test_ws_game_protocol.py` included). The one collection error
  (`test_encounter_engine.py` dup-basename) is pre-existing pytest infra, out of territory.
- **HTTP smoke**: `/`=200 html, `/static/css`=200 text/css, `/static/js`=200 js, `/api/*` ok,
  `/ws/game` GET=426.
- **WS history replay**: after_id=0→all events, after_id=2→only newer, after_id=3→empty. Correct.
- **Browser (Playwright, headless)**: no console errors, no failed requests, marked+DOMPurify
  load, welcome/chat panes mutually exclusive, wizard renders greeting + 10 preset cards,
  select→submit→local-echo works, `done` unblocks the generating guard, second send works.

## Bug found & fixed during review
`.pane { display:flex }` overrode the `hidden` attribute → welcome + chat rendered
simultaneously. Fixed with `[hidden] { display:none !important }`.

## Breaking
- Frontend now served at `http://127.0.0.1:18083/` (was separate vite :3001). `webui.sh` no
  longer starts a frontend dev server.
- `GET /` now returns HTML, not the JSON info blob.
- CORS middleware removed (same-origin).
