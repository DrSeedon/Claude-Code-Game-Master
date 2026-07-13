# Game session system prompt — root cause

## Question
Context: `/ws/game?campaign=<name>` game turns. Symptom: the DM "несёт бред" —
no DnD rules, no world/campaign awareness. Change under test: does the DM's
`system_prompt` actually contain the DnD rules for the campaign being played?
Baseline: it should contain dm-slots (combat/dice/tools) + narrator + campaign-rules.
Outcome (measurable): length + presence of `dm-roll`/combat/campaign context in the
string returned by `load_system_prompt()`.

## Root cause — CONFIRMED (measurement)
Two chained bugs make the DM's prompt just a narrator style with **zero DnD rules**.

**Bug 1 — `load_system_prompt()` is campaign-blind.**
`backend/claude_dm.py:8` — `def load_system_prompt() -> str` takes **no campaign
argument**. It reads narrator + campaign-rules from the GLOBAL active campaign
(`world-state/active-campaign.txt`, lines 47, 76). But the game WS is
campaign-addressed: `server.py:516 campaign = query_params.get("campaign")`,
`server.py:536 system_prompt = load_system_prompt()` (no campaign passed).
→ The prompt ignores which campaign the socket is for. With a multi-campaign
`_sessions` registry (`game_session.py:21`), it *can't* use the global active
campaign safely anyway (two sessions would need two different prompts).
CONFIRMED — primary source (code).

**Bug 2 — the DnD rules compiler hard-exits without an active campaign.**
`claude_dm.py:28` compiles rules by running
`.claude/additional/infrastructure/dm-active-modules-rules.sh`. That script:
```
ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" ...)
[ -z "$ACTIVE" ] && exit 0        # ← no active campaign → 0 bytes
OVERVIEW=.../$ACTIVE/campaign-overview.json
[ -f "$OVERVIEW" ] || exit 0       # ← no overview → 0 bytes
```
Measured: `bash dm-active-modules-rules.sh` → **0 chars** (no active-campaign.txt
present). Even `--core-only` → 0 (early-exit blocks all modes). So `dm_rules=""`.
CONFIRMED — measurement.

**Net effect (measured):** `load_system_prompt()` returns **2257 chars = only the
epic-heroic narrator fallback** (`claude_dm.py:70`). `'dm-roll' in prompt → False`.
The 66 KB of real DnD rules in `.claude/additional/dm-slots/` (combat, dice-rolling,
skill-checks, spell-casting, tools) never reach the DM.

- `active-campaign.txt`: MISSING
- `/tmp/dm-rules.md`: MISSING → falls to the bash compiler → 0 bytes
- `dm-slots/*.md`: 66234 bytes of real rules, present but unused

## Fix approach (chosen — bug fix, converged)
Make the prompt campaign-aware in `backend/claude_dm.py` (my backend territory),
without global side-effects:

1. `load_system_prompt(campaign_name: str | None = None)` — new optional arg.
   `server.py` passes the WS's `campaign`.
2. Compile the rules for THAT campaign. The compiler keys off `active-campaign.txt`;
   rather than clobber that global file (races across concurrent sessions), pass
   the campaign to the compiler via an **env var override** it reads
   (`DM_ACTIVE_CAMPAIGN`), with a tiny compiler change: `ACTIVE=${DM_ACTIVE_CAMPAIGN:-$(cat active-campaign.txt)}`.
   Fallback: if the campaign has no overview.json, still emit CORE slots (so the DM
   always gets DnD rules even for a bare campaign) — the current early-exit is too
   aggressive.
3. Read narrator + campaign-rules from `campaigns/<campaign_name>/`, not the global one.

Alternative considered (rejected): read dm-slots directly in Python, bypassing the
bash compiler. Rejected — duplicates the compiler's module/slot-replacement logic
(66 KB, module addons, conflict handling); would diverge from the canonical rules.
Keep one source of truth (the compiler), just feed it the right campaign.

### Territory note
The one-line compiler tweak is in `.claude/additional/infrastructure/` (DM-system
core, outside frontend/backend). Flagging for approval — it's the minimal change;
the alternative (reimplement in Python) is worse. If the orchestrator prefers zero
`.claude/` edits, I'll set `active-campaign.txt` transactionally in Python instead
(with the concurrency caveat).

## Affected files
- `backend/claude_dm.py` — add `campaign_name` param, campaign-scoped narrator/rules,
  env-var to the compiler, CORE-slots fallback.
- `backend/server.py` — pass `campaign` to `load_system_prompt(campaign)`.
- `.claude/additional/infrastructure/dm-active-modules-rules.sh` — honor
  `DM_ACTIVE_CAMPAIGN` env + emit CORE slots when no campaign overview (2-line change).
- `frontend/js/app.js` + `index.html`/`css` — Task 1 UI: empty-chat "▶ Начать игру"
  placeholder; Task 2 UI: `wizard_complete` → in-chat button, no auto-switch.

## Risks / edge cases
- Concurrent sessions for different campaigns → must NOT share global state. Env-var
  approach is per-subprocess-call, so safe.
- Campaign with no overview.json (fresh) → CORE slots still emit (fallback fix).
- `/tmp/dm-rules.md` pre-compiled path — if present it's used verbatim (campaign-blind);
  should be bypassed when a campaign is passed, else stale. Fix: only use /tmp cache
  when campaign_name is None.
