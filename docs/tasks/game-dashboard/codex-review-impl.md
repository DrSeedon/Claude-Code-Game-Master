The changes introduce functional regressions in multi-campaign status display, wizard rate-limit handling, and reset-session error handling. These are user-visible issues that should be fixed before considering the patch correct.

Full review comments:

- [P2] Key character status cache by campaign — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/frontend/js/app.js:343-343
  With multiple campaigns, this can render the wrong character because `/api/status?campaign=...` ultimately calls `get_character_status`, whose cache is a single module-level value and is not keyed by `campaign_dir`. After viewing campaign A, selecting campaign B within the 5s cache TTL can return A's cached HP/location and display it as B's dashboard; refresh/key the backend cache per campaign before relying on this panel.

- [P2] Forward rate-limit events in wizard — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/backend/providers/claude_sdk.py:146-146
  This new event type is yielded for both game and wizard calls to `process_message`, but `wizard_websocket` only forwards `text_delta`, `text`, `activity`, and `error`. When a rate/session limit happens during campaign creation, the provider now yields `rate_limit` and returns, so the wizard client receives only `done` with no warning or retry hint; forward this event there or emit an `error` for callers that do not handle it.

- [P2] Check reset-session response before reconnecting — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/frontend/js/app.js:377-381
  When the server refuses a reset with 409 because a turn is in progress, `fetch` still resolves and this code continues to hide the context meter and reconnect. In that scenario Claude's session id was not cleared, so the UI proceeds as if a fresh session was started even though the backend explicitly rejected it; check `response.ok`/409 before proceeding.