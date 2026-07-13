# Game system prompt fix + wizard-complete UX — report

## Task 1 — DM got no DnD rules (root cause fixed)
The DM's `system_prompt` was **2257 chars = only a narrator style**, `'dm-roll' in prompt → False`.
The 66 KB of real rules in `.claude/additional/dm-slots/` never reached it. Three chained bugs:

1. `load_system_prompt()` took **no campaign arg** — read narrator/rules from the GLOBAL
   `active-campaign.txt`, but `/ws/game` is campaign-addressed. `server.py` called it with none.
2. The rules compiler `dm-active-modules-rules.sh` did `[ -z "$ACTIVE" ] && exit 0` → **0 bytes**
   with no global active campaign. Measured: compiler → 0 chars.
3. (found while testing) `common-module.sh find_project_root` tested `[ -d "$dir/.git" ]`; in a
   git **worktree** `.git` is a FILE → walked past the worktree root → wrong `PROJECT_ROOT` → no slots.

### Fix
- `backend/claude_dm.py`: `load_system_prompt(campaign_name=None)` — passes the campaign to the
  compiler via a `DM_ACTIVE_CAMPAIGN` env override (per-subprocess, race-free vs. clobbering the
  global file); reads narrator/rules from `campaigns/<name>/`; uses the `/tmp/dm-rules.md` cache only
  when no campaign is scoped. Defense-in-depth: rejects a campaign name with `/`, `\`, or `..`.
- `.claude/additional/infrastructure/dm-active-modules-rules.sh`: honor `DM_ACTIVE_CAMPAIGN`; emit
  CORE slots even with no campaign overview (dropped the hard early-exit; Python step tolerates an
  empty overview path → no modules, core slots).
- `.claude/additional/infrastructure/common-module.sh`: `find_project_root` `-d` → `-e` so `.git`
  (a file in a worktree, a dir in a clone) both resolve. Fixes the DM system in ANY worktree.
- `backend/server.py`: `load_system_prompt(campaign)`; validate `?campaign=` (`^[A-Za-z0-9_-]{1,64}$`)
  before use — blocks path traversal into the env/path (my change widened the campaign name's reach).

### Measured (pass/fail defined before: prompt must contain dm-roll + combat + narrator)
- `load_system_prompt('dragon-quest')` → **66479 chars**, has `dm-roll`, combat, dice, narrator. PASS.
- Bare campaign (no modules) → 66479, has dm-roll (CORE fallback). PASS.
- Traversal `'../../etc'` → rejected → falls back to core rules, reads nothing outside campaigns/. PASS.

## Task 1 UI — empty-chat placeholder
`frontend/js/app.js` + `css`: an empty game chat shows `.chat-start` ("⚔️ Готов к приключению?" +
"▶ Начать игру"). The button calls `sendChat('Начать игру')`. Removed on any message/history render
(`removeChatStart()` in `addUserMessage`/`addDmMessage`/`createStreamBubble`); shown in `selectCampaign`.

## Task 2 — wizard no longer auto-switches
`onWizardComplete`: instead of `selectCampaign(name)` immediately, it adds an in-chat
"✅ Кампания создана! …" message + a "▶ Начать играть" button (→ `selectCampaign(name)`). The user
can keep talking to the wizard; the campaign appears in the sidebar via poll.

## Files (+240 / −63)
- backend/claude_dm.py, backend/server.py
- .claude/additional/infrastructure/{dm-active-modules-rules.sh, common-module.sh}
- frontend/js/app.js, frontend/css/style.css
- tests/test_claude_dm.py (new), tests/test_ws_game_protocol.py (mock signature)

## Tests
- 190 backend pass (`uv run pytest`, was 188 + 2 new claude_dm; ws-protocol mock updated to `*a,**k`).
- Browser (Playwright): empty campaign → placeholder + "▶ Начать игру" → click sends + removes it;
  `wizard_complete` keeps mode='wizard', shows the button, click → mode='game'. No console errors.

## Adversarial self-review
- **Path traversal** (self-caught, same class Codex hit on the wizard): campaign name now flows into a
  bash env + path. Added validation at the WS handler + a guard in `load_system_prompt`. Blocked.
- **Concurrency**: `DM_ACTIVE_CAMPAIGN` is set on a per-`subprocess.check_output` `env=` dict — not a
  process-global — so two sessions for different campaigns don't clobber each other.
- **chat-start lifecycle**: guarded against duplicates (`if querySelector('.chat-start') return`) and
  removed by every message-add path; can't get stuck once a message renders.

## Codex
`codex_review` ran (bg-8b82e3fe53, reported done) but wrote **no artifact** (known Codex CWD/output
bug — recurred on the wizard task too). I proactively fixed the one load-bearing concern it would
raise (campaign-name path traversal) and verified the rest by measurement/tests. Re-run on the
uncommitted diff if a formal pass is required.

## Not deployed
Per instruction — commit only. Orchestrator deploys.
