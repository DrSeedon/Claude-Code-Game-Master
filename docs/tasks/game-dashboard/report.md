# Game dashboard, session controls, limits — report

4 problems (priority 1>2>4>3), all shipped.

## P1 — DM didn't know it was inside a campaign
It ran a campaign-selection menu on "Начать игру" instead of the session. Fix:
`backend/claude_dm.py` — `_campaign_context(project_root, campaign_name)` builds a
`# Current Campaign` block (genre/tone/setting from overview.json + character
name/HP/location from `get_character_status`) ending with an explicit instruction:
"You are ALREADY running this campaign … do NOT list campaigns … immediately narrate
the scene". Appended to the system prompt. Best-effort — a missing overview/character
yields a thinner block, never an error (wrapped in try/except).
Verified: prompt contains the block with the setting + the no-menu instruction.

## P2 — character dashboard
Frontend only (`/api/status?campaign=X` already existed). `.char-panel` strip below
the header: name, HP bar (green/yellow/red), XP, gold (formatted), inventory count,
location. Loaded on `selectCampaign`, refreshed after each `done`, hidden in wizard /
on mobile-back. Verified: shows "Aria" for a seeded campaign.

## P4 — new-session button (reset Claude context, keep history)
- `claude_sdk.py`: `provider.reset()` = disconnect + `_session_id = None` (plain
  `close()` keeps session_id and resumes — wrong for a fresh session).
- `game_session.py`: `reset_session()` (refuses while a turn runs) + `peek_session()`.
- `server.py`: `POST /api/campaigns/{name}/reset-session` — validates name, 409 if a
  turn is running, `{reset:false}` if no live session.
- Frontend: 🔄 button → confirm → **close WS first** (so no turn can start between the
  server's running-check and reset) → POST → reconnect keeping `afterId` (no history
  replay → no chat duplication). Verified: 2 msgs before → 2 after (no dup), reconnected.

## P3 — rate/session limit indicator
- `claude_sdk.py`: `_rate_limit_info(err)` matches rate/session/usage-limit/429/overloaded
  in the exception text + extracts `retry_after` seconds; `process_message` yields
  `{type:"rate_limit", content, retry_after?}` and stops (doesn't burn the 3-retry budget).
- `game_session` forwards it via broker (not written to the event log).
- Frontend: `.rate-limit-bar` warning ("⏳ Лимит: подождите ~Ns"), cleared on next send.
Verified: parser classifies rate/session/429 correctly, returns None for normal errors;
UI bar shows on the event.

## Files (+~240)
backend/claude_dm.py, game_session.py, providers/claude_sdk.py, server.py;
frontend/index.html, css/style.css, js/app.js; tests/test_claude_dm.py (+3 tests).

## Tests
194 backend pass (`uv run pytest`; +3: campaign-context block, rate_limit classify,
existing name-validation). Browser (Playwright): char panel, new-session (no dup),
rate-limit bar, wizard hides them. No console errors.

## Adversarial self-review
- **reset TOCTOU** — the endpoint checks `session.running`, but a turn could start
  between check and `provider.reset()`. Mitigated: frontend closes the WS *before* the
  POST, so the client can't send during reset. (Server check remains as defense.)
- **reset chat duplication** (self-caught) — first draft reset `afterId=0` → full history
  replay would DUPLICATE the on-screen chat. Fixed: keep `afterId` → no replay.
- **get_character_status on every prompt build** — runs once per WS connect (not per
  turn), wrapped in try/except → can't crash the connect.

## Codex
`codex_review` ran (bg-d00a609140, reported done) but wrote **no artifact** (recurring
Codex CWD/output bug this session). Addressed the load-bearing concern it would raise
(reset race) proactively; rest verified by tests + browser. Re-run on the uncommitted
diff for a formal pass.

## Not deployed — commit only.
