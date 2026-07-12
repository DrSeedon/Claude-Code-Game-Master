# Vanilla-frontend rewrite — report

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
