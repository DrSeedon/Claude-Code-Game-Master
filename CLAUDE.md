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

## Session notes (2026-07-20 → 2026-07-22)

### What happened (mega-session)
Full rewrite of DnD Game Master web client from React → vanilla JS, modeled after Orchestra's architecture.

### Key decisions
- **Killed API provider** — `anthropic_api.py` + `tools_registry.py` deleted (~1200 lines). SDK-only path via `claude-agent-sdk`
- **React → Vanilla JS** — deleted entire `frontend/src/`, `node_modules/`, `package.json`. Now: `frontend/{index.html, css/style.css, js/app.js}` (~1100 lines total). Zero npm, zero build
- **FastAPI serves everything** — one process (uvicorn :18083), serves static + API + WS. No separate frontend server
- **GameSession registry** — turn runs in background asyncio.Task, WS disconnect doesn't kill DM mid-sentence
- **LiveBroker** — in-memory pub/sub per campaign, multiple WS subscribers possible
- **EventLog** — append-only JSONL per campaign (`events.jsonl`), monotonic ids, `after_id` replay on reconnect
- **Wizard = ephemeral** — no session persistence for campaign creation wizard. One-shot, disconnect = lost
- **Models** — whitelist `[claude-sonnet-5, claude-opus-4-8]`, default `claude-sonnet-5`. Model pill (click-cycle) in header
- **Auth** — cookie-based login page (`backend/auth.py`), password in `DND_AUTH_PASSWORD` env
- **Bind 127.0.0.1** — not 0.0.0.0. nginx reverse proxy on VPS
- **Campaign-addressed WS** — `/ws/game?campaign=X&after_id=N&model=M`, no global active campaign for WS

### Architecture (current)
```
Browser (vanilla JS) → nginx (SSL) → FastAPI (server.py)
  ├─ /ws/game?campaign=X → GameSession registry → ClaudeSDKProvider → claude CLI subprocess → Anthropic
  ├─ /ws/wizard → ephemeral provider + in-process WizardMCP (asyncio.Queue)
  ├─ /api/* → REST endpoints (campaigns, status, models, health)
  └─ / → frontend/index.html (static)
```

### Deploy
- **VPS:** Contabo DE (158.220.127.161), user `kesha`, project at `/home/kesha/projects/dnd-game-master`
- **Domain:** https://dnd.seedon.ru (DNS in Selectel, SSL via certbot)
- **Service:** `systemd dnd-game-master.service`
- **Password:** `dnd2026game` (in `.env` on VPS as `DND_AUTH_PASSWORD`)
- **Port:** 18083 (registered in `~/ports.md`)
- **No proxy needed** — Contabo in DE, direct Anthropic access
- **Deploy command:** `rsync -avz --exclude=... --delete /mnt/data/Projects/Python/Claude-Code-Game-Master/ root@158.220.127.161:/home/kesha/projects/dnd-game-master/ && ssh root@158.220.127.161 "chown -R kesha:kesha ... && systemctl restart dnd-game-master"`

### Important files
- `backend/server.py` — main FastAPI app, WS handlers, auth middleware
- `backend/game_session.py` — GameSession registry, turn lifecycle, hibernate
- `backend/live_broker.py` — pub/sub (43 lines)
- `backend/event_log.py` — JSONL append-only log
- `backend/providers/claude_sdk.py` — SDK wrapper, streaming, context usage
- `backend/claude_dm.py` — system prompt assembly (dm-rules + narrator + campaign context)
- `backend/wizard_mcp.py` — in-process MCP for wizard (show_choices, create_campaign)
- `backend/auth.py` — cookie auth with login page
- `backend/config.py` — env config, default model `claude-sonnet-5`
- `frontend/js/app.js` — main frontend (~950 lines), streaming typewriter, campaign list, wizard
- `frontend/css/style.css` — Orchestra-style dark theme
- `docs/tasks/sdk-comparison-research.md` — deep Orchestra vs DnD comparison
- `docs/tasks/frontend-migration-blueprint.md` — streaming migration spec
- `artifacts/architecture.html` — interactive architecture diagram

### Workers
- `vanilla-frontend` — Opus 4.8, idle, ctx:70%. Long-lived system worker for all frontend+backend work on this project. Has deep context of entire codebase

### Security rules established
- Campaign names validated: regex blocks path traversal (`../`)
- Session IDs validated: `^[A-Za-z0-9_-]{1,64}$`
- `bypassPermissions` on SDK — accepted for local/auth-gated use
- Auth middleware skips `/auth/*` and static assets

### Known issues
- Pre-existing pytest collection error: `test_encounter_engine.py` duplicate basename between `tests/` and `.claude/additional/modules/world-travel/tests/`
- Codex review bg jobs consistently fail to write output files (CWD-bug in Orchestra codex_review tool) — workers self-verify instead
