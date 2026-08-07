# DM System - Developer Rules

## Stack
- Python via `uv run python` (never `python3`)
- Bash wrappers in `tools/` → Python modules in `lib/`
- Tests: `uv run pytest`

## Architecture
- `lib/` — CORE Python: dice, player, session, inventory, currency, NPCs, locations, plots, consequences, notes
- `tools/` — thin bash wrappers + `dispatch_middleware` for module hooks
- `modules/` — optional gameplay modules (custom-stats, world-travel, mass-combat, firearms-combat)
- `.claude/additional/dm-slots/` — DM rules (loaded into `/tmp/dm-rules.md`)
- `.claude/additional/infrastructure/` — loaders (dm-active-modules-rules.sh, dm-campaign-rules.sh, dm-narrator.sh)
- `.claude/additional/campaign-rules-templates/` — campaign rule templates
- `.claude/additional/narrator-styles/` — narrator style definitions

## CORE tools (always available)
| Tool | Lib | Purpose |
|------|-----|---------|
| `dm-roll.sh` | `dice.py` | Dice with `--label`, `--dc`, `--ac`. Auto-lookup: `--skill "name"`, `--save "name"`, `--attack "weapon"`, `--initiative "name" ...`, `--advantage`, `--disadvantage`. Reads entities from world.json. Auto-combat: `--target "creature"` (player attacks, AC from world.json), `--defend --from "creature"` (creature attacks, stats from world.json). Auto-damage on hit. |
| `dm-inventory.sh` | `inventory_manager.py` | Items, weight, gold, HP/XP, transfers, `remove` (sold/destroyed/consumed), `use` (auto-consume via wiki), `craft` (auto-craft via wiki recipe). Always use `--qty N`, never call multiple times. |
| `dm-status.sh` | `inventory_manager.py status` | Compact inventory for session start |
| `dm-player.sh` | `player_manager.py` | XP, HP, HP max, gold, conditions |
| `dm-session.sh` | `session_manager.py` | Start/end, move (`--elapsed N`), save/restore |
| `dm-npc.sh` | `npc_manager.py` | NPCs, party, attitudes |
| `dm-location.sh` | `location_manager.py` | Locations, connections |
| `dm-note.sh` | `note_manager.py` | World facts |
| `dm-plot.sh` | `plot_manager.py` | Quests, objectives |
| `dm-consequence.sh` | `consequence_manager.py` | Timed events |
| `dm-time.sh` | `time_manager.py` | Game clock. Usage: `dm-time.sh "<time>" "<date>" --elapsed N [--sleeping]`. Positional args required. |
| `dm-campaign.sh` | `campaign_manager.py` | Campaign management |
| `dm-wiki.sh` | `wiki_manager.py` | Structured knowledge base: items, recipes, abilities, materials |
| `dm-condition.sh` | `player_manager.py` | Condition management (add/remove/check) — wrapper for dm-player.sh condition |
| `dm-search.sh` | `entity_enhancer.py` | Hybrid world-state + RAG search for scenes and entities |
| `dm-overview.sh` | — | World state overview (NPCs, locations, facts, consequences) |
| `dm-enhance.sh` | `entity_enhancer.py` | RAG entity enhancement — auto-runs on dm-session.sh move |

## Calendar system
- `lib/calendar.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"calendar"` section (months, weekdays, epoch)
- Used by `time_manager.py` for date display and weekday calculation

## Currency system
- `lib/currency.py` — universal, configurable per campaign
- Config in `campaign-overview.json` → `"currency"` section
- Stored as single int in base units (copper for D&D)
- `format_money(2537)` → `"25g 3s 7c"`, `parse_money("2gp 5sp")` → `250`

## Module pattern (for optional modules)
Each module in `modules/<name>/`:
- `middleware/<tool>.sh` — intercepts CORE tool calls (pre-hook: exit 0 = handled)
- `middleware/<tool>.sh.post` — runs after CORE (post-hook: always runs)
- `lib/` — module Python code
- `tools/` — module-specific CLI
- `module.json` — metadata, replaces dm-slots

Modules declare neutral `provides`, `providers`, and `action_routes` contracts in
`module.json`. A module MUST NOT import, inspect, or name another gameplay
module. CORE composes active capabilities and resolved DM rules.

**Modules MUST be campaign-agnostic (MANDATORY).** This is a public repo used by multiple campaigns. NEVER add campaign-specific content (character names, spell names, setting-specific rules, faction names) to module code, module rules, or dm-slots. Campaign-specific rules belong in `campaign-rules.md` for that campaign only.

## Dev commands
```bash
uv run pytest                                              # run all tests
bash .claude/additional/infrastructure/tools/dm-module.sh list # list active modules
```

## Data Architecture — WorldGraph
- **`world.json`** — unified entity graph. ALL game data: player, NPCs, locations, items, creatures, facts, quests, consequences, spells, economy. One file per campaign.
- **`campaign-overview.json`** — metadata only: time, date, calendar, modules, narrator style, genre, tone.
- **`campaign-rules.md`** — per-campaign rules.
- Custom stats, inventory, wiki — all stored as nodes in `world.json`.
- `dm-time.sh --elapsed` auto-ticks via WorldGraph: custom stats decay, recurring expenses/income, production, consequences, random events.
- Move + time: `dm-session.sh move "Location" --elapsed 0.5` combines move and time advance in one call.

## Rules
- **LANGUAGE POLICY (MANDATORY, NO EXCEPTIONS):** ALL rules files (dm-slots, module rules, CLAUDE.md, module.json) MUST be written entirely in English — every sentence, every example, every table cell. Campaign DATA (NPC names, location names, fact content, session logs) can be in any language.
- All tools route through `lib/world_graph.py` for data operations.
- `dm-world.sh` is the unified CLI — all old tools (dm-npc.sh, dm-location.sh, etc.) are thin wrappers over it.

## DM Gameplay Rules
All gameplay rules (combat, movement, narration, loot, social, time management, state persistence) live in `.claude/additional/dm-slots/`. These are loaded at session start into `/tmp/dm-rules.md`. Edit THOSE files for gameplay changes, not this file. This file is dev-only.

## Verification
- After lib/ or tools/ changes: `uv run pytest`
- After dm-slots or module rules edits: verify English-only (no Russian text in rules files)
- After JSON schema changes: run affected tool with `--help` to verify it still parses
- After module middleware changes: test the intercepted action end-to-end
- Proving a fix is load-bearing: delete the element ENTIRELY (name together with body) and repair
  the call sites, mutating each part of the fix separately. Replacing a body with `pass` while the
  name still exists keeps the dependency alive and reports a false "not exercised" — that is how
  a fixture was almost dropped as dead while 14 tests still referenced it by name.

## Slot System
All dm-slots files are replaceable by modules. Each slot has a `<!-- slot:name -->` marker. Modules declare `"replaces": ["slot-name"]` in module.json to override a slot. The loader (`dm-active-modules-rules.sh`) skips replaced slots and loads module rules instead.

## Post-compaction recovery
After context compaction, ALWAYS reload DM rules before continuing gameplay:
```bash
# DM rules are pre-compiled by the UserPromptSubmit hook
Read /tmp/dm-rules.md
```
If `/tmp/dm-rules.md` is missing (hook didn't run), recompile:
```bash
bash .claude/additional/infrastructure/dm-active-modules-rules.sh > /tmp/dm-rules.md 2>/dev/null
```
Then read the file.

## Session notes (2026-07-20)

### What happened (this session)
Three major changes to the wizard + one frontend feature + one bug fix:
1. **Wizard schema fix** — added explicit required properties to CAMPAIGN_SETUP_SCHEMA player.data (16 fields) and node type descriptions (consequence needs trigger+status, etc.). This was the FIRST fix attempt before the full rewrite.
2. **Wizard rewrite** — replaced monolithic `create_campaign` JSON blueprint with incremental CLI tools (dm-campaign.sh, dm-location.sh, dm-npc.sh, etc.). Worker `wizard-rewrite` (Opus 4.8) did this. -1952/+247 lines.
3. **Campaign delete button** — added ✕ button on each campaign-item in sidebar with confirm dialog.
4. **Wizard message queue** — fixed bug where sidebar submit during DM generation silently lost the message. Added `pendingWizardMsg` state.
5. **Deleted `backend/campaign_setup.py`** (814 lines) and `tests/test_campaign_setup.py` (443 lines) — no longer needed after wizard rewrite.

### Key decisions
- **Wizard uses CLI tools, not JSON blueprint** — DM now calls dm-campaign.sh, dm-location.sh, dm-npc.sh, dm-plot.sh, dm-player.sh etc. to create campaigns incrementally. No more CAMPAIGN_SETUP_SCHEMA, validate_campaign_setup, apply_campaign_setup.
- **Wizard MCP = 3 UI-only tools** — show_choices, clear_choices, wizard_complete. Campaign data creation is via bash tools.
- **SDK allowed_tools removed** — `_make_options()` no longer sets `allowed_tools`. Under bypassPermissions everything is granted; the old allowlist was blocking bash tools for BOTH wizard and game mode.
- **campaign_api.create_campaign simplified** — dropped `setup`, `require_ready` params. REST endpoint never used them.
- **Pending wizard message queue** — `state.pendingWizardMsg` stores one message if DM is generating. Sent automatically on `done` event with `skipEcho: true`.

### Architecture (current)
```
Browser (vanilla JS) → nginx (SSL) → FastAPI (server.py)
  ├─ /ws/game?campaign=X → GameSession registry → ClaudeSDKProvider → claude CLI subprocess → Anthropic
  ├─ /ws/wizard → ephemeral provider + WizardMCP (3 UI tools) + bash tools (dm-*.sh)
  ├─ /api/* → REST endpoints (campaigns, status, models, health)
  └─ / → frontend/index.html (static)
```

### Deploy
- **VPS:** Contabo DE (158.220.127.161), user `kesha`, project at `/home/kesha/projects/dnd-game-master`
- **Domain:** https://dnd-game-master.duckdns.org (DuckDNS, SSL via certbot). Token in
  `~/.duckdns_token` (0600, not in git); a `*/30` cron re-points the record at the VPS's current
  public IP, so a hardware move that changes the IP self-heals within 30 min.
  The old `dnd.seedon.ru` was dropped on 2026-08-07: seedon.ru belongs to a company that had to
  remove any public "company domain → German server" link (152-ФЗ). Do not resurrect it — the name
  now resolves to their Moscow wildcard.
- **The DuckDNS token is account-wide, and the account is shared. `dnd-game-master` is the ONLY
  domain this project may touch.** The same account holds the owner's personal VPN domain
  (`foghedgehog`); the token cannot tell them apart, so nothing but discipline stops a wrong
  `domains=` parameter from repointing the VPN. Two agents already did exactly that on 2026-08-07 —
  once from another project, once here — before anyone realised the token has no per-domain scope.
  Splitting the accounts was considered and rejected by the owner: one account stays, the boundary
  is the rule. Always name the domain explicitly, never loop over the account's domains.
- **A 200 is transport, not meaning.** DuckDNS answers a revoked token with `HTTP 200` and body
  `KO`, so `curl -f` never fires: compare the RESPONSE BODY against the expected value, and test the
  failing branch with a deliberately wrong value. Verified 2026-08-07 — the original keep-alive cron
  would have reported success forever after the token was reissued.
- **Service:** `systemd dnd-game-master.service`
- **Password:** `dnd2026game` (in `.env` on VPS as `DND_AUTH_PASSWORD`)
- **Port:** 18083 (registered in `~/ports.md`)
- **No proxy needed** — Contabo in DE, direct Anthropic access
- **Deploy = git pull, NOT rsync.** VPS is a real git clone of `origin` (converted 2026-08-03; it used to be an rsync dump with an empty `.git`, which made pull and rollback impossible). Push first — the VPS pulls from GitHub, not from the laptop:
  ```bash
  git push origin main
  ssh root@158.220.127.161 "su -s /bin/bash kesha -c 'cd /home/kesha/projects/dnd-game-master && git pull --ff-only' && systemctl restart dnd-game-master"
  ```
- **Run git as `kesha`, never root** — `su -s /bin/bash kesha` (`su - kesha` hangs: no password). Root-owned files under `User=kesha` break `.git` writes mid-deploy. Check: `find /home/kesha/projects/dnd-game-master ! -user kesha | wc -l` → must be 0
- **Live data is NOT in git** — `world-state/campaigns` (13 campaigns), `world-state/usage` and `.env` are gitignored and exist only on the VPS. Never `git clean` or re-clone over them without a backup

### Orchestrator lives on the VPS (migrated 2026-08-03)
**Read `docs/vps-handoff.md` first** — full state handoff written before the migration: what was done, what is still open, and the traps. Context does not survive the move; that file does.
The project is played on https://dnd-game-master.duckdns.org, so the orchestrator session runs on the VPS, not the laptop.
- **Migration tool:** `scripts/migrate_agent.py` in the Orchestra repo — moves the session WITH its transcript, logs, inbox and worktrees (`UPSERT`, so it also works when no session exists on the target). Do NOT hand-write `INSERT`/`UPDATE` into `orchestra.db`; §6 of `docs/vps-orchestrator-onboarding.md` describes the opposite case (resetting an existing stale session).
- **An orchestrator cannot migrate itself** — `assert_idle` counts the caller as `running`. Someone outside must launch it. The gate only inspects the SOURCE host, so agents running on the VPS do not block it.
- **Never restart Orchestra on the VPS yourself** — it kills the in-flight turns of every agent there, including other projects'. `Orchestra-orchestrator` owns that restart.
- **MCP servers are per-session**, stored in the `mcp_servers_custom` DB column — NOT in `~/.claude.json` (which is empty for `kesha` and stays that way). `orchestra` MCP is injected automatically. Ask `Orchestra-orchestrator` to provision anything else.
- **Dashboard port 8888 is firewalled off** — reachable only as https://orchestra.seedon.ru from outside, or `127.0.0.1:8888` from inside the VPS.
- **Skills copied from the laptop carry hardcoded `/mnt/data/...` paths** and silently break. Grep any copied skill for `/mnt/data` before trusting it. Fix with an env var + default, e.g. `ENV_FILE="${DEEPGRAM_ENV_FILE:-/home/kesha/orchestra/.env}"` — not a second hardcode.
- **An MCP entry in the config proves nothing** — verify the underlying binary exists (`mcp-pandoc` was configured server-wide while `pandoc` itself was missing). Check the fact, not the config line.

### Important files
- `backend/server.py` — main FastAPI app, WS handlers, auth middleware
- `backend/game_session.py` — GameSession registry, turn lifecycle, hibernate
- `backend/live_broker.py` — pub/sub (43 lines)
- `backend/event_log.py` — JSONL append-only log
- `backend/providers/claude_sdk.py` — SDK wrapper, streaming, context usage, NO allowed_tools
- `backend/claude_dm.py` — system prompt assembly (dm-rules + narrator + campaign context)
- `backend/wizard_mcp.py` — MCP with 3 UI tools: show_choices, clear_choices, wizard_complete
- `backend/wizard_prompt.py` — wizard system prompt with bash-tool creation phases
- `backend/auth.py` — cookie auth with login page
- `backend/config.py` — env config, default model `claude-sonnet-5`
- `backend/campaign_api.py` — simplified create_campaign (no setup/require_ready)
- `frontend/js/app.js` — main frontend, streaming typewriter, campaign list, wizard, pendingWizardMsg queue
- `frontend/css/style.css` — Orchestra-style dark theme, campaign-delete-btn styles

### Workers
- `vanilla-frontend` — Opus 5, idle, ctx:70%. Long-lived system worker for all frontend+backend work

### Security rules established
- Campaign names validated: regex blocks path traversal (`../`)
- Session IDs validated: `^[A-Za-z0-9_-]{1,64}$`
- `bypassPermissions` on SDK — accepted for local/auth-gated use
- Auth middleware skips `/auth/*` and static assets

### Known issues
- Pre-existing pytest collection error: `test_encounter_engine.py` duplicate basename between `tests/` and `.claude/additional/modules/world-travel/tests/`
- Wizard hasn't been tested end-to-end with the new bash-tool flow yet (deployed, user started testing but hit the pending message bug which is now fixed)
- Tests: 357 passed as of last run
